"""Turn a Guardian tool result (docs/CONTRACT.md shapes) into the card the harness renders.

Card kinds and what the front end (static/cards.js) expects:
  link / message  {level: red|amber|grey, title, reasons[<=3], injection, domain, screenshot_url, pending, action}
  verify          {verify: {id, name, pronoun, status: waiting|confirmed|denied|no_reply, started_at}}
  recovery        {recovery: {incident_id, index, total, text, done, family_told}, action}
Fields the contract doesn't define yet (final_domain, a step's number and total) are used
when the server sends them and otherwise worked out here.
"""
import os
import re
import time
from urllib.parse import urlsplit

TITLES = {
    "red": "Don't open this link",
    "amber": "Be careful",
    "grey": "No red flags found",
}
LEVEL_WORDS = {
    "red": ("high", "red", "danger", "dangerous", "block", "scam"),
    "amber": ("medium", "amber", "yellow", "caution", "warn", "warning", "suspicious"),
    "grey": ("none", "low", "grey", "gray", "no red flags", "no_red_flags", "unknown"),
}
SAFE_RE = re.compile(r"\bsafe(ly|ty)?\b", re.I)
# A reason saying the page carried instructions meant for the AI rather than the person.
INJECTION_RE = re.compile(
    r"hidden (text|instructions?|prompts?|commands?)|prompt injection|"
    r"instructions? (aimed at|meant for|for|to) (the |an )?(ai|assistant|chatbot|guardian)|"
    r"(trick|fool|manipulate) (the |an )?(ai|assistant|chatbot)",
    re.I,
)
# The demo family contact, with the pronoun they use. Unknown names get "them".
FAMILY = "Rahul"
PRONOUNS = {"Rahul": "him"}
VERIFY_STATUSES = ("confirmed", "denied", "no_reply")


def _level(value) -> str | None:
    v = str(value or "").strip().lower().replace("’", "'")
    if v == "don't open this link":
        return "red"
    if v == "be careful":
        return "amber"
    if v == "no red flags found":
        return "grey"
    for level, words in LEVEL_WORDS.items():
        if v in words:
            return level
    return None


def _shot_url(path: str | None) -> str | None:
    """screenshot_path may be a full URL (presigned S3) or a path relative to the server."""
    if not path:
        return None
    if re.match(r"https?://", path):
        return path
    base = os.getenv("SCREENSHOT_BASE_URL") or re.sub(r"/mcp/?$", "", os.getenv("MCP_URL", "http://localhost:8765/mcp"))
    return base.rstrip("/") + "/" + path.lstrip("/")


def _clean(text: str) -> str:
    """The card must never claim a page is safe."""
    return SAFE_RE.sub("okay", str(text)).strip()


def _reasons(raw) -> list[str]:
    out = []
    for r in raw or []:
        if isinstance(r, dict):
            r = r.get("text") or r.get("reason") or r.get("message") or ""
        if r:
            out.append(_clean(r))
    return out


def _host(url) -> str | None:
    if not url:
        return None
    url = str(url)
    try:
        return urlsplit(url if re.match(r"https?://", url, re.I) else "http://" + url).hostname
    except ValueError:
        return None


def tell_family(reason: str) -> dict:
    return {"label": f"Tell {FAMILY}", "tool": "alert_family", "args": {"reason": reason}}


def start_recovery(description: str) -> dict:
    return {"label": "Start recovery", "tool": "start_incident", "args": {"description": description}}


def build_card(tool: str, data: dict, prev: dict | None = None, args: dict | None = None) -> dict | None:
    """Return a card dict, or None if this result should not change the card."""
    if not isinstance(data, dict) or "error" in data:
        return None
    src = {**data, **data["card"]} if isinstance(data.get("card"), dict) else data
    prev, args = prev or {}, args or {}
    if tool in ("check_link", "get_link_report", "check_message"):
        return _verdict_card(tool, src, prev, args)
    if tool in ("verify_caller", "get_verification"):
        return _verify_card(tool, src, prev, args)
    if tool in ("start_incident", "next_step"):
        return _recovery_card(tool, src, prev, args)
    return None


