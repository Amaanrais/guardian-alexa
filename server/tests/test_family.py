import asyncio
import logging

import httpx
import pytest

from server import config, family, storage

pytestmark = pytest.mark.anyio
TOKEN = "123456:SECRET-test-token-do-not-log"


def join(name, chat_id):
    assert family.add_member(name, chat_id) == "added"


async def wait_for(vid, status, timeout=2.0):
    end = asyncio.get_running_loop().time() + timeout
    while (await family.get_verification(vid))["status"] != status:
        assert asyncio.get_running_loop().time() < end, f"never became {status}"
        await asyncio.sleep(0.02)


async def test_fake_verify_is_denied_after_a_delay():
    out = await family.verify_caller("Rahul")  # the fake-mode demo member
    assert out["status"] == "waiting"
    assert (await family.get_verification(out["verification_id"]))["status"] == "waiting"
    await wait_for(out["verification_id"], "denied")


async def test_no_reply_after_timeout(monkeypatch):
    monkeypatch.setattr(family, "FAKE_ANSWER", "no_answer_at_all")
    monkeypatch.setattr(family, "_answer", lambda *a, **k: False)  # nobody ever presses a button
    monkeypatch.setattr(config, "VERIFY_NO_REPLY_S", 0.1)
    vid = (await family.verify_caller("Rahul"))["verification_id"]
    assert (await family.get_verification(vid))["status"] == "waiting"
    await asyncio.sleep(0.15)
    assert (await family.get_verification(vid))["status"] == "no_reply"


async def test_unknown_family_member():
    join("Priya", 11)
    with pytest.raises(family.FamilyError, match="I don't have Rahul in your family circle yet."):
        await family.verify_caller("Rahul")


async def test_names_match_case_insensitively():
    join("Rahul", 11)
    assert (await family.verify_caller("  rahul "))["status"] == "waiting"


async def test_unknown_verification():
    with pytest.raises(family.FamilyError, match="can't find that call check"):
        await family.get_verification("nope")


async def test_alert_recipients_come_from_config(caplog):
    join("Rahul", 11)
    join("Priya", 22)
    caplog.set_level(logging.INFO)
    out = await family.alert_family("Mum started recovery: shared a code")
    assert out == {"sent": True, "recipients": ["Rahul", "Priya"]}
    assert "fake alert to Rahul, Priya" in caplog.text


async def test_alert_with_nobody_to_tell(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_FAKE", False)
    assert await family.alert_family("x") == {"sent": False, "recipients": []}


class FakeBot:
    """Records Bot API calls; answers like Telegram does."""

    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def handler(self, request: httpx.Request) -> httpx.Response:
        method = request.url.path.rsplit("/", 1)[-1]
        body = request.read().decode() and __import__("json").loads(request.read())
        self.calls.append((method, body))
        if self.fail:
            return httpx.Response(401, json={"ok": False, "description": f"Unauthorized for bot{TOKEN}"})
        result = {"sendMessage": {"message_id": len(self.calls)}}.get(method, True)
        return httpx.Response(200, json={"ok": True, "result": result})

    def install(self):
        family.set_telegram(family.Telegram(TOKEN, httpx.AsyncClient(transport=httpx.MockTransport(self.handler))))
        return self


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_FAKE", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", TOKEN)
    return FakeBot().install()


def press(vid, answer, chat_id, cq_id="cq1"):
    return {"update_id": 1, "callback_query": {"id": cq_id, "data": f"v:{vid}:{answer}", "from": {"id": chat_id},
                                               "message": {"message_id": 5, "chat": {"id": chat_id}}}}


def start(text, chat_id, first_name="Rahul", chat_type="private"):
    return {"update_id": 2, "message": {"text": text, "chat": {"id": chat_id, "type": chat_type},
                                        "from": {"id": chat_id, "first_name": first_name}}}


async def test_verify_sends_buttons_and_records_confirmed(bot):
    join("Rahul", 42)
    vid = (await family.verify_caller("Rahul"))["verification_id"]
    method, body = bot.calls[0]
    assert method == "sendMessage" and body["chat_id"] == 42
    assert body["text"] == f"Are you calling {config.PERSON_NAME} right now?"
    buttons = body["reply_markup"]["inline_keyboard"][0]
    assert [b["text"] for b in buttons] == ["Yes, it's me", "No, it's not me"]
    await family.handle_update(press(vid, "yes", 42))
    assert (await family.get_verification(vid))["status"] == "confirmed"
    assert [c[0] for c in bot.calls[1:]] == ["answerCallbackQuery", "editMessageText"]


