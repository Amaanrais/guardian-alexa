import json

import pytest

from server import config, playbooks, recovery, storage

pytestmark = pytest.mark.anyio


@pytest.fixture
def alerts(monkeypatch):
    sent = []

    async def fake_alert(reason):
        sent.append(reason)
        return {"sent": True, "recipients": ["Rahul"]}

    monkeypatch.setattr(recovery.family, "alert_family", fake_alert)
    return sent


@pytest.mark.parametrize("description,expected", [
    ("I gave someone my bank code", "shared_code"),
    ("They asked for my OTP and I read it out", "shared_code"),
    ("i told them my PIN", "shared_code"),
    ("I clicked a link and typed my password", "clicked_link"),
    ("I CLICKED THE LINK in the text", "clicked_link"),
    ("I signed in on a page from an email", "clicked_link"),
])
def test_playbook_matching(description, expected):
    assert playbooks.match(description).id == expected


def test_nothing_matches():
    assert playbooks.match("someone rang me about my parcel") is None


def test_shipped_playbooks_are_valid_and_never_ask_for_secrets():
    pbs = playbooks.load_all()
    assert set(pbs) >= {"shared_code", "clicked_link"}
    for pb in pbs.values():
        assert len(pb.steps) >= 3
        for s in pb.steps:
            assert not playbooks._ASKS_FOR_SECRET.search(s["text"])


@pytest.mark.parametrize("text", [
    "Tell me your PIN so I can check it.",
    "What is your password?",
    "Please read me the code from the text.",
    "Type your card number here.",
])
def test_playbook_asking_for_a_secret_is_refused(tmp_path, text):
    (tmp_path / "bad.json").write_text(json.dumps(
        {"id": "bad", "title": "Bad", "match_phrases": ["x"], "steps": [{"text": text}]}))
    with pytest.raises(playbooks.PlaybookError, match="asks for a secret"):
        playbooks.load_all(tmp_path)


def test_protective_advice_is_allowed(tmp_path):
    (tmp_path / "ok.json").write_text(json.dumps({"id": "ok", "title": "Ok", "match_phrases": ["x"], "steps": [
        {"text": "Never share your PIN with anyone."}, {"text": "Change your password in the app you normally use."}]}))
    assert len(playbooks.load_all(tmp_path)["ok"].steps) == 2


async def test_start_progress_and_done(alerts):
    out = await recovery.start_incident("I gave someone my code")
    assert out["playbook_title"] == "I gave someone my code / OTP / PIN"
    assert out["step"]["step_number"] == 1 and out["step"]["total_steps"] == 3
    assert alerts == [f"{config.PERSON_NAME} started recovery: shared a code"]

    iid = out["incident_id"]
    assert (await recovery.next_step(iid))["step"]["step_number"] == 2
    assert (await recovery.next_step(iid))["step"]["step_number"] == 3
    done = await recovery.next_step(iid)
    assert done["done"] is True and "3 steps" in done["summary"]
    assert await recovery.next_step(iid) == done  # stays done
    # progress lives behind the storage interface
    assert storage.get_store().get("incidents", iid)["done"] is True


async def test_step_action_is_passed_through(alerts):
    iid = (await recovery.start_incident("I clicked a link"))["incident_id"]
    await recovery.next_step(iid)
    step = (await recovery.next_step(iid))["step"]
    assert step["action"]["tool"] == "alert_family"


async def test_clarifying_question_when_nothing_matches(alerts):
    out = await recovery.start_incident("something bad happened")
    assert out == {"incident_id": None, "playbook_title": None,
                   "step": {"text": "Did you share a code, or click a link?", "step_number": 0, "total_steps": 0}}
    assert alerts == []  # nobody is alerted until a playbook is chosen
    assert storage.get_store().all("incidents") == {}


async def test_unknown_incident():
    with pytest.raises(recovery.RecoveryError, match="can't find that recovery"):
        await recovery.next_step("nope")


async def test_family_alert_failure_does_not_block_recovery(monkeypatch):
    async def boom(reason):
        raise RuntimeError("telegram down")
    monkeypatch.setattr(recovery.family, "alert_family", boom)
    assert (await recovery.start_incident("I shared a code"))["step"]["step_number"] == 1
