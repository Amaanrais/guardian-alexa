"""Domain age via RDAP, with a hard timeout and an in-memory cache."""

import asyncio
import time
from datetime import UTC, datetime

import httpx

from . import config

BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
FALLBACK_BASE = "https://rdap.org/"
SUCCESS_TTL_S = 24 * 3600
FAILURE_TTL_S = 10 * 60

_cache: dict[str, tuple[float, int | None]] = {}
_bootstrap: dict[str, str] | None = None
_bootstrap_task: asyncio.Task | None = None
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(follow_redirects=True, headers={"Accept": "application/rdap+json"})
    return _client


async def _load_bootstrap() -> None:
    global _bootstrap
    try:
        resp = await _get_client().get(BOOTSTRAP_URL, timeout=5.0)
        resp.raise_for_status()
        table: dict[str, str] = {}
        for tlds, urls in resp.json()["services"]:
            base = next((u for u in urls if u.startswith("https://")), urls[0])
            for tld in tlds:
                table[tld.lower()] = base if base.endswith("/") else base + "/"
        _bootstrap = table
    except Exception:
        pass  # fall back to rdap.org; retried on a later lookup


def _base_for(domain: str) -> str:
    global _bootstrap_task
    if _bootstrap is None and (_bootstrap_task is None or _bootstrap_task.done()):
        _bootstrap_task = asyncio.create_task(_load_bootstrap())
    tld = domain.rsplit(".", 1)[-1]
    return (_bootstrap or {}).get(tld, FALLBACK_BASE)


def _registration_age_days(data: dict) -> int | None:
    for event in data.get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            registered = datetime.fromisoformat(event["eventDate"].replace("Z", "+00:00"))
            if registered.tzinfo is None:
                registered = registered.replace(tzinfo=UTC)
            return max(0, (datetime.now(UTC) - registered).days)
    return None


async def fetch_age_days(domain: str) -> int | None:
    """Network lookup, no cache. Tests replace this."""
    resp = await _get_client().get(f"{_base_for(domain)}domain/{domain}")
    if resp.status_code != 200:
        return None
    return _registration_age_days(resp.json())


async def domain_age_days(domain: str) -> int | None:
    """Days since registration, or None if unknown. Never takes longer than RDAP_TIMEOUT_S."""
    now = time.monotonic()
    cached = _cache.get(domain)
    if cached and cached[0] > now:
        return cached[1]
    try:
        async with asyncio.timeout(config.RDAP_TIMEOUT_S):
            age = await fetch_age_days(domain)
    except Exception:
        age = None
    _cache[domain] = (now + (SUCCESS_TTL_S if age is not None else FAILURE_TTL_S), age)
    return age
