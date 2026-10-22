"""URL heuristics that need no network: punycode, brand look-alikes, and other cheap tells."""

import ipaddress
import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import config
from .netguard import ParsedURL
from .scoring import Signal

@dataclass(frozen=True)
class Brand:
    name: str  # as people write it: "Wells Fargo"
    domains: tuple[str, ...]  # official domains, main one first
    aliases: tuple[str, ...] = ()  # other names it goes by: "Amex"
    payment: bool = False  # payment network or wallet, routinely shown on other sites' checkouts
    match_in_domains: bool = True  # False for common words ("visa") that appear in unrelated domains

    @property
    def names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)

    @property
    def keys(self) -> tuple[str, ...]:
        """Names as they'd appear in a domain: "Wells Fargo" -> "wellsfargo"."""
        return tuple(re.sub(r"[^a-z0-9]", "", n.lower()) for n in self.names)


def load_brands(path: Path) -> list[Brand]:
    """brands.json maps a brand's display name to its official domains, or to an object with
    "domains" and optionally "aliases", "payment" and "match_in_domains"."""
    brands = []
    for name, spec in json.loads(path.read_text()).items():
        if isinstance(spec, list):
            spec = {"domains": spec}
        brands.append(Brand(
            name=name,
            domains=tuple(d.lower() for d in spec["domains"]),
            aliases=tuple(spec.get("aliases", ())),
            payment=bool(spec.get("payment", False)),
            match_in_domains=bool(spec.get("match_in_domains", True)),
        ))
    return brands


BRANDS: list[Brand] = load_brands(config.BRANDS_FILE)

SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "ow.ly", "is.gd", "buff.ly", "rebrand.ly",
    "cutt.ly", "shorturl.at", "tiny.cc", "rb.gy", "t.ly",
}
RISKY_TLDS = {"zip", "mov", "top", "xyz", "click", "tk", "ml", "ga", "cf", "gq", "icu", "cam", "rest", "country"}
_TWO_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.nz", "co.in",
    "co.jp", "com.br", "com.mx", "co.za", "com.sg", "com.cn", "com.tr",
}

# Common Unicode look-alikes and ASCII substitutions, mapped to the letter they imitate.
_CONFUSABLES = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j",
    "ӏ": "l", "ԁ": "d", "ɡ": "g", "ո": "n", "ս": "u", "ν": "v", "ο": "o", "α": "a", "ε": "e",
    "ı": "i", "ł": "l", "à": "a", "á": "a", "â": "a", "ä": "a", "é": "e", "è": "e", "ê": "e",
    "í": "i", "ì": "i", "ó": "o", "ò": "o", "ô": "o", "ö": "o", "ú": "u", "ü": "u", "ç": "c",
    "0": "o", "1": "l", "3": "e", "5": "s", "@": "a",
})


def registrable_domain(host: str) -> str:
    labels = host.split(".")
    n = 3 if ".".join(labels[-2:]) in _TWO_LEVEL_SUFFIXES else 2
    return ".".join(labels[-n:])


def skeleton(text: str) -> str:
    s = text.lower().translate(_CONFUSABLES)
    return s.replace("rn", "m").replace("vv", "w")


def _within_one_edit(a: str, b: str) -> bool:
    """True if a and b differ by one substitution, insertion, deletion or adjacent swap."""
    if a == b or abs(len(a) - len(b)) > 1:
        return a == b
    if len(a) == len(b):
        diffs = [i for i in range(len(a)) if a[i] != b[i]]
        if len(diffs) == 1:
            return True
        return len(diffs) == 2 and diffs[1] == diffs[0] + 1 and a[diffs[0]] == b[diffs[1]] and a[diffs[1]] == b[diffs[0]]
    short, long_ = sorted((a, b), key=len)
    return any(long_[:i] + long_[i + 1:] == short for i in range(len(long_)))


def _is_official(host: str, domains: tuple[str, ...]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _is_official_anywhere(host: str) -> bool:
    return any(_is_official(host, b.domains) for b in BRANDS)


def brand_signals(display_host: str) -> list[Signal]:
    """Look-alike and brand-misuse checks on a Unicode hostname."""
    if _is_official_anywhere(display_host):
        return []
    signals: list[Signal] = []
    reg = registrable_domain(display_host)
    name = reg.split(".")[0]
    tokens = [t for t in re.split(r"[.\-_]", display_host) if t]

    for brand in BRANDS:
        pretty = brand.domains[0]
        # Look-alike: the domain's own name imitates the brand.
        candidates = {name, *name.split("-")}
        if any(c != key and (skeleton(c) == key or (len(key) >= 5 and len(c) >= 5 and _within_one_edit(skeleton(c), key)))
               for c in candidates for key in brand.keys):
            signals.append(Signal("lookalike_brand", f"The web address imitates {pretty} but isn't the real site."))
            continue
        # Brand name used somewhere in an unrelated domain (paypal-login.com, amazon.verify.net).
        if brand.match_in_domains and any(
            key in tokens or (len(key) >= 6 and key in display_host.replace("-", "")) for key in brand.keys
        ):
            signals.append(
                Signal("brand_in_unofficial_domain", f"The address mentions {brand.name} but doesn't belong to {pretty}.")
            )
    return signals


def claimed_brands(identity_text: str, host: str) -> list[Brand]:
    """Brands the page presents itself as, when it isn't on their official domain.

    `identity_text` should hold only where a site names itself (title, h1/h2, logo alt text,
    og:site_name), never body copy, where shops routinely mention "Pay with PayPal". Names must
    match as written or in capitals, which keeps most ordinary words out ("apple", "chase").
    Longer names are matched first and consumed, so "Apple Pay" doesn't also count as Apple.
    """
    by_length = sorted(((n, b) for b in BRANDS for n in b.names), key=lambda nb: -len(nb[0]))
    claimed: list[Brand] = []
    for name, brand in by_length:
        pattern = rf"(?<![A-Za-z0-9])(?:{re.escape(name)}|{re.escape(name.upper())})(?![A-Za-z0-9])"
        identity_text, hits = re.subn(pattern, " ", identity_text)
        if hits and brand not in claimed and not _is_official(host, brand.domains):
            claimed.append(brand)
    return claimed


def url_signals(parsed: ParsedURL) -> list[Signal]:
    signals: list[Signal] = []
    host = parsed.host
    is_ip = True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        is_ip = False

    if is_ip:
        signals.append(Signal("ip_literal_host", "The link uses a bare number address instead of a website name."))
    else:
        if any(label.startswith("xn--") for label in host.split(".")) or parsed.display_host != host:
            signals.append(
                Signal("punycode", f"The address uses letters from another alphabet that can imitate a real site ({parsed.display_host}).")
            )
        signals.extend(brand_signals(parsed.display_host))
        if registrable_domain(host) in SHORTENERS:
            signals.append(Signal("url_shortener", "The link is shortened, which hides where it really goes."))
        if host.rsplit(".", 1)[-1] in RISKY_TLDS:
            signals.append(Signal("risky_tld", "The address ends in a domain type often used by scams."))
    if parsed.has_userinfo:
        signals.append(Signal("userinfo_in_url", "The link hides its real destination after an @ sign."))
    if parsed.scheme == "http":
        signals.append(Signal("not_https", "The link isn't using a secure connection."))
    return signals
