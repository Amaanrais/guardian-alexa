"""The family circle over Telegram: verify_caller, get_verification, alert_family, and the bot's update poller.

Family members join by sending the bot /start (or /start <code> when TELEGRAM_JOIN_CODE is set);
their first name and chat id go into server/data/family.json. Recipients always come from there,
never from a tool caller. TELEGRAM_FAKE=1 runs everything without the network.
"""

import asyncio
import logging
import secrets
import time

import httpx

from . import config
from .storage import get_store

log = logging.getLogger(__name__)
# httpx logs every request URL at INFO, and Telegram URLs contain the bot token.
for _noisy in ("httpx", "httpcore"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

API = "https://api.telegram.org"
FAMILY, VERIFY, STATE = "family", "verifications", "telegram"
FAKE_MEMBER = {"name": "Rahul", "chat_id": 0}
FAKE_ANSWER = "denied"
POLL_TIMEOUT_S = 25
ANSWERS = {"yes": ("confirmed", "Yes, it's me"), "no": ("denied", "No, it's not me")}

_telegram = None
_tasks: set[asyncio.Task] = set()


class FamilyError(Exception):
    """A plain-language problem to report back to the person."""


class TelegramError(Exception):
    """A failed Bot API call. Its message never contains the token."""


def redact(text: str) -> str:
    token = config.TELEGRAM_BOT_TOKEN
    return text.replace(token, "***") if token else text


class RedactToken(logging.Filter):
    """Belt and braces for log handlers: blank out the bot token wherever it might appear."""

    def filter(self, record: logging.LogRecord) -> bool:
        if config.TELEGRAM_BOT_TOKEN:
            record.msg = redact(record.getMessage())
            record.args = ()
        return True


class Telegram:
    def __init__(self, token: str, client: httpx.AsyncClient | None = None):
        self._token = token
        self._client = client or httpx.AsyncClient()

    async def call(self, method: str, *, http_timeout: float = 10, **params):
        try:
            resp = await self._client.post(f"{API}/bot{self._token}/{method}", json=params, timeout=http_timeout)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            # httpx's own messages include the URL, and so the token: report only the kind of failure
            raise TelegramError(f"{method} failed: {type(exc).__name__}") from None
        if not data.get("ok"):
            raise TelegramError(f"{method} failed: {redact(str(data.get('description') or resp.status_code))}")
        return data["result"]


def telegram() -> Telegram:
    global _telegram
    if _telegram is None:
        if not config.TELEGRAM_BOT_TOKEN:
            raise FamilyError("Family messaging isn't set up yet.")
        _telegram = Telegram(config.TELEGRAM_BOT_TOKEN)
    return _telegram


def set_telegram(client: Telegram | None) -> None:
    """Swap the Bot API client (tests). None goes back to the default."""
    global _telegram
    _telegram = client


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


# ---------- the family circle ----------

def members() -> list[dict]:
    found = list(get_store().all(FAMILY).values())
    if not found and config.TELEGRAM_FAKE:
        return [FAKE_MEMBER]  # so fake mode works as a demo fallback out of the box
    return found


def find(name: str) -> dict | None:
    key = name.strip().casefold()
    return next((m for m in members() if m["name"].casefold() == key), None)


def add_member(name: str, chat_id: int) -> str:
    """Returns "added", "exists" (same person again) or "taken" (that name belongs to another chat)."""
    key = name.strip().casefold()
    existing = get_store().get(FAMILY, key)
    if existing:
        # Never let a second account take over a name: it could then answer call checks for them.
        return "exists" if existing["chat_id"] == chat_id else "taken"
    get_store().put(FAMILY, key, {"name": name.strip(), "chat_id": chat_id, "joined_at": time.time()})
    return "added"


# ---------- verify_caller / get_verification ----------

async def verify_caller(name: str) -> dict:
    member = find(name)
    if member is None:
        raise FamilyError(f"I don't have {name.strip()[:60]} in your family circle yet.")
    vid = secrets.token_urlsafe(16)
    record = {"name": member["name"], "chat_id": member["chat_id"], "status": "waiting", "created_at": time.time()}
    get_store().put(VERIFY, vid, record)
    if config.TELEGRAM_FAKE:
        _spawn(_fake_answer(vid))
    else:
        try:
            msg = await telegram().call(
                "sendMessage", chat_id=member["chat_id"], text=f"Are you calling {config.PERSON_NAME} right now?",
                reply_markup={"inline_keyboard": [[
                    {"text": ANSWERS["yes"][1], "callback_data": f"v:{vid}:yes"},
                    {"text": ANSWERS["no"][1], "callback_data": f"v:{vid}:no"}]]})
        except TelegramError as exc:
            log.warning("verify_caller: %s", exc)
            raise FamilyError(f"I couldn't reach {member['name']} just now. If you're unsure, "
                              "hang up and call them on the number you know.") from None
        get_store().put(VERIFY, vid, {**record, "message_id": msg["message_id"]})
    return {"verification_id": vid, "status": "waiting"}


async def _fake_answer(vid: str) -> None:
    await asyncio.sleep(config.FAKE_ANSWER_DELAY_S)
    _answer(vid, FAKE_ANSWER)


def _answer(vid: str, status: str, chat_id: int | None = None) -> bool:
    """Record a yes/no if the check is still open and (for real presses) came from the right chat."""
    record = get_store().get(VERIFY, vid)
    if not record or _current_status(vid, record) != "waiting":
        return False
    if chat_id is not None and record["chat_id"] != chat_id:
        return False
    get_store().put(VERIFY, vid, {**record, "status": status, "answered_at": time.time()})
    return True


def _current_status(vid: str, record: dict) -> str:
    if record["status"] == "waiting" and time.time() - record["created_at"] > config.VERIFY_NO_REPLY_S:
        get_store().put(VERIFY, vid, {**record, "status": "no_reply"})
        return "no_reply"
    return record["status"]


async def get_verification(vid: str) -> dict:
    record = get_store().get(VERIFY, vid)
    if record is None:
        raise FamilyError("I can't find that call check. Let's ask again.")
    return {"status": _current_status(vid, record)}


# ---------- alert_family ----------

async def alert_family(reason: str) -> dict:
    """Message everyone in the family circle. Recipients come from config only."""
    reason = " ".join(str(reason).split())[:500]
    recipients = members()
    if not recipients:
        log.warning("alert_family: nobody is in the family circle yet")
        return {"sent": False, "recipients": []}
    text = f"Guardian alert for {config.PERSON_NAME}: {reason}"
    if config.TELEGRAM_FAKE:
        log.info("fake alert to %s: %s", ", ".join(m["name"] for m in recipients), reason)
        return {"sent": True, "recipients": [m["name"] for m in recipients]}
    sent = []
    for m in recipients:
        try:
            await telegram().call("sendMessage", chat_id=m["chat_id"], text=text)
            sent.append(m["name"])
        except (TelegramError, FamilyError) as exc:
            log.warning("alert to %s failed: %s", m["name"], exc)
    return {"sent": bool(sent), "recipients": sent}


# ---------- incoming updates: button presses and /start ----------

async def handle_update(update: dict) -> None:
    tg = telegram()
    if cq := update.get("callback_query"):
        parts = str(cq.get("data", "")).split(":")
        chat_id = (cq.get("message") or {}).get("chat", {}).get("id", cq.get("from", {}).get("id"))
        if len(parts) != 3 or parts[0] != "v" or parts[2] not in ANSWERS:
            return
        status, label = ANSWERS[parts[2]]
        ok = _answer(parts[1], status, chat_id)
        await tg.call("answerCallbackQuery", callback_query_id=cq["id"],
                      text=f"Thanks, I've told {config.PERSON_NAME}." if ok else "This check has already finished.")
        if ok and cq.get("message"):
            await tg.call("editMessageText", chat_id=chat_id, message_id=cq["message"]["message_id"],
                          text=f"Are you calling {config.PERSON_NAME} right now?\nYou answered: {label}")
        return

    msg = update.get("message") or {}
    text = str(msg.get("text") or "")
    if not text.startswith("/start") or msg.get("chat", {}).get("type") != "private":
        return
    chat_id = msg["chat"]["id"]
    code = text.split(maxsplit=1)[1].strip() if " " in text else ""
    if config.TELEGRAM_JOIN_CODE and not secrets.compare_digest(code, config.TELEGRAM_JOIN_CODE):
        reply = "Please ask the family for Guardian's join code, then send /start followed by the code."
    else:
        name = (msg.get("from") or {}).get("first_name") or "Family member"
        reply = {
            "added": f"Hi {name}, you're now in {config.PERSON_NAME}'s Guardian family circle. "
                     f"I'll message you if {config.PERSON_NAME} needs help, or wants to check a call is really you.",
            "exists": f"You're already in {config.PERSON_NAME}'s Guardian family circle.",
            "taken": f"Someone called {name} is already in {config.PERSON_NAME}'s family circle. "
                     "Ask the family to check the list.",
        }[add_member(name, chat_id)]
    await tg.call("sendMessage", chat_id=chat_id, text=reply)


async def poll_updates() -> None:
    """Long-poll getUpdates forever, remembering the offset across restarts."""
    tg = telegram()
    try:
        await tg.call("deleteWebhook")  # getUpdates refuses to run while a webhook is set
    except TelegramError as exc:
        log.warning("Telegram: %s", exc)
    offset = (get_store().get(STATE, "updates") or {}).get("offset")
    while True:
        try:
            updates = await tg.call("getUpdates", http_timeout=POLL_TIMEOUT_S + 10, offset=offset,
                                    timeout=POLL_TIMEOUT_S, allowed_updates=["message", "callback_query"])
        except TelegramError as exc:
            log.warning("Telegram polling: %s", exc)
            await asyncio.sleep(5)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            try:
                await handle_update(update)
            except Exception as exc:  # noqa: BLE001 - one bad update mustn't stop the poller
                log.warning("Telegram update %s failed: %s", update.get("update_id"), redact(str(exc)))
            get_store().put(STATE, "updates", {"offset": offset})


def start_polling() -> asyncio.Task | None:
    if config.TELEGRAM_FAKE:
        log.info("Telegram fake mode: no network")
        return None
    if not config.TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN isn't set: family messaging is off")
        return None
    return asyncio.create_task(poll_updates())
