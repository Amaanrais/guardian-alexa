"""SSRF guard: schemes, address classes, DNS tricks and redirect hops."""

import httpx
import pytest

from server import linkcheck
from server.netguard import (
    BlockedURLError,
    guarded_fetch,
    guarded_fetch_following,
    is_blocked_ip,
    parse_url,
    resolve_host,
    resolve_public,
)

pytestmark = pytest.mark.anyio

BLOCKED_IPS = [
    "127.0.0.1",
    "127.1.2.3",
    "169.254.169.254",  # cloud metadata
    "10.0.0.1",
    "10.255.255.254",
    "172.16.0.1",
    "192.168.1.1",
    "100.64.0.1",  # carrier-grade NAT
    "0.0.0.0",
    "224.0.0.1",
    "255.255.255.255",
    "::1",
    "::",
    "fe80::1",
    "fc00::1",
    "::ffff:127.0.0.1",  # IPv4-mapped
    "::ffff:169.254.169.254",
    "64:ff9b::a9fe:a9fe",  # NAT64 of 169.254.169.254
    "2002:7f00:1::",  # 6to4 of 127.0.0.1
]
PUBLIC_IPS = ["93.184.215.14", "8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"]


@pytest.mark.parametrize("ip", BLOCKED_IPS)
def test_blocks_non_public_ips(ip):
    assert is_blocked_ip(ip)


@pytest.mark.parametrize("ip", PUBLIC_IPS)
def test_allows_public_ips(ip):
    assert not is_blocked_ip(ip)


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://example.com/", "gopher://example.com/", "javascript:alert(1)",
     "data:text/html,hi", "http://", "example.com", "http://:80/"],
)
def test_rejects_non_http_urls(url):
    with pytest.raises(BlockedURLError) as exc:
        parse_url(url)
    assert exc.value.code == "invalid_url"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://10.1.2.3:8080/",
        "http://[::1]/",
        "http://localhost/",
        "http://2130706433/",  # decimal form of 127.0.0.1
        "http://0x7f.0.0.1/",  # hex form
        "http://127.0.0.1.nip.io/",  # public DNS name that resolves to loopback
    ],
)
async def test_real_resolver_blocks_private_targets(url):
    parsed = parse_url(url)
    try:
        await resolve_host(parsed.host, parsed.port)
    except OSError:
        pytest.skip("resolver can't resolve this name here")
    with pytest.raises(BlockedURLError) as exc:
        await resolve_public(parsed)
    assert exc.value.code == "private_address"


async def test_mixed_public_and_private_records_are_blocked(fake_dns):
    fake_dns["rebind.test"] = ["93.184.215.14", "10.0.0.7"]
    with pytest.raises(BlockedURLError):
        await resolve_public(parse_url("http://rebind.test/"))


async def test_fetch_never_connects_to_blocked_host(fake_dns):
    calls = []
    transport = httpx.MockTransport(lambda req: calls.append(req) or httpx.Response(200))
    fake_dns["internal.test"] = ["192.168.0.10"]
    async with httpx.AsyncClient(transport=transport) as client:
        for url in ["http://127.0.0.1/", "http://169.254.169.254/", "http://10.0.0.1/", "http://internal.test/"]:
            with pytest.raises(BlockedURLError):
                await guarded_fetch(client, url)
    assert calls == []


async def test_fetch_is_pinned_to_vetted_ip(fake_dns):
    seen = []
    fake_dns["shop.test"] = ["93.184.215.14"]
    transport = httpx.MockTransport(lambda req: seen.append(req) or httpx.Response(200, text="ok"))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await guarded_fetch(client, "http://shop.test/a?b=1")
    assert result.status == 200
    assert seen[0].url.host == "93.184.215.14"
    assert seen[0].url.raw_path == b"/a?b=1"
    assert seen[0].headers["host"] == "shop.test"


@pytest.mark.parametrize(
    "location", ["http://10.0.0.5/admin", "http://169.254.169.254/latest/meta-data/", "http://127.0.0.1:6379/", "http://intranet.test/"]
)
async def test_redirect_to_private_ip_is_blocked(fake_dns, location):
    fake_dns["start.test"] = ["93.184.215.14"]
    fake_dns["intranet.test"] = ["10.0.0.5"]
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req.headers["host"])
        return httpx.Response(302, headers={"Location": location})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BlockedURLError) as exc:
            await guarded_fetch_following(client, "http://start.test/")
    assert exc.value.code == "private_address"
    assert calls == ["start.test"]  # the private hop was never requested


async def test_redirect_loop_is_capped(fake_dns):
    fake_dns["loop.test"] = ["93.184.215.14"]
    transport = httpx.MockTransport(lambda req: httpx.Response(302, headers={"Location": "/again"}))
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(BlockedURLError):
            await guarded_fetch_following(client, "http://loop.test/")


@pytest.mark.parametrize("url", ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/", "http://10.0.0.8/"])
async def test_check_link_refuses_private_targets_without_sandbox(url, fake_dns, fake_rdap, no_sandbox):
    out = await linkcheck.check_link(url)
    assert out["quick_verdict"] != "No red flags found"
    assert any("private" in r for r in out["reasons"])
    assert no_sandbox == []
    assert linkcheck.get_link_report(out["job_id"])["status"] == "blocked"
