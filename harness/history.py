"""Recent verdicts for the home screen, kept in harness/.data/history.json (git-ignored)."""
import json
import time
from pathlib import Path

PATH = Path(__file__).parent / ".data" / "history.json"
MAX_ENTRIES = 50
WEEK_S = 7 * 24 * 3600


def _load() -> list[dict]:
    try:
        return json.loads(PATH.read_text())
    except (OSError, ValueError):
        return []


def record(card: dict) -> None:
    """Store a finished link or message verdict."""
    entry = {"kind": card["kind"], "level": card["level"], "title": card["title"],
             "label": card.get("domain") or ("A message" if card["kind"] == "message" else "A link"),
             "at": time.time()}
    entries = _load()
    last = entries[-1] if entries else None
    # the same verdict twice within a minute is one check reported twice (e.g. a re-polled report)
    if last and all(last[k] == entry[k] for k in ("kind", "level", "label")) and entry["at"] - last["at"] < 60:
        return
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps((entries + [entry])[-MAX_ENTRIES:]))


def summary() -> dict:
    entries = _load()
    now = time.time()
    return {"checks_this_week": sum(1 for e in entries if now - e["at"] < WEEK_S),
            "recent": list(reversed(entries[-3:]))}
