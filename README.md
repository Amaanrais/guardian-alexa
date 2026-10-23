# guardian-alexa

New here? Start with [GUIDE.md](GUIDE.md): setup, running it, the demo script and troubleshooting.

## Harness — simulated Echo Show

A browser page styled like an Echo Show (left: transcript + mic + spoken replies, right: verdict card)
and a small FastAPI backend whose agent connects to the Guardian MCP server as a real MCP client
(Streamable HTTP, official `mcp` SDK), lists its tools and calls them.

### Run

```bash
uv venv .venv --python 3.12 && .venv/bin/pip install -r requirements.txt   # once
.venv/bin/playwright install chromium                                     # once, for the link sandbox
cp .env.example .env            # then set AGENT_* (blank AGENT_PROVIDER = mock, no key needed)

# terminal 1, repo root: Guardian MCP server on http://localhost:8765/mcp
.venv/bin/python -m server
# terminal 2:
cd harness && ../.venv/bin/uvicorn app:app --port 8080
```
Open http://localhost:8080 in **Chrome or Edge** (Web Speech API; other browsers get typing only).
The corner chip shows which agent is running (`Mock agent` or `openrouter · <model>`).

`.env.example` lists only the settings you'll usually change; blank lines mean "use the default".
Example for OpenRouter's free tier (free models are rate-limited, so keep `mock` as a demo fallback):

```
AGENT_PROVIDER=openrouter
AGENT_MODEL=nvidia/nemotron-3.5-lightning:free
AGENT_API_KEY=sk-or-...
```

| Env var | Default | Meaning |
|---|---|---|
| `MCP_URL` | `http://localhost:8765/mcp` | Guardian MCP server |
| `AGENT_PROVIDER` | `mock` | `mock` = keyword routing, no LLM. `bedrock`, `groq`, `openrouter`, `openai`, `ollama`, or any name with `AGENT_BASE_URL` (OpenAI-compatible API). `USE_BEDROCK=1` still means `bedrock`. |
| `AGENT_MODEL` | — | Model id for that provider, e.g. `llama-3.3-70b-versatile` (Groq), `nvidia/nemotron-3.5-lightning:free` (OpenRouter). Must support tool calling; embedding models won't work. |
| `AGENT_API_KEY` | — | Provider API key (not for `bedrock` or `ollama`) |
| `AGENT_BASE_URL` | preset | Overrides the provider's URL, e.g. `https://api.together.xyz/v1` |
| `AWS_REGION`, `BEDROCK_MODEL_ID` | `us-east-1`, a Claude model id | Bedrock settings (needs AWS credentials + model access) |

Server settings (Telegram, port, person's name, ...) are in `server/README.md`.
In both modes the harness itself waits for `check_link`'s sandbox report (~10 s) before answering,
so the verdict includes what the page asks for, not just the address checks. After `verify_caller`
it likewise waits for the family member's answer. If a model call fails (free models are
rate-limited), the harness retries once, then answers that turn in mock mode.
The harness reads the repo-root `.env` if present.

### Mock mode phrases
- a link → `check_link`, then `get_link_report` ("Is this a scam? http://…")
- "Is that really Rahul calling?" → `verify_caller`; "did he answer?" → `get_verification`
- "I gave someone my code" / "I clicked a link" → `start_incident`; "next" → `next_step`; "repeat" replays the step
- "tell my family" → `alert_family`; other scam text → `check_message`

### Card
Colour **and** icon (⛔ red, ⚠️ amber, ℹ️ grey), screenshot thumbnail, top 3 reasons, one action button.
Titles are only "Don't open this link" / "Be careful" / "No red flags found" (or the server's own title);
the word "safe" is rewritten before display and speech.

### Tool-result shape assumed
`harness/card.py` follows `docs/CONTRACT.md`; it also accepts a `card`
object or flat fields: `verdict`/`level` (high|medium|none), `reasons[]`, `screenshot_url`, `job_id`,
`action{label,tool,args}`, `verification_id`, `status` (confirmed|denied|none), `incident_id`, `step`, `speech`.
Adjust `card.py` once the contract is final.

### No server yet?
`python harness/fake_server.py` serves canned responses in the `docs/CONTRACT.md` format on `http://localhost:8765/mcp`.
