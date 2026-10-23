#!/usr/bin/env bash
# Serve only site/demo-bank/ (the fictional NordBank page) on port 8090 and expose it through a
# cloudflared quick tunnel, so Guardian's link check (which refuses localhost) can visit it.
# Prints the public URL; Ctrl+C stops both.
set -euo pipefail

PORT=8090
DIR="$(cd "$(dirname "$0")/../site/demo-bank" && pwd)"

if ! command -v cloudflared >/dev/null; then
  brew install cloudflared
fi

LOG="$(mktemp -t demo-bank-tunnel)"
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$DIR" >/dev/null 2>&1 &
SERVER=$!
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$LOG" 2>&1 &
TUNNEL=$!
trap 'kill $SERVER $TUNNEL 2>/dev/null; rm -f "$LOG"' EXIT INT TERM

for _ in $(seq 60); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
if [ -z "${URL:-}" ]; then
  echo "cloudflared didn't report a URL; its log:" >&2
  cat "$LOG" >&2
  exit 1
fi

echo "NordBank demo page: $URL/"
set +e
wait $TUNNEL
STATUS=$?
echo "cloudflared exited ($STATUS); last lines of its log:" >&2
tail -20 "$LOG" >&2
exit $STATUS
