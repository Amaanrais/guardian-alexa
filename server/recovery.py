"""start_incident / next_step: walk the person through a playbook, one calm step at a time."""

import logging
import secrets
import time

from . import config, family, playbooks
from .storage import get_store

log = logging.getLogger(__name__)
COLLECTION = "incidents"


class RecoveryError(Exception):
    """A plain-language problem to report back to the person."""


async def start_incident(description: str) -> dict:
    pb = playbooks.match(description)
    if pb is None:
        # Ask once rather than guess; nothing is stored and nobody is alerted yet.
        return {"incident_id": None, "playbook_title": None,
                "step": {"text": playbooks.CLARIFYING_QUESTION, "step_number": 0, "total_steps": 0}}
    incident_id = secrets.token_urlsafe(16)
    get_store().put(COLLECTION, incident_id, {
        "playbook_id": pb.id, "step_number": 1, "done": False,
        "description": description[:500], "started_at": time.time()})
    try:
        await family.alert_family(f"{config.PERSON_NAME} started recovery: {pb.family_summary}")
    except Exception:  # noqa: BLE001 - the steps matter more than the alert
        log.warning("couldn't alert the family about incident %s", incident_id)
    return {"incident_id": incident_id, "playbook_title": pb.title, "step": playbooks.step(pb, 1)}


async def next_step(incident_id: str) -> dict:
    store = get_store()
    record = store.get(COLLECTION, incident_id)
    if record is None:
        raise RecoveryError("I can't find that recovery. Let's start again: tell me what happened.")
    pb = playbooks.load_all().get(record["playbook_id"])
    if pb is None:
        raise RecoveryError("That recovery list isn't available any more. Let's start again.")
    summary = f'You finished all {len(pb.steps)} steps for "{pb.title}".'
    if record["done"]:
        return {"done": True, "summary": summary}
    number = record["step_number"] + 1
    if number > len(pb.steps):
        store.put(COLLECTION, incident_id, {**record, "done": True, "finished_at": time.time()})
        return {"done": True, "summary": summary}
    store.put(COLLECTION, incident_id, {**record, "step_number": number})
    return {"step": playbooks.step(pb, number)}
