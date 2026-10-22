"""Runtime settings. Everything configurable comes from the environment (.env at the repo root)."""

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

PROTOCOL_VERSION = "2025-11-25"

HOST = os.getenv("GUARDIAN_HOST", "127.0.0.1")
PORT = int(os.getenv("GUARDIAN_PORT", "8765"))
# Comma-separated Host header values to accept when serving beyond localhost (DNS-rebinding protection).
ALLOWED_HOSTS = [h.strip() for h in os.getenv("GUARDIAN_ALLOWED_HOSTS", "").split(",") if h.strip()]

BRANDS_FILE = Path(os.getenv("GUARDIAN_BRANDS_FILE", str(REPO_ROOT / "server" / "brands.json")))
SCREENS_DIR = Path(os.getenv("GUARDIAN_SCREENS_DIR", str(REPO_ROOT / "server" / "screens")))
SANDBOX_CONCURRENCY = int(os.getenv("GUARDIAN_SANDBOX_CONCURRENCY", "2"))

# Who Guardian protects, as family members know them ("Are you calling Mum right now?").
PERSON_NAME = os.getenv("GUARDIAN_PERSON_NAME", "Mum")
DATA_DIR = Path(os.getenv("GUARDIAN_DATA_DIR", str(REPO_ROOT / "server" / "data")))
PLAYBOOKS_DIR = REPO_ROOT / "playbooks"

# Telegram family messaging. The token is a secret: it is never logged.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_FAKE = os.getenv("TELEGRAM_FAKE", "") == "1"
# If set, family members must send "/start <code>" to join; strongly recommended.
TELEGRAM_JOIN_CODE = os.getenv("TELEGRAM_JOIN_CODE", "")

# bedrock | anthropic | openai | none
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "none").strip().lower()

# Fixed by spec, not configurable.
QUICK_DNS_TIMEOUT_S = 0.35
RDAP_TIMEOUT_S = 0.3
SANDBOX_TIMEOUT_S = 10.0
VERIFY_NO_REPLY_S = 120
FAKE_ANSWER_DELAY_S = 3.0
