import pytest

from server import message

pytestmark = pytest.mark.anyio


def codes(text):
    return {s.code for s in message.message_signals(text)}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("URGENT: your account will be suspended today", {"urgency"}),
        ("Please buy two Google Play cards and send me the numbers", {"gift_card"}),
        ("Read me the verification code we just sent you", {"otp_pin_request"}),
        ("This is the IRS. There is a warrant for your arrest", {"impersonation"}),
        ("Your payment failed, update your billing info", {"payment_pressure"}),
        ("Grandma, it's me. I need bail money, wire the money now", {"impersonation", "payment_pressure"}),
        ("See you at dinner on Sunday!", set()),
    ],
)
def test_rules(text, expected):
    assert expected <= codes(text)
    if not expected:
        assert codes(text) == set()


def test_extract_urls():
    text = "Go to https://paypa1.com/login, or www.example.org/x. Also amazon-refund.net/claim! Bye."
    assert message.extract_urls(text) == [
        "https://paypa1.com/login",
        "http://www.example.org/x",
        "http://amazon-refund.net/claim",
    ]


async def test_classic_scam_message(fake_dns, fake_rdap, no_sandbox):
    out = await message.check_message(
        "Amazon: your account is locked. Act now and pay the fee with a gift card. Call us immediately."
    )
    assert out["verdict"] == "Don't trust this message"
    assert out["links"] == []


async def test_risky_link_escalates_harmless_text(fake_dns, fake_rdap, no_sandbox):
    fake_dns["paypa1.com"] = ["93.184.215.14"]
    out = await message.check_message("hey, is this you? https://paypa1.com/photo")
    assert out["verdict"] == "Don't trust this message"
    assert out["links"][0]["quick_verdict"] == "Don't open this link"
    assert out["links"][0]["job_id"]
    assert len(no_sandbox) == 1


async def test_ordinary_message(fake_dns, fake_rdap, no_sandbox):
    out = await message.check_message("Running 10 minutes late, save me a seat")
    assert out == {"verdict": "No red flags found", "reasons": [], "links": []}
