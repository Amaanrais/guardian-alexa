# guardian-alexa

## Harness — simulated Echo Show

A browser page styled like an Echo Show (left: transcript + mic + spoken replies, right: verdict card)
and a small FastAPI backend whose agent connects to the Guardian MCP server as a real MCP client
(Streamable HTTP, official `mcp` SDK), lists its tools and calls them.

### Run

```bash
source venv/bin/activate && pip install -r requirements.txt
# terminal 1: Guardian MCP server on http://localhost:8000/mcp
# terminal 2:
cd harness
MCP_URL=http://localhost:8000/mcp uvicorn app:app --port 8080
```
Open http://localhost:8080 in **Chrome or Edge** (Web Speech API; other browsers get typing only).

| Env var | Default | Meaning |
|---|---|---|
| `MCP_URL` | `http://localhost:8000/mcp` | Guardian MCP server |
| `USE_BEDROCK` | `0` | `1` = Bedrock Converse tool use; otherwise keyword-routed mock mode (no AWS) |
| `AWS_REGION`, `BEDROCK_MODEL_ID` | `us-east-1`, a Claude model id | Bedrock settings (needs AWS credentials + model access) |

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
`python harness/fake_server.py` serves canned responses in the `docs/CONTRACT.md` format on `http://localhost:8000/mcp`.
