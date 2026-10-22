"""Turns detected signals into a verdict. Weights and thresholds are fixed here and nowhere else.

Verdicts are deliberately never "safe": the best we can say is that we found no red flags.
"""

from dataclasses import dataclass
from typing import Literal

LinkVerdict = Literal["Don't open this link", "Be careful", "No red flags found"]
LINK_VERDICTS: tuple[LinkVerdict, LinkVerdict, LinkVerdict] = (
    "No red flags found",
    "Be careful",
    "Don't open this link",
)

CAREFUL_THRESHOLD = 25
DANGER_THRESHOLD = 60

WEIGHTS: dict[str, int] = {
    # Link: quick checks
    "lookalike_brand": 60,
    "brand_in_unofficial_domain": 45,
    "punycode": 25,
    "domain_very_new": 40,  # registered < 30 days ago
    "domain_new": 15,  # registered < 180 days ago
    "ip_literal_host": 30,
    "userinfo_in_url": 35,
    "not_https": 10,
    "url_shortener": 10,
    "risky_tld": 10,
    "dns_failed": 15,
    "private_address": 30,
    "invalid_url": 30,
    # Link: sandbox
    "password_field": 15,
    "otp_field": 30,
    "card_field": 20,  # every honest checkout has one; only adds weight to other signals
    "pin_field": 30,
    "cross_domain_redirect": 15,
    "brand_impersonation": 45,  # page names a brand it isn't, and asks for secrets
    "redirect_to_private": 40,
    "download_attempt": 30,
    "page_unreachable": 25,
    # Message rules
    "urgency": 15,
    "gift_card": 45,
    "otp_pin_request": 45,
    "impersonation": 20,
    "payment_pressure": 25,
}


@dataclass(frozen=True)
class Signal:
    code: str
    reason: str

    def __post_init__(self) -> None:
        if self.code not in WEIGHTS:
            raise ValueError(f"unknown signal code {self.code!r}")


def total(signals: list[Signal]) -> int:
    # A signal code counts once, however many times it fires.
    return sum(WEIGHTS[code] for code in {s.code for s in signals})


def level(signals: list[Signal]) -> int:
    score = total(signals)
    if score >= DANGER_THRESHOLD:
        return 2
    if score >= CAREFUL_THRESHOLD:
        return 1
    return 0


def reasons(signals: list[Signal]) -> list[str]:
    """Reasons ordered by weight, most serious first, de-duplicated."""
    seen: set[str] = set()
    out: list[str] = []
    for s in sorted(signals, key=lambda s: -WEIGHTS[s.code]):
        if s.reason not in seen:
            seen.add(s.reason)
            out.append(s.reason)
    return out


def link_verdict(signals: list[Signal]) -> LinkVerdict:
    return LINK_VERDICTS[level(signals)]


def message_verdict(message_signals: list[Signal], link_levels: list[int]) -> LinkVerdict:
    """Messages share the link verdicts (docs/CONTRACT.md); the worst of text and links wins."""
    return LINK_VERDICTS[max([level(message_signals), *link_levels])]
