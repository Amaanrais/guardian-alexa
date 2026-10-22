# Guardian MCP tool contract

Server: `http://localhost:8000/mcp` (FastMCP, stateless Streamable HTTP, protocol 2025-11-25).
Every tool returns a JSON object (as `structuredContent`, or a JSON text block).

**Verdict** is always one of exactly: `Don't open this link` · `Be careful` · `No red flags found`.
It is never "Safe". Reasons are plain-language strings, most important first.

| Tool | Returns |
|---|---|
| `check_link(url)` | `{quick_verdict, reasons[], job_id}` — answers in < 500 ms and starts the sandbox visit |
| `get_link_report(job_id)` | `{status, verdict, reasons[], screenshot_path}` |
| `check_message(text)` | `{verdict, reasons[], job_ids[]}` |
| `verify_caller(name)` | `{verification_id}` |
| `get_verification(id)` | `{status: "confirmed" \| "denied" \| "no_reply"}` |
| `start_incident(description)` | `{incident_id, step}` |
| `next_step(incident_id)` | `{step}` or `{done: true}` |
| `alert_family(reason)` | `{sent: true}` |

## Notes for the harness
- `get_link_report.status`: the harness treats `done`, `complete` or `completed` as finished, and `failed` or `error` as stop. Anything else (e.g. `pending`, `running`) means keep polling.
- `screenshot_path` is either a full URL (presigned S3) or a path under the server origin; the harness prefixes `SCREENSHOT_BASE_URL` (default: `MCP_URL` without `/mcp`).
- Voice rule: no tool or reply ever asks for passwords, codes, PINs or card numbers.
