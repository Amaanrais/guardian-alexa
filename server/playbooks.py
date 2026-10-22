"""Recovery playbooks: playbooks/<id>.json, picked by keyword scoring against what the person said."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import config

CLARIFYING_QUESTION = "Did you share a code, or click a link?"
_WORD = re.compile(r"[a-z0-9']+")
_STOP = {"a", "an", "the", "my", "i", "to", "on", "in", "of", "and", "or", "it", "someone", "them", "me"}
# A step may tell people to protect a secret ("never share your PIN"), but Guardian must never
# ask for one. These catch asking: "tell me your PIN", "what is your code", "type your password here".
_ASKS_FOR_SECRET = re.compile(
    r"\b(tell|give|send|read|say|share)\s+(me|us|guardian)\b.*\b(password|passcode|code|otp|pin|card)|"
    r"\bwhat(?:'s| is)\s+your\s+(password|passcode|code|otp|pin|card)|"
    r"\b(type|enter|say)\s+(your\s+)?(password|passcode|code|otp|pin|card number)\s+(here|now|to me|to guardian)",
    re.I,
)


class PlaybookError(ValueError):
    pass


@dataclass(frozen=True)
class Playbook:
    id: str
    title: str
    family_summary: str
    match_phrases: tuple[str, ...]
    steps: tuple[dict, ...] = field(default=())


def _validate(data: dict, source: Path) -> Playbook:
    for key in ("id", "title", "match_phrases", "steps"):
        if key not in data:
            raise PlaybookError(f"{source.name}: missing {key!r}")
    if data["id"] != source.stem:
        raise PlaybookError(f"{source.name}: id must match the file name")
    steps = []
    for i, step in enumerate(data["steps"], 1):
        text = str(step.get("text") or "").strip()
        if not text:
            raise PlaybookError(f"{source.name}: step {i} has no text")
        if _ASKS_FOR_SECRET.search(text):
            raise PlaybookError(f"{source.name}: step {i} asks for a secret, which Guardian never does")
        action = step.get("action")
        if action is not None and not (isinstance(action, dict) and action.get("label") and action.get("tool")):
            raise PlaybookError(f"{source.name}: step {i} has an action without label and tool")
        steps.append({"text": text, **({"action": {"label": action["label"], "tool": action["tool"],
                                                    "args": action.get("args") or {}}} if action else {})})
    if not steps:
        raise PlaybookError(f"{source.name}: no steps")
    return Playbook(id=data["id"], title=data["title"], family_summary=data.get("family_summary") or data["title"],
                    match_phrases=tuple(p.lower() for p in data["match_phrases"]), steps=tuple(steps))


def load_all(directory: Path | None = None) -> dict[str, Playbook]:
    """Every playbook, read fresh so edits to the JSON files apply without a restart."""
    directory = Path(directory or config.PLAYBOOKS_DIR)
    return {p.stem: _validate(json.loads(p.read_text()), p) for p in sorted(directory.glob("*.json"))}


def score(playbook: Playbook, description: str) -> int:
    text = description.lower()
    words = set(_WORD.findall(text))
    total = 0
    for phrase in playbook.match_phrases:
        if re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text):
            total += 3  # the whole phrase
        total += sum(1 for w in _WORD.findall(phrase) if w not in _STOP and w in words)
    return total


def match(description: str, playbooks: dict[str, Playbook] | None = None) -> Playbook | None:
    """The best-scoring playbook, or None if nothing matches at all. Ties go to the first id."""
    playbooks = load_all() if playbooks is None else playbooks
    best = max(playbooks.values(), key=lambda pb: (score(pb, description), -sorted(playbooks).index(pb.id)), default=None)
    return best if best and score(best, description) > 0 else None


def step(playbook: Playbook, number: int) -> dict:
    """Step `number` (1-based) in the contract's shape."""
    return {**playbook.steps[number - 1], "step_number": number, "total_steps": len(playbook.steps)}
