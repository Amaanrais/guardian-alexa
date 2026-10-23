"""Opens a link in a throwaway headless Chromium and records what the page asks for.

The browser never touches the network itself. Every request is intercepted and fetched by
`netguard.guarded_fetch`, so each redirect hop, sub-resource and script-driven navigation is
re-resolved and vetted. As a backstop the browser is pointed at a dead proxy, so anything that
somehow escapes interception goes nowhere.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from playwright.async_api import Request, Route, async_playwright

from . import config
from .netguard import BlockedURLError, guarded_fetch, guarded_fetch_following, redirect_target

log = logging.getLogger(__name__)

MAX_REQUESTS = 200
MAX_NAVIGATIONS = 10
PER_REQUEST_TIMEOUT_S = 5.0
SETTLE_S = 1.5  # time left for script/meta redirects after load
DEAD_PROXY = "http://127.0.0.1:9"
SKIPPED_RESOURCE_TYPES = {"media", "font", "websocket", "eventsource", "manifest", "ping"}

# Runs before any page script: forms can't be submitted and WebRTC is gone.
NO_SUBMIT_JS = """
(() => {
  const block = function () {};
  HTMLFormElement.prototype.submit = block;
  HTMLFormElement.prototype.requestSubmit = block;
  window.addEventListener('submit', e => { e.preventDefault(); e.stopImmediatePropagation(); }, true);
  for (const name of ['RTCPeerConnection', 'webkitRTCPeerConnection']) {
    try { delete window[name]; window[name] = undefined; } catch (e) {}
  }
})();
"""

DETECT_FIELDS_JS = r"""
() => {
  const found = new Set();
  for (const el of document.querySelectorAll('input, select, textarea')) {
    const type = (el.getAttribute('type') || 'text').toLowerCase();
    if (type === 'hidden' || type === 'submit' || type === 'button') continue;
    const ac = (el.getAttribute('autocomplete') || '').toLowerCase();
    const labels = el.labels ? Array.from(el.labels).map(l => l.textContent).join(' ') : '';
    const text = [el.name, el.id, el.getAttribute('placeholder'), el.getAttribute('aria-label'), labels, ac]
      .join(' ').toLowerCase();
    if (type === 'password') found.add('password');
    if (ac === 'one-time-code' || /\b(otp|one[\s-]?time|verification code|2fa|passcode|auth(entication)? code|sms code)\b/.test(text)) found.add('otp');
    if (ac.startsWith('cc-') || /(card ?number|cardnumber|cc-?num|\bcvv2?\b|\bcvc\b|\bcsc\b|expir|credit ?card|debit ?card)/.test(text)) found.add('card');
    if (/\bpin\b/.test(text)) found.add('pin');
  }
  return Array.from(found);
}
"""


# Where a page names itself: title, h1/h2, logo alt text and og:site_name. Body copy is
# deliberately left out; it names other brands all the time ("Pay with PayPal").
IDENTITY_TEXT_JS = """
() => {
  const parts = [document.title];
  for (const h of document.querySelectorAll('h1, h2')) parts.push(h.innerText);
  for (const img of document.querySelectorAll('img[alt]')) {
    const hint = [img.alt, img.id, img.className, img.getAttribute('src')].join(' ').toLowerCase();
    if (hint.includes('logo')) parts.push(img.alt);
  }
  for (const m of document.querySelectorAll('meta[property="og:site_name"]')) parts.push(m.content);
  return parts.filter(Boolean).join('\\n');
}
"""
MAX_IDENTITY_TEXT = 4000

# All text on the page, hidden or not, plus HTML comments: where instructions aimed at an AI hide.
PAGE_TEXT_JS = """
() => {
  const parts = [];
  const walk = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT | NodeFilter.SHOW_COMMENT);
  while (walk.nextNode()) {
    const n = walk.currentNode, parent = n.parentNode && n.parentNode.nodeName;
    if (parent !== 'SCRIPT' && parent !== 'STYLE' && n.nodeValue.trim()) parts.push(n.nodeValue.trim());
  }
  for (const el of document.querySelectorAll('[aria-label], [title], img[alt]'))
    parts.push(el.getAttribute('aria-label') || el.getAttribute('title') || el.getAttribute('alt') || '');
  return parts.join('\\n');
}
"""
MAX_PAGE_TEXT = 20000


@dataclass
class SandboxResult:
    redirect_chain: list[str] = field(default_factory=list)
    final_url: str | None = None
    final_domain: str | None = None
    fields: set[str] = field(default_factory=set)
    identity_text: str = ""  # title, h1/h2, logo alt text and og:site_name, across frames
    page_text: str = ""  # every text node and comment, hidden ones too; only ever scanned, never passed on
    screenshot_path: str | None = None
    blocked_url: str | None = None  # a hop that resolved to a private address
    download_attempted: bool = False
    error: str | None = None


def _host(url: str) -> str | None:
    try:
        return (urlsplit(url).hostname or "").lower() or None
    except ValueError:
        return None


async def run_sandbox(url: str, screenshot_path: Path, client: httpx.AsyncClient | None = None) -> SandboxResult:
    """Never raises; problems are reported on the result. `client` is injectable for tests."""
    result = SandboxResult()
    own_client = client is None
    client = client or httpx.AsyncClient(timeout=PER_REQUEST_TIMEOUT_S, verify=True)
    try:
        async with asyncio.timeout(config.SANDBOX_TIMEOUT_S + 5):  # hard cap incl. browser start-up
            await _browse(url, screenshot_path, client, result)
    except TimeoutError:
        result.error = result.error or "timeout"
    except Exception as exc:  # noqa: BLE001 - a broken page must not crash the job
        log.exception("sandbox failed for %s", url)
        result.error = result.error or type(exc).__name__
    finally:
        if own_client:
            await client.aclose()
    if result.final_url:
        result.final_domain = _host(result.final_url)
    return result


async def _browse(url: str, screenshot_path: Path, client: httpx.AsyncClient, result: SandboxResult) -> None:
    # Chromium follows a fulfilled 3xx without routing the next hop back through us, so the
    # browser is never handed a redirect. Main-frame hops are aborted and re-navigated by the
    # loop below (so page.url stays honest); sub-resource hops are followed in Python.
    request_count = 0
    pending_redirect: str | None = None

    async def handle(route: Route, request: Request) -> None:
        nonlocal request_count, pending_redirect
        request_count += 1
        is_main_nav = request.is_navigation_request() and request.frame.parent_frame is None
        if request_count > MAX_REQUESTS or request.resource_type in SKIPPED_RESOURCE_TYPES:
            await route.abort("blockedbyclient")
            return
        if request.method not in ("GET", "HEAD"):
            # No form posts or data uploads leave the sandbox.
            await route.abort("blockedbyclient")
            return
        if is_main_nav:
            if len(result.redirect_chain) >= MAX_NAVIGATIONS:
                await route.abort("blockedbyclient")
                return
            result.redirect_chain.append(request.url)
        try:
            if is_main_nav:
                fetched = await guarded_fetch(client, request.url, method=request.method, headers=request.headers)
                target = redirect_target(fetched)
                if target:
                    pending_redirect = target
                    await route.abort("aborted")
                    return
            else:
                fetched = await guarded_fetch_following(client, request.url, headers=request.headers)
        except BlockedURLError as exc:
            if is_main_nav and exc.code == "private_address":
                result.blocked_url = request.url
            await route.abort("blockedbyclient")
            return
        except Exception:
            await route.abort("failed")
            return
        headers: dict[str, str] = {}
        for k, v in fetched.headers:
            # Chromium never fires "load" on a fulfilled response whose header value holds a newline
            # (Cloudflare tunnels repeat x-robots-tag), so only Set-Cookie keeps Playwright's "\n".
            sep = "\n" if k.lower() == "set-cookie" else ", "
            headers[k] = f"{headers[k]}{sep}{v}" if k in headers else v
        await route.fulfill(status=fetched.status, headers=headers, body=fetched.body)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            proxy={"server": DEAD_PROXY, "bypass": "<-loopback>"},
            args=["--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--disable-background-networking"],
        )
        try:
            context = await browser.new_context(
                accept_downloads=False,
                service_workers="block",
                viewport={"width": 1280, "height": 800},
            )
            await context.add_init_script(NO_SUBMIT_JS)
            await context.route("**/*", handle)
            await context.route_web_socket("**/*", lambda ws: None)  # mocked: never connects
            page = await context.new_page()

            def on_download(download) -> None:
                result.download_attempted = True
                asyncio.ensure_future(download.cancel())

            page.on("download", on_download)

            loop = asyncio.get_running_loop()
            deadline = loop.time() + config.SANDBOX_TIMEOUT_S - 1.0  # leave time for inspection
            next_url: str | None = url
            settled = False
            while next_url and not result.blocked_url:
                pending_redirect = None
                remaining = deadline - loop.time()
                if remaining <= 0:
                    result.error = "timeout"
                    break
                try:
                    await page.goto(next_url, wait_until="load", timeout=remaining * 1000)
                    result.error = None
                except Exception as exc:  # noqa: BLE001
                    # Partial loads are still worth inspecting; record why and carry on.
                    result.error = type(exc).__name__
                if pending_redirect is None and not settled:
                    # Give script and meta-refresh redirects a moment to fire.
                    settled = True
                    with contextlib.suppress(Exception):
                        await page.wait_for_timeout(min(SETTLE_S, max(0.0, deadline - loop.time())) * 1000)
                next_url = pending_redirect
            if result.blocked_url:
                result.error = "blocked"
                return

            loaded = not page.url.startswith(("about:", "chrome-error:"))
            result.final_url = page.url if loaded else None
            for frame in page.frames:
                with contextlib.suppress(Exception):
                    result.fields.update(await frame.evaluate(DETECT_FIELDS_JS))
                with contextlib.suppress(Exception):
                    text = await frame.evaluate(IDENTITY_TEXT_JS)
                    result.identity_text = (result.identity_text + "\n" + text)[:MAX_IDENTITY_TEXT]
                with contextlib.suppress(Exception):
                    text = await frame.evaluate(PAGE_TEXT_JS)
                    result.page_text = (result.page_text + "\n" + text)[:MAX_PAGE_TEXT]
            if loaded:
                with contextlib.suppress(Exception):
                    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                    await page.screenshot(path=str(screenshot_path), timeout=2000)
                    result.screenshot_path = str(screenshot_path)
        finally:
            await browser.close()
