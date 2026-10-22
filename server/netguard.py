"""SSRF guard. Every outbound fetch of a user-supplied URL goes through `guarded_fetch`.

Rules: http/https only; the hostname is resolved here and every resolved address must be
publicly routable; the connection is pinned to the vetted IP (no second DNS lookup for an
attacker to rebind); redirects are never followed here, so each hop is re-checked by the caller.
"""

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx
import idna

MAX_URL_LENGTH = 2048
ALLOWED_SCHEMES = {"http", "https"}

_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_HOP_BY_HOP = {
    "host", "connection", "keep-alive", "proxy-authorization", "proxy-connection",
    "te", "trailer", "transfer-encoding", "upgrade", "content-length",
}


class BlockedURLError(Exception):
    """The URL must not be fetched. `code` is "invalid_url" or "private_address"."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ParsedURL:
    url: str
    scheme: str
    host: str  # ASCII (IDNA-encoded), lower-case, no trailing dot
    port: int
    display_host: str  # Unicode form, for look-alike checks
    has_userinfo: bool


def is_blocked_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%", 1)[0])
    if isinstance(ip, ipaddress.IPv6Address):
        # IPv6 forms that embed an IPv4 address are judged by that address.
        embedded = ip.ipv4_mapped or ip.sixtofour or (ip.teredo[1] if ip.teredo else None)
        if embedded is None and ip in _NAT64:
            embedded = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
        if embedded is not None and is_blocked_ip(str(embedded)):
            return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def parse_url(url: str) -> ParsedURL:
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise BlockedURLError("invalid_url", "This link is unusually long, so it can't be checked.")
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise BlockedURLError("invalid_url", "This doesn't look like a valid web link.") from None
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise BlockedURLError("invalid_url", "Only ordinary web links (http or https) can be checked.")
    raw_host = (parts.hostname or "").rstrip(".")
    if not raw_host:
        raise BlockedURLError("invalid_url", "This doesn't look like a valid web link.")
    try:
        ipaddress.ip_address(raw_host)
        host = display = raw_host
    except ValueError:
        try:
            host = idna.encode(raw_host, uts46=True).decode("ascii")
            display = idna.decode(host)
        except idna.IDNAError:
            raise BlockedURLError("invalid_url", "This web address contains characters that aren't allowed.") from None
    return ParsedURL(
        url=url,
        scheme=scheme,
        host=host.lower(),
        port=port or (443 if scheme == "https" else 80),
        display_host=display.lower(),
        has_userinfo=parts.username is not None,
    )


async def resolve_host(host: str, port: int) -> list[str]:
    """Resolve to IP strings. Tests replace this to simulate DNS."""
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(info[4][0] for info in infos))


async def resolve_public(parsed: ParsedURL) -> list[str]:
    """Resolve and vet every address. Raises BlockedURLError if any is non-public."""
    try:
        ips = await resolve_host(parsed.host, parsed.port)
    except socket.gaierror:
        raise BlockedURLError("dns_failed", "We couldn't find this website.") from None
    if not ips:
        raise BlockedURLError("dns_failed", "We couldn't find this website.")
    # Reject if *any* record is private: an attacker can mix public and private records.
    if any(is_blocked_ip(ip) for ip in ips):
        raise BlockedURLError(
            "private_address", "This link points to a private or internal network address, so it can't be checked."
        )
    return ips


@dataclass
class FetchResult:
    url: str
    status: int
    headers: list[tuple[str, str]]
    body: bytes


async def guarded_fetch(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    max_bytes: int = 5_000_000,
) -> FetchResult:
    """Fetch one hop. Never follows redirects; the caller must re-check any Location itself."""
    parsed = parse_url(url)
    ips = await resolve_public(parsed)
    ip = ips[0]
    pinned = httpx.URL(parsed.url).copy_with(host=ip)
    default_port = 443 if parsed.scheme == "https" else 80
    host_header = parsed.host if parsed.port == default_port else f"{parsed.host}:{parsed.port}"
    out_headers = {k: v for k, v in (headers or {}).items() if k.lower() not in _HOP_BY_HOP}
    out_headers["Host"] = host_header
    extensions = {"sni_hostname": parsed.host} if parsed.scheme == "https" else {}

    request = client.build_request(method, pinned, headers=out_headers, extensions=extensions)
    response = await client.send(request, stream=True, follow_redirects=False)
    try:
        body = bytearray()
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > max_bytes:
                break
    finally:
        await response.aclose()
    # httpx has already decoded the body, so drop encoding/length headers.
    resp_headers = [
        (k, v) for k, v in response.headers.multi_items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "content-encoding"
    ]
    return FetchResult(url=parsed.url, status=response.status_code, headers=resp_headers, body=bytes(body[:max_bytes]))


REDIRECT_STATUSES = {301, 302, 303, 307, 308}


def redirect_target(result: FetchResult) -> str | None:
    if result.status not in REDIRECT_STATUSES:
        return None
    location = next((v for k, v in result.headers if k.lower() == "location"), None)
    return urljoin(result.url, location) if location else None


async def guarded_fetch_following(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    max_hops: int = 5,
) -> FetchResult:
    """GET, following redirects, with every hop re-parsed, re-resolved and vetted."""
    for _ in range(max_hops + 1):
        result = await guarded_fetch(client, url, headers=headers)
        target = redirect_target(result)
        if target is None:
            return result
        url = target
    raise BlockedURLError("invalid_url", "This link redirects too many times.")
