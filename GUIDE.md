# Guardian guide

How to set up, run and demo Guardian on your own machine. Technical details are in `README.md`
(harness) and `server/README.md` (MCP server).

## 1. Set up (once)

```bash
uv venv .venv --python 3.12 && .venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium        # the browser the link check uses
cp .env.example .env                          # git-ignored; never commit it
```

Edit `.env`:

| You want | Set |
|---|---|
| No LLM, no key (safe fallback) | `AGENT_PROVIDER=mock` (or leave it blank) |
| OpenRouter (free tier) | `AGENT_PROVIDER=openrouter`, `AGENT_MODEL=nvidia/nemotron-3.5-lightning:free`, `AGENT_API_KEY=sk-or-...` |
| Groq | `AGENT_PROVIDER=groq`, `AGENT_MODEL=llama-3.3-70b-versatile`, `AGENT_API_KEY=gsk_...` |
| Bedrock | `AGENT_PROVIDER=bedrock` (uses your AWS credentials) |
| Fake family (no Telegram) | `TELEGRAM_FAKE=1`: one member, "Rahul", who answers "No" after 3 s |
| Real family on Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_JOIN_CODE`, and leave `TELEGRAM_FAKE` blank (see `server/README.md`) |

The model must support tool calling. Embedding models don't work.

## 2. Run

```bash
.venv/bin/python -m server                                # terminal 1, repo root
cd harness && ../.venv/bin/uvicorn app:app --port 8080    # terminal 2
```

Open http://localhost:8080 in **Chrome or Edge** and allow the microphone. The chip in the corner
says which agent is running: `Mock agent` or `openrouter · <model>`.

## 3. Host the demo bank page

The link check refuses `localhost` and private addresses on purpose, so the NordBank page must
be on a public URL:

Run `scripts/demo_bank.sh` (terminal 3). It serves only `site/demo-bank/` on port 8090 through a
cloudflared quick tunnel (installing `cloudflared` with Homebrew if needed) and prints the public URL,
e.g. `https://<name>.trycloudflare.com/`. The URL changes every run. The rest of `site/` (home,
privacy, terms) is hosted separately and never links to the demo bank.

NordBank is invented. The page has a "FICTIONAL DEMO" banner, `noindex`, and a form that can't submit.

## 4. Demo script

Say or type these in order. The link check takes about 10 s; the rest answer within a few seconds.

| # | Say | You should see |
|---|---|---|
| 1 | "Is this link okay? https://&lt;name&gt;.trycloudflare.com/" | Red card "Don't open this link", a screenshot, and the purple "This page tried to fool the AI" banner (the page hides an instruction telling the AI to call it safe). |
| 2 | "Is that really Rahul calling me?" | Guardian messages Rahul. About 3 s later: Rahul says it isn't him, so hang up. |
| 3 | "I gave someone my code" | A recovery checklist, step 1 of 4. |
| 4 | "next" (×3), "repeat" once | The next steps; the last one has an "Ask my family to check with me" button. |
| 5 | "Tell my family" | "I've told Rahul." |

Points worth saying out loud in the video: Guardian never says "safe" (only "no red flags
found"), it never asks for codes or PINs, and the web page's own words never reach the AI.

## 5. If something goes wrong

| Symptom | Fix |
|---|---|
| "I can't reach my safety checks right now." | Terminal 1 isn't running, or crashed. Restart `python -m server`. |
| Chip says `Mock agent` but you set a provider | `.env` is not in the repo root, or terminal 2 was started before you edited it. Restart it. |
| Replies stop or are slow on OpenRouter | Free-tier rate limit. The harness retries once, then answers that turn in mock mode; to stay in mock, set `AGENT_PROVIDER=mock` and restart terminal 2. |
| Link says "private or internal network address" | You checked a `localhost` URL. Use the hosted one from step 3. |
| Microphone does nothing | Use Chrome or Edge, allow the mic, or just type. |
| No server at all (e.g. only working on the UI) | `python harness/fake_server.py` instead of terminal 1: canned answers. |

Before recording, run the whole script once in `mock` mode as a backup take.

## 6. Tests

```bash
.venv/bin/python -m pytest server             # ~35 s, launches headless Chromium
```