def _verdict_card(tool: str, src: dict, prev: dict, args: dict) -> dict | None:
    level = _level(src.get("verdict")) or _level(src.get("quick_verdict")) or _level(src.get("level"))
    if level is None:
        return None
    kind = "message" if tool == "check_message" else "link"
    same_link = prev.get("kind") == "link" and tool == "get_link_report"
    reasons = _reasons(src.get("reasons"))
    domain = (src.get("final_domain") or _host(src.get("final_url"))
              or (_host(args.get("url")) if tool == "check_link" else None)
              or (prev.get("domain") if same_link else None))
    shot = _shot_url(src.get("screenshot_path") or src.get("screenshot_url"))
    status = str(src.get("status") or "")
    title = TITLES[level]
    # The purple banner states the AI-trick reason, so the list keeps the other ones.
    injection = [r for r in reasons if INJECTION_RE.search(r)]
    shown = [r for r in reasons if r not in injection]
    return {
        "kind": kind,
        "level": level,
        "title": title,
        "reasons": shown[:3],
        "injection": bool(injection),
        "domain": domain if kind == "link" else None,
        "screenshot_url": shot or (prev.get("screenshot_url") if same_link else None),
        "pending": tool == "check_link" or (tool == "get_link_report" and status in ("pending", "running")),
        "action": tell_family(f"{title}: {reasons[0]}" if reasons else title) if level != "grey" else None,
    }


def _verify_card(tool: str, src: dict, prev: dict, args: dict) -> dict | None:
    before = prev.get("verify") if prev.get("kind") == "verify" else {}
    if tool == "verify_caller":
        if not src.get("verification_id"):
            return None
        name = str(args.get("name") or FAMILY)
        before = {"id": src["verification_id"], "name": name, "started_at": int(time.time() * 1000)}
    status = str(src.get("status") or "waiting")
    name = before.get("name") or FAMILY
    return {
        "kind": "verify",
        "verify": {
            "id": before.get("id") or args.get("id"),
            "name": name,
            "pronoun": PRONOUNS.get(name, "them"),
            "status": status if status in VERIFY_STATUSES else "waiting",
            "started_at": before.get("started_at") or int(time.time() * 1000),
        },
    }


def _recovery_card(tool: str, src: dict, prev: dict, args: dict) -> dict | None:
    before = prev.get("recovery") if prev.get("kind") == "recovery" else {}
    if tool == "start_incident":
        before = {}
    incident = src.get("incident_id") or before.get("incident_id") or args.get("incident_id")
    if src.get("done"):
        total = before.get("total") or before.get("index")
        return {"kind": "recovery", "recovery": {
            "incident_id": incident, "done": True, "index": total, "total": total, "family_told": False}}

    step = src.get("step") or src.get("next_step") or src.get("text")
    index = src.get("step_number") or src.get("index")
    total = src.get("total_steps") or src.get("total")
    if isinstance(step, dict):
        index = index or step.get("number") or step.get("index")
        total = total or step.get("total")
        step = step.get("text") or step.get("title")
    if not step:
        return None
    index = int(index) if index else (1 if tool == "start_incident" else (before.get("index") or 0) + 1)
    total = int(total) if total else before.get("total")
    return {"kind": "recovery", "recovery": {
        "incident_id": incident, "index": index, "total": total, "text": _clean(step), "done": False}}


def speech(card: dict | None) -> str:
    """What Guardian says when a card arrives without a reply of its own (button presses, polling)."""
    if not card:
        return ""
    if card.get("kind") == "verify":
        v = card["verify"]
        name, obj = v["name"], v["pronoun"]
        return {
            "confirmed": f"{name} confirmed it's {obj}. Even so, never share a code or PIN.",
            "denied": f"{name} says it isn't {obj}. Hang up now.",
            "no_reply": f"{name} didn't answer. Don't send money. Call {obj} back on the number you usually use.",
        }.get(v["status"], "")
    if card.get("kind") == "recovery":
        r = card["recovery"]
        if r.get("done"):
            told = " Your family has been told." if r.get("family_told") else ""
            return "You've done everything on the list." + told
        return r.get("text") or ""
    return ""
