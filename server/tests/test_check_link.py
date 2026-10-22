import re
import time

import pytest

from server import linkcheck, rdap

pytestmark = pytest.mark.anyio


async def test_lookalike_domain(fake_dns, fake_rdap, no_sandbox):
    fake_dns["paypa1-login.com"] = ["93.184.215.14"]
    out = await linkcheck.check_link("https://paypa1-login.com/signin")
    assert out["quick_verdict"] == "Don't open this link"
    assert any("imitates paypal.com" in r for r in out["reasons"])
    assert len(no_sandbox) == 1


async def test_punycode_homograph(fake_dns, fake_rdap, no_sandbox):
    fake_dns["xn--pypal-4ve.com"] = ["93.184.215.14"]  # pаypal.com with Cyrillic "а"
    out = await linkcheck.check_link("https://xn--pypal-4ve.com/")
    assert out["quick_verdict"] == "Don't open this link"
    assert any("another alphabet" in r for r in out["reasons"])


async def test_brand_in_unofficial_new_domain(fake_dns, fake_rdap, no_sandbox):
    fake_dns["amazon-refunds.net"] = ["93.184.215.14"]
    fake_rdap["amazon-refunds.net"] = 3
    out = await linkcheck.check_link("https://amazon-refunds.net/claim")
    assert out["quick_verdict"] == "Don't open this link"
    assert any("3 days ago" in r for r in out["reasons"])


async def test_official_domain_has_no_red_flags(fake_dns, fake_rdap, no_sandbox):
    fake_dns["www.paypal.com"] = ["93.184.215.14"]
    out = await linkcheck.check_link("https://www.paypal.com/signin")
    assert out["quick_verdict"] == "No red flags found"
    assert out["reasons"] == []
    assert len(no_sandbox) == 1


async def test_unrelated_words_are_not_brands(fake_dns, fake_rdap, no_sandbox):
    fake_dns["purchase-groups.org"] = ["93.184.215.14"]
    out = await linkcheck.check_link("https://purchase-groups.org/")
    assert out["quick_verdict"] == "No red flags found"


async def test_userinfo_trick(fake_dns, fake_rdap, no_sandbox):
    fake_dns["evil.test"] = ["93.184.215.14"]
    out = await linkcheck.check_link("http://paypal.com@evil.test/")
    assert out["quick_verdict"] != "No red flags found"


async def test_quick_check_stays_under_500ms_when_dns_and_rdap_hang(monkeypatch, no_sandbox):
    import asyncio

    from server import netguard

    async def hang(*_args):
        await asyncio.sleep(10)

    monkeypatch.setattr(netguard, "resolve_host", hang)
    monkeypatch.setattr(rdap, "fetch_age_days", hang)
    start = time.perf_counter()
    out = await linkcheck.check_link("https://slow-site.example/")
    assert time.perf_counter() - start < 0.5
    assert out["job_id"]


async def test_rdap_is_cached(monkeypatch):
    calls = []

    async def fetch(domain):
        calls.append(domain)
        return 12

    monkeypatch.setattr(rdap, "fetch_age_days", fetch)
    assert await rdap.domain_age_days("example.test") == 12
    assert await rdap.domain_age_days("example.test") == 12
    assert calls == ["example.test"]


def test_rdap_registration_age_parsing():
    assert rdap._registration_age_days({"events": [{"eventAction": "registration", "eventDate": "2000-01-01T00:00:00Z"}]}) > 9000
    assert rdap._registration_age_days({"events": [{"eventAction": "expiration", "eventDate": "2030-01-01T00:00:00Z"}]}) is None


async def test_report_while_pending_and_unknown(fake_dns, fake_rdap, no_sandbox):
    fake_dns["shop.test"] = ["93.184.215.14"]
    out = await linkcheck.check_link("https://shop.test/")
    report = linkcheck.get_link_report(out["job_id"])
    assert report["status"] == "pending"
    assert report["screenshot_path"] is None
    assert linkcheck.get_link_report("nope")["status"] == "error"


async def test_never_says_safe(fake_dns, fake_rdap, no_sandbox):
    fake_dns["paypa1.com"] = ["93.184.215.14"]
    fake_dns["example.org"] = ["93.184.215.14"]
    outputs = [
        await linkcheck.check_link(u)
        for u in ["https://paypa1.com", "https://example.org", "http://127.0.0.1", "ftp://x", "http://unknown.test"]
    ]
    outputs += [linkcheck.get_link_report(o["job_id"]) for o in outputs] + [linkcheck.get_link_report("missing")]
    for o in outputs:
        text = " ".join([o.get("quick_verdict") or o.get("verdict"), *o["reasons"]])
        assert not re.search(r"\bsafe\b", text, re.I), text


def test_brands_load_from_json():
    from server.lookalike import BRANDS, brand_signals

    nordbank = next(b for b in BRANDS if b.name == "NordBank")
    assert nordbank.domains == ("nordbank.example",)
    assert [s.code for s in brand_signals("n0rdbank.com")] == ["lookalike_brand"]
    assert [s.code for s in brand_signals("nordbank-verify.net")] == ["brand_in_unofficial_domain"]
    assert brand_signals("online.nordbank.example") == []


def test_claimed_brands_prefers_longer_names_and_aliases():
    from server.lookalike import claimed_brands

    names = lambda text, host="shop.test": [b.name for b in claimed_brands(text, host)]  # noqa: E731
    assert names("Checkout | Apple Pay") == ["Apple Pay"]  # not also "Apple"
    assert names("AMEX rewards") == ["American Express"]
    assert names("PayPal", "www.paypal.com") == []
    assert names("apple pie recipes") == []


def test_payment_brand_flags_and_common_word_domains():
    from server.lookalike import BRANDS, brand_signals

    payment = {b.name for b in BRANDS if b.payment}
    assert {"PayPal", "Visa", "Mastercard", "American Express", "Apple Pay", "Google Pay", "Klarna"} <= payment
    assert brand_signals("uk-visa-help.com") == []  # "visa" is an ordinary word in domains
    assert [s.code for s in brand_signals("amex-verify.com")] == ["brand_in_unofficial_domain"]


async def test_job_ids_are_128_bit_random_tokens(fake_dns, fake_rdap, no_sandbox, monkeypatch):
    import base64
    import secrets

    calls = []
    real = secrets.token_urlsafe
    monkeypatch.setattr(secrets, "token_urlsafe", lambda n: calls.append(n) or real(n))
    fake_dns["shop.test"] = ["93.184.215.14"]
    ids = {(await linkcheck.check_link("https://shop.test/"))["job_id"] for _ in range(50)}
    assert calls and all(n >= 16 for n in calls)  # secrets module, >= 128 bits
    assert len(ids) == 50
    for job_id in ids:
        assert len(base64.urlsafe_b64decode(job_id + "==")) >= 16
