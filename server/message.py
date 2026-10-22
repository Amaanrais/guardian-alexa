"""Rule-based red flags for a pasted message, plus check_link on every URL inside it."""

import asyncio
import re
from urllib.parse import urlsplit

from . import linkcheck, scoring
from .scoring import Signal

MAX_LINKS = 5

RULES: list[tuple[str, re.Pattern[str], str]] = [
    (
        "urgency",
        re.compile(
            r"\b(urgent|urgently|immediately|right away|act now|asap|within \d+ (hours?|minutes?|days?)|"
            r"today only|final (notice|warning)|last chance|expires? (today|soon)|"
            r"(account|card) (will be |has been |is )?(suspended|locked|closed|disabled|frozen))\b",
            re.I,
        ),
        "It pressures you to act quickly.",
    ),
    (
        "gift_card",
        re.compile(
            r"\b(gift ?cards?|itunes cards?|google play cards?|steam cards?|ebay cards?|vanilla (visa|cards?)|"
            r"scratch (off )?the (back|code)|numbers? on the back of the card)\b",
            re.I,
        ),
        "It asks for gift cards. Real companies and agencies never ask for payment in gift cards.",
    ),
    (
        "otp_pin_request",
        re.compile(
            r"\b(verification code|security code|one[- ]time (pass)?code|otp|pin( number)?|passcode|"
            r"(send|tell|give|read|share) (me|us)( back)? the code|code (we|that was|i) (just )?sent)\b",
            re.I,
        ),
        "It asks for a security code or PIN. Never share these with anyone.",
    ),
    (
        "impersonation",
        re.compile(
            r"\b(irs|social security( administration)?|medicare|amazon|paypal|apple support|microsoft support|"
            r"tech(nical)? support|your bank|bank of america|wells fargo|chase bank|fraud (department|team)|"
            r"police|sheriff|warrant|fbi|usps|fedex|dhl|customs|"
            r"(grandma|grandpa|nana|granny),? it'?s me)\b",
            re.I,
        ),
        "It claims to be from a company, agency or relative. Scammers often pretend to be someone you trust.",
    ),
    (
        "payment_pressure",
        re.compile(
            r"\b(wire (the )?(money|funds|transfer)|western union|moneygram|bitcoin|crypto(currency)?|zelle|venmo|"
            r"cash ?app|pay (now|immediately|a fee|the fee|a fine|the fine)|overdue (payment|balance|bill)|unpaid|"
            r"outstanding balance|refund|send (the )?money|processing fee|payment (failed|declined)|"
            r"update (your )?(payment|billing)|bail)\b",
            re.I,
        ),
        "It pushes you to send money or update payment details.",
    ),
]

_URL_RE = re.compile(
    r"(?:https?://[^\s<>\"'()]+)|(?:\bwww\.[^\s<>\"'()]+)|"
    r"(?:\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|info|biz|co|us|uk|io|me|ly|xyz|top|click|app|site|online|shop|live|support|help)\b(?:/[^\s<>\"'()]*)?)",
    re.I,
)


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for match in _URL_RE.finditer(text):
        url = match.group(0).rstrip(".,;:!?")
        if not re.match(r"https?://", url, re.I):
            url = "http://" + url
        if url not in urls:
            urls.append(url)
    return urls[:MAX_LINKS]


def message_signals(text: str) -> list[Signal]:
    return [Signal(code, reason) for code, pattern, reason in RULES if pattern.search(text)]


async def check_message(text: str) -> dict:
    signals = message_signals(text)
    urls = extract_urls(text)
    link_results = await asyncio.gather(*(linkcheck.check_link(u) for u in urls))
    reasons = scoring.reasons(signals)
    for url, result in zip(urls, link_results):
        if result["reasons"] and result["quick_verdict"] != "No red flags found":
            host = urlsplit(url).hostname or url
            reasons.append(f"The link to {host} has a warning sign: {result['reasons'][0]}")
    return {
        "verdict": scoring.message_verdict(signals, [r["level"] for r in link_results]),
        "reasons": reasons,
        "job_ids": [r["job_id"] for r in link_results],
    }
