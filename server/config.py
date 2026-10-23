"""Runtime settings. Everything configurable comes from the environment (.env at the repo root)."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")


def _env(name: str, default: str) -> str:
    """A blank value (`KEY=` as copied from .env.example) means "use the default"."""
    return os.getenv(name) or default


PROTOCOL_VERSION = "2025-11-25"

HOST = _env("GUARDIAN_HOST", "127.0.0.1")
PORT = int(_env("GUARDIAN_PORT", "8765"))
# Comma-separated Host header values to accept when serving beyond localhost (DNS-rebinding protection).
ALLOWED_HOSTS = [h.strip() for h in _env("GUARDIAN_ALLOWED_HOSTS", "").split(",") if h.strip()]

BRANDS_FILE = Path(_env("GUARDIAN_BRANDS_FILE", str(REPO_ROOT / "server" / "brands.json")))
SCREENS_DIR = Path(_env("GUARDIAN_SCREENS_DIR", str(REPO_ROOT / "server" / "screens")))
SANDBOX_CONCURRENCY = int(_env("GUARDIAN_SANDBOX_CONCURRENCY", "2"))

# Who Guardian protects, as family members know them ("Are you calling Mum right now?").
PERSON_NAME = _env("GUARDIAN_PERSON_NAME", "Mum")
DATA_DIR = Path(_env("GUARDIAN_DATA_DIR", str(REPO_ROOT / "server" / "data")))
PLAYBOOKS_DIR = REPO_ROOT / "playbooks"

# Telegram family messaging. The token is a secret: it is never logged.
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_FAKE = _env("TELEGRAM_FAKE", "") == "1"
# If set, family members must send "/start <code>" to join; strongly recommended.
TELEGRAM_JOIN_CODE = _env("TELEGRAM_JOIN_CODE", "")

# bedrock | anthropic | openai | none
LLM_PROVIDER = _env("LLM_PROVIDER", "none").strip().lower()

# Fixed by spec, not configurable.
QUICK_DNS_TIMEOUT_S = 0.35
RDAP_TIMEOUT_S = 0.3
SANDBOX_TIMEOUT_S = 10.0
VERIFY_NO_REPLY_S = 120
FAKE_ANSWER_DELAY_S = 3.0
