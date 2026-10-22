import asyncio
import socket

import pytest

from server import config, family, linkcheck, netguard, rdap, storage


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
def _family_sandbox(tmp_path, monkeypatch):
    """Every test gets its own data folder and fake Telegram: no network, no real family."""
    storage.set_store(storage.JsonFileStore(tmp_path / "data"))
    monkeypatch.setattr(config, "TELEGRAM_FAKE", True)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "TELEGRAM_JOIN_CODE", "")
    monkeypatch.setattr(config, "FAKE_ANSWER_DELAY_S", 0.05)
    family.set_telegram(None)
    yield
    storage.set_store(None)
    family.set_telegram(None)


@pytest.fixture(autouse=True)
def _reset_state():
    linkcheck._jobs.clear()
    linkcheck._semaphore = None
    rdap._cache.clear()
    yield
    linkcheck._jobs.clear()


@pytest.fixture
def fake_dns(monkeypatch):
    """Replace DNS with a dict: host -> list of IPs. Unknown hosts fail to resolve."""
    records: dict[str, list[str]] = {}

    async def resolve(host: str, port: int) -> list[str]:
        try:
            import ipaddress

            ipaddress.ip_address(host)
            return [host]
        except ValueError:
            pass
        if host not in records:
            raise socket.gaierror(socket.EAI_NONAME, "not found")
        return records[host]

    monkeypatch.setattr(netguard, "resolve_host", resolve)
    return records


@pytest.fixture
def fake_rdap(monkeypatch):
    """Replace RDAP with a dict: registrable domain -> age in days (default: 10 years)."""
    ages: dict[str, int | None] = {}

    async def fetch(domain: str) -> int | None:
        return ages.get(domain, 3650)

    monkeypatch.setattr(rdap, "fetch_age_days", fetch)
    return ages


@pytest.fixture
def no_sandbox(monkeypatch):
    """Record sandbox jobs instead of launching a browser."""
    started: list[str] = []

    def fake_run_job(job_id: str):
        started.append(job_id)  # recorded when scheduled, not when the task first runs
        return asyncio.sleep(0)

    monkeypatch.setattr(linkcheck, "_run_job", fake_run_job)
    return started
