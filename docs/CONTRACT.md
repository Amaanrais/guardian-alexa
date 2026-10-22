# Guardian MCP tool contract

Server: `http://localhost:8765/mcp` (FastMCP, stateless Streamable HTTP, protocol 2025-11-25).
Every tool returns a JSON object (as `structuredContent`, or a JSON text block).

**Verdict** is always one of exactly: `Don't open this link` · `Be careful` · `No red flags found`.
It is never "Safe". Reasons are plain-language strings, most important first.

| Tool | Returns |
|---|---|
| `check_link(url)` | `{quick_verdict, reasons[], job_id}` — answers in < 500 ms and starts the sandbox visit |
| `get_link_report(job_id)` | `{status, verdict, reasons[], screenshot_path}` |
| `check_message(text)` | `{verdict, reasons[], job_ids[]}` |
| `verify_caller(name)` | `{verification_id, status: "waiting"}` |
| `get_verification(id)` | `{status: "confirmed" \| "denied" \| "no_reply" \| "waiting"}` |
| `start_incident(description)` | `{incident_id, playbook_title, step}` |
| `next_step(incident_id)` | `{step}` or `{done: true, summary}` |
| `alert_family(reason)` | `{sent: true, recipients: [names]}` |

**Errors** come back as an MCP tool error (`isError: true`) whose text is a plain-language
sentence that can be spoken. The SDK may prefix it with `Error executing tool <name>: `.

## Notes for the harness
- `get_link_report.status`: the server returns `pending` or `running` while the sandbox visit is under way, then `done` (including links refused for pointing at a private address; the reasons say so) or `error` (unknown or expired `job_id`, or the check crashed). The harness treats `done`, `complete` or `completed` as finished, and `failed` or `error` as stop. Anything else (e.g. `pending`, `running`) means keep polling.
- `screenshot_path` is either a full URL (presigned S3) or a path under the server origin; the harness prefixes `SCREENSHOT_BASE_URL` (default: `MCP_URL` without `/mcp`). The server currently returns `/screens/<job_id>.png` and serves it at that path; it's `null` when there's no screenshot.
- `check_message.job_ids`: one sandbox job per link found in the text (at most 5), in order; poll each with `get_link_report`.
- Voice rule: no tool or reply ever asks for passwords, codes, PINs or card numbers.

## Recovery: `start_incident` / `next_step`

A **step** is:

```json
{"text": "Call your bank on the number on the back of your card.",
 "step_number": 1, "total_steps": 3,
 "action": {"label": "Tell Rahul", "tool": "alert_family", "args": {"reason": "..."}}}
```

- `text` is one or two short, calm sentences, written to be spoken aloud.
- `step_number` counts from 1; `total_steps` is the playbook's length.
- `action` is optional: one button the harness can show, calling `tool` with `args`.
- No step ever asks for a password, code, PIN or card number. The server refuses to load a playbook that does.

`start_incident(description)` picks a playbook by matching the description against each
playbook's `match_phrases` (case-insensitive keyword scoring) and returns
`{incident_id, playbook_title, step}` with step 1. It also tells the family
(`alert_family`, e.g. "Mum started recovery: shared a code").

**No match:** the server asks one clarifying question instead and creates nothing:

```json
{"incident_id": null, "playbook_title": null,
 "step": {"text": "Did you share a code, or click a link?", "step_number": 0, "total_steps": 0}}
```

`step_number: 0` means "this is a question, not a step". Call `start_incident` again with the
person's answer. The family is only alerted once a playbook has been chosen.

`next_step(incident_id)` returns the next `{step}`, or `{done: true, summary}` after the last
one (and the same again if called after that). An unknown `incident_id` is a tool error.

### Playbook files

`playbooks/<id>.json`:

```json
{"id": "shared_code",
 "title": "I gave someone my code / OTP / PIN",
 "family_summary": "shared a code",
 "match_phrases": ["gave someone my code", "otp", "pin"],
 "steps": [{"text": "...", "action": {"label": "...", "tool": "...", "args": {}}}]}
```

`family_summary` is optional (it's what the family alert says; default: `title`).
In a playbook file, steps only need `text` and an optional `action`; the server adds
`step_number` and `total_steps`.

## Family: `verify_caller` / `get_verification` / `alert_family`

Family messaging uses a Telegram bot. A family member joins by sending the bot `/start`
(or `/start <code>` when `TELEGRAM_JOIN_CODE` is set). Their Telegram first name becomes the
name used in `verify_caller(name)`. The family circle lives on the server, in
`server/data/family.json`.

- `verify_caller(name)` sends that family member "Are you calling Mum right now?" with the
  buttons **Yes, it's me** / **No, it's not me**, and returns `{verification_id, status: "waiting"}`.
  A name not in the family circle is a tool error: "I don't have Rahul in your family circle yet."
- `get_verification(id)` returns `{status}`: `waiting` until they press a button, then
  `confirmed` or `denied`. After **120 seconds** with no answer it becomes `no_reply`.
  Poll about every 3 seconds. An unknown id is a tool error.
- `alert_family(reason)` messages everyone in the family circle and returns
  `{sent: true, recipients: [names]}`. Recipients always come from the server's config, never
  from the caller. If nobody could be reached it returns `{sent: false, recipients: []}`.

**Fake mode** (`TELEGRAM_FAKE=1`): no network. `verify_caller` answers `denied` by itself after
3 seconds, and `alert_family` only logs. If the family circle is empty in fake mode, it contains
one demo member, "Rahul". Use it for tests and as the demo fallback.
