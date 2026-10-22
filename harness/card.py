"""Turn a Guardian tool result into the card the harness renders.

CONTRACT.md was not available when this was written, so the parser accepts either a
ready-made `card` object or the flat fields named in the build brief (verdict, reasons,
screenshot_url) and degrades gracefully when fields are missing.
"""
import os
import re

TITLES = {
    "red": "Don't open this link",
    "amber": "Be careful",
    "grey": "No red flags found",
}
ICONS = {"red": "⛔", "amber": "⚠️", "grey": "ℹ️"}
LEVEL_WORDS = {
    "red": ("high", "red", "danger", "dangerous", "block", "denied", "scam"),
    "amber": ("medium", "amber", "yellow", "caution", "warn", "warning", "suspicious"),
    "grey": ("none", "low", "grey", "gray", "no red flags", "no_red_flags", "unknown"),
}
SAFE_RE = re.compile(r"\bsafe(ly|ty)?\b", re.I)
CARD_TOOLS = {"check_link", "get_link_report", "check_message", "get_verification",
              "start_incident", "next_step", "alert_family", "verify_caller"}


def _level(value) -> str | None:
    v = str(value or "").strip().lower().replace("\u2019", "'")
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
    return out[:3]


def build_card(tool: str, data: dict, prev: dict | None = None) -> dict | None:
    """Return a card dict, or None if this result should not change the card."""
    if not isinstance(data, dict) or tool not in CARD_TOOLS:
        return None
    base = data.get("card") if isinstance(data.get("card"), dict) else {}
    src = {**data, **base}

    level = (_level(src.get("level")) or _level(src.get("color")) or _level(src.get("verdict"))
             or _level(src.get("quick_verdict")))
    if tool == "get_verification":
        level = {"denied": "red", "confirmed": "grey"}.get(str(src.get("status")), "amber")
    if tool == "alert_family":
        return None
    if tool in ("start_incident", "next_step"):
        level = level or "amber"
    if level is None:
        return prev if tool == "check_link" and prev else None

    title = src.get("title")
    if tool == "get_verification":
        title = {"red": "Hang up", "grey": "It really is them"}.get(level, "No answer yet")
    if tool in ("start_incident", "next_step"):
        title = "All steps done" if src.get("done") else "Your next step"
        if src.get("done"):
            level, src = "grey", {**src, "reasons": ["You finished every step. Well done."]}
    if not title or SAFE_RE.search(str(title)):
        title = TITLES[level]

    reasons = _reasons(src.get("reasons"))
    if tool in ("start_incident", "next_step") and not reasons:
        step = src.get("step") or src.get("next_step") or src.get("text")
        if isinstance(step, dict):
            step = step.get("text") or step.get("title")
        reasons = _reasons([step]) if step else []

    # a quick verdict has no screenshot yet; keep the one from the earlier report if any
    shot = _shot_url(src.get("screenshot_path") or src.get("screenshot_url"))
    if not shot and tool in ("check_link", "get_link_report"):
        shot = (prev or {}).get("screenshot_url")

    if tool == "get_verification" and level == "red" and not reasons:
        reasons = ["The real person says it isn't them."]
    action = src.get("action") if isinstance(src.get("action"), dict) else None
    if action is None:
        if tool in ("start_incident", "next_step", "get_verification"):
            action = None
        elif level in ("red", "amber"):
            action = {"label": "Tell Rahul", "tool": "alert_family",
                      "args": {"reason": reasons[0] if reasons else title}}
    if action:
        action = {"label": _clean(action.get("label", "Tell Rahul")),
                  "tool": action.get("tool"), "args": action.get("args") or {}}

    kind = {"check_message": "message", "get_verification": "verify",
            "start_incident": "recovery", "next_step": "recovery"}.get(tool, "link")
    return {"level": level, "icon": ICONS[level], "kind": kind, "title": _clean(title), "reasons": reasons,
            "screenshot_url": shot, "action": action, "pending": tool == "check_link" or (tool == "get_link_report" and str(src.get("status")) not in ("done", "complete", "completed"))}
