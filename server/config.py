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

# Fixed by spec, not configurable.
QUICK_DNS_TIMEOUT_S = 0.35
RDAP_TIMEOUT_S = 0.3
SANDBOX_TIMEOUT_S = 10.0