async def test_denied_by_button(bot):
    join("Rahul", 42)
    vid = (await family.verify_caller("Rahul"))["verification_id"]
    await family.handle_update(press(vid, "no", 42))
    assert (await family.get_verification(vid))["status"] == "denied"


async def test_button_from_another_chat_is_ignored(bot):
    join("Rahul", 42)
    vid = (await family.verify_caller("Rahul"))["verification_id"]
    await family.handle_update(press(vid, "yes", 999))
    assert (await family.get_verification(vid))["status"] == "waiting"


async def test_late_answer_after_no_reply_is_ignored(bot, monkeypatch):
    join("Rahul", 42)
    monkeypatch.setattr(config, "VERIFY_NO_REPLY_S", 0)
    vid = (await family.verify_caller("Rahul"))["verification_id"]
    await asyncio.sleep(0.01)
    await family.handle_update(press(vid, "yes", 42))
    assert (await family.get_verification(vid))["status"] == "no_reply"


async def test_start_joins_the_family_circle(bot):
    await family.handle_update(start("/start", 42, "Rahul"))
    assert storage.get_store().get("family", "rahul") ["chat_id"] == 42
    assert "you're now in" in bot.calls[-1][1]["text"]


async def test_start_cannot_take_over_an_existing_name(bot):
    join("Rahul", 42)
    await family.handle_update(start("/start", 666, "Rahul"))
    assert family.find("Rahul")["chat_id"] == 42
    assert "already in" in bot.calls[-1][1]["text"]


async def test_join_code(bot, monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_JOIN_CODE", "tulip-42")
    await family.handle_update(start("/start", 42, "Rahul"))
    await family.handle_update(start("/start wrong", 43, "Priya"))
    assert family.members() == []
    await family.handle_update(start("/start tulip-42", 42, "Rahul"))
    assert [m["name"] for m in family.members()] == ["Rahul"]


async def test_group_chats_cannot_join(bot):
    await family.handle_update(start("/start", -100, "Rahul", chat_type="group"))
    assert family.members() == []


async def test_alert_goes_to_everyone_in_the_circle(bot):
    join("Rahul", 42)
    join("Priya", 43)
    out = await family.alert_family("Mum started recovery: shared a code")
    assert out == {"sent": True, "recipients": ["Rahul", "Priya"]}
    assert sorted(b["chat_id"] for m, b in bot.calls if m == "sendMessage") == [42, 43]


async def test_token_never_appears_in_logs(monkeypatch, caplog):
    monkeypatch.setattr(config, "TELEGRAM_FAKE", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", TOKEN)
    caplog.set_level(logging.DEBUG)  # everything, including httpx and httpcore
    FakeBot(fail=True).install()
    join("Rahul", 42)
    assert await family.alert_family("x") == {"sent": False, "recipients": []}
    with pytest.raises(family.FamilyError, match="couldn't reach Rahul"):
        await family.verify_caller("Rahul")

    def explode(request):
        raise httpx.ConnectError(f"cannot connect to {request.url}")  # httpx errors carry the URL
    family.set_telegram(family.Telegram(TOKEN, httpx.AsyncClient(transport=httpx.MockTransport(explode))))
    await family.alert_family("x")
    assert caplog.records, "expected some logging to inspect"
    assert TOKEN not in caplog.text
    assert "SECRET" not in caplog.text


def test_redact_filter_blanks_the_token(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", TOKEN)
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "url was %s", (f"https://api.telegram.org/bot{TOKEN}/x",), None)
    family.RedactToken().filter(record)
    assert TOKEN not in record.getMessage()


def test_circle_is_names_only_in_join_order():
    join("Amaan", 42)
    join("Priya", 43)
    assert family.circle() == {"members": [{"name": "Amaan"}, {"name": "Priya"}]}


def test_circle_in_fake_mode_has_the_demo_member():
    assert family.circle() == {"members": [{"name": "Rahul"}]}


def test_circle_is_empty_until_someone_joins(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_FAKE", False)
    assert family.circle() == {"members": []}
