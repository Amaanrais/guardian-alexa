"""check_link fast path, the background sandbox job store, and get_link_report."""

import asyncio
import secrets
import time
from dataclasses import dataclass, field
from typing import Literal

from . import config, rdap, sandbox, scoring
from .lookalike import brand_signals, claimed_brands, registrable_domain, url_signals
from .netguard import BlockedURLError, parse_url, resolve_public
from .scoring import Signal

JobStatus = Literal["pending", "running", "done", "blocked", "not_found"]

JOB_TTL_S = 3600
ACCOUNT_SECRETS = {"password", "pin", "otp"}
MAX_JOBS = 1000


@dataclass
class Job:
    url: str
    quick_signals: list[Signal]
    status: JobStatus = "pending"
    sandbox_signals: list[Signal] = field(default_factory=list)
    screenshot_path: str | None = None
    created: float = field(default_factory=time.monotonic)


_jobs: dict[str, Job] = {}
_tasks: set[asyncio.Task] = set()
_semaphore: asyncio.Semaphore | None = None


def _prune() -> None:
    cutoff = time.monotonic() - JOB_TTL_S
    for job_id in [j for j, job in _jobs.items() if job.created < cutoff]:
        del _jobs[job_id]
    while len(_jobs) >= MAX_JOBS:
        del _jobs[next(iter(_jobs))]


def _age_signals(age_days: int | None) -> list[Signal]:
    if age_days is None:
        return []
    if age_days < 30:
        return [Signal("domain_very_new", f"This website was only set up {age_days} days ago.")]
    if age_days < 180:
        return [Signal("domain_new", "This website was set up in the last few months.")]
    return []


async def quick_check(url: str) -> tuple[list[Signal], bool]:
    """Fast checks only. Returns (signals, sandbox_allowed)."""
    try:
        parsed = parse_url(url)
    except BlockedURLError as exc:
        return [Signal(exc.code, str(exc))], False

    signals = url_signals(parsed)

    async def dns() -> Signal | None:
        try:
            async with asyncio.timeout(config.QUICK_DNS_TIMEOUT_S):
                await resolve_public(parsed)
        except BlockedURLError as exc:
            return Signal(exc.code, str(exc))
        except TimeoutError:
            pass  # slow DNS is not a red flag; the sandbox re-checks every hop anyway
        return None

    dns_signal, age = await asyncio.gather(dns(), rdap.domain_age_days(registrable_domain(parsed.host)))
    signals += _age_signals(age)
    if dns_signal:
        signals.append(dns_signal)
    return signals, not (dns_signal and dns_signal.code == "private_address")


def _sandbox_signals(result: sandbox.SandboxResult, start_url: str) -> list[Signal]:
    signals: list[Signal] = []
    if result.blocked_url:
        signals.append(Signal("redirect_to_private", "The link tried to send us to a private network address, so we stopped."))
    if result.download_attempted:
        signals.append(Signal("download_attempt", "The page tried to download a file to your device."))
    for kind, reason in (
        ("password", "The page asks for a password."),
        ("otp", "The page asks for a one-time security code."),
        ("card", "The page asks for bank card details."),
        ("pin", "The page asks for a PIN."),
    ):
        if kind in result.fields:
            signals.append(Signal(f"{kind}_field", reason))
    if result.final_domain and result.fields:
        # Claiming a brand is only damning on a page that also asks for secrets. Payment brands
        # sit next to card fields on every honest checkout, so for them only a password, PIN or
        # one-time code counts.
        for brand in claimed_brands(result.identity_text, result.final_domain):
            secrets_asked = result.fields & ACCOUNT_SECRETS if brand.payment else result.fields
            if not secrets_asked:
                continue
            signals.append(Signal(
                "brand_impersonation",
                f"The page says it's {brand.name}, but it isn't on {brand.domains[0]}, and it asks for private details.",
            ))
    start_host = parse_url(start_url).host if start_url else None
    if result.final_domain and start_host and registrable_domain(result.final_domain) != registrable_domain(start_host):
        signals.append(Signal("cross_domain_redirect", f"The link sends you on to a different website ({result.final_domain})."))
        signals += brand_signals(result.final_domain)
    if not result.final_url and not result.blocked_url:
        signals.append(Signal("page_unreachable", "We couldn't open the page to check it."))
    return signals


async def _run_job(job_id: str) -> None:
    global _semaphore
    job = _jobs[job_id]
    _semaphore = _semaphore or asyncio.Semaphore(config.SANDBOX_CONCURRENCY)
    async with _semaphore:
        job.status = "running"
        result = await sandbox.run_sandbox(job.url, config.SCREENS_DIR / f"{job_id}.png")
    signals = _sandbox_signals(result, job.url)
    if result.final_domain and registrable_domain(result.final_domain) != registrable_domain(parse_url(job.url).host):
        signals += _age_signals(await rdap.domain_age_days(registrable_domain(result.final_domain)))
    job.sandbox_signals = signals
    job.screenshot_path = result.screenshot_path
    job.status = "blocked" if result.blocked_url else "done"


async def check_link(url: str) -> dict:
    signals, sandbox_allowed = await quick_check(url)
    _prune()
    job_id = secrets.token_urlsafe(12)
    job = Job(url=url.strip(), quick_signals=signals)
    _jobs[job_id] = job
    if sandbox_allowed:
        task = asyncio.create_task(_run_job(job_id))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    else:
        job.status = "blocked"
    return {
        "quick_verdict": scoring.link_verdict(signals),
        "reasons": scoring.reasons(signals),
        "job_id": job_id,
        "level": scoring.level(signals),
    }


def get_link_report(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if job is None:
        return {
            "status": "not_found",
            "verdict": "Be careful",
            "reasons": ["We don't have a report for this check. It may have expired; please check the link again."],
            "screenshot_path": None,
        }
    signals = job.quick_signals + job.sandbox_signals
    reasons = scoring.reasons(signals)
    if job.status in ("pending", "running"):
        reasons.append("We're still opening the page to look closer.")
    return {
        "status": job.status,
        "verdict": scoring.link_verdict(signals),
        "reasons": reasons,
        "screenshot_path": job.screenshot_path,
    }
