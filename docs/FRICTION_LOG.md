# Friction log

Anything confusing or broken while building Guardian (AWS sign-up, Bedrock, Alexa+ docs, tooling).
Newest first. Copy the template, keep it short, add a screenshot path if you have one.

```
## YYYY-MM-DD HH:MM · Area (AWS / Bedrock / Alexa+ / Telegram / tooling) · who
- Tried:
- Expected:
- Happened:   (exact error text)
- Workaround:
- Severity:   High (blocked us) / Medium (cost real time) / Low (annoying)
- Suggestion: (what the tool's makers could change)
```

---

## 2026-10-23 · Alexa+ · tooling
- Tried: running Guardian, our own MCP server, behind a real Alexa+ device to demo it.
- Expected: to test on an Echo we had access to, or in a developer simulator.
- Happened: the only Echo available belonged to a friend. Testing on it would have meant signing their Amazon
  account out and ours in, and they weren't comfortable doing that on their personal device. With no Alexa+
  simulator to fall back on, we couldn't show Guardian on a real Echo.
- Workaround: built `harness/`, a simulated Echo Show whose agent connects to Guardian as a real MCP client
  (Streamable HTTP, official `mcp` SDK), so everything except the device itself is real.
- Severity: High. The core "Alexa+" experience could only be simulated.
- Suggestion: a browser-based Alexa+ developer simulator that accepts a custom MCP server URL, or a way to add a
  developer account to a shared Echo for testing without signing the owner out. Also a documented pattern for
  long-running tools (a progress update or callback), since a sandboxed link check takes about 10 seconds.

## 2026-10-23 · Playwright / Chromium · tooling
- Tried: checking the NordBank demo page through a Cloudflare quick tunnel (`scripts/demo_bank.sh`).
- Expected: the sandbox opens the page and returns a report with a screenshot.
- Happened: "couldn't open the page". Our sandbox fulfils each request through `route.fulfill()`, joining repeated
  response headers with `"\n"`. Cloudflare tunnels repeat `x-robots-tag`, and Chromium never fired `load` on a
  response whose header value held a newline. No error, just a timeout.
- Workaround: join repeated headers with `", "` and keep `"\n"` only for `Set-Cookie` (`server/sandbox.py`).
- Severity: Medium. Our main demo failed, and the silent timeout took a while to trace.
- Suggestion: Playwright could document which header values `route.fulfill()` accepts and raise an error (or
  log a warning) for values Chromium will reject, instead of letting the page hang.

## 2026-10-23 · Setup · tooling
- Tried: `cp .env.example .env`, then `python -m server`, as the README says.
- Expected: the server starts with defaults.
- Happened: `ValueError: invalid literal for int() with base 10: ''`. Blank `KEY=` lines overrode the defaults.
- Workaround: blank now means "use the default" (`server/config.py`), and `.env.example` lists only the 6 usual settings.
- Severity: High. The server wouldn't start on first setup.
- Suggestion: python-dotenv's README could point out that `KEY=` loads an empty string, not "unset", so code
  should treat blank as default.

## 2026-10-23 · OpenRouter · tooling
- Tried: `nvidia/nemotron-3.5-embed-1b:free` as the agent model.
- Expected: the agent answers and calls tools.
- Happened: not listed on OpenRouter, and an embedding model can't chat or call tools anyway.
- Workaround: `nvidia/nemotron-3.5-lightning:free` (has tool calling). The model also answered links before the sandbox
  finished, so the harness now waits for `get_link_report` itself.
- Severity: Medium. Trial and error to find a free model that calls tools, plus a harness change.
- Suggestion: OpenRouter's model list and API could flag clearly which models support tool calling, and the API
  could return a clear error when a model id doesn't exist or can't chat.

## 2026-10-23 · Demo site · tooling
- Tried: planning to serve the NordBank demo page from `localhost` and check it with `check_link`.
- Expected: a sandbox report with a screenshot.
- Happened: the SSRF guard (correctly) refuses every private address, so `check_link` would answer "This link
  points to a private or internal network address, so it can't be checked." Caught while reading `netguard.py`.
- Workaround: serve only `site/demo-bank/` through a temporary Cloudflare quick tunnel (`scripts/demo_bank.sh`) and
  check that URL. The fake bank page is never hosted publicly.
- Severity: Low. Our guard was right; we only needed another way to serve the page.
- Suggestion: none for a vendor. Note for MCP builders: an SSRF guard in a link checker blocks localhost demos,
  so plan a public test URL early.

## 2026-10-23 · LLM providers · tooling
- Tried: running the agent on something other than Bedrock while AWS access was still pending.
- Expected: one setting to switch provider.
- Happened: the agent was hard-wired to Bedrock Converse; Groq/OpenRouter use the OpenAI tool-call format.
- Workaround: `harness/llm.py` gateway, `AGENT_PROVIDER` / `AGENT_MODEL` / `AGENT_API_KEY` / `AGENT_BASE_URL`.
- Severity: Medium. AWS access was still pending, so we couldn't use Bedrock and had to write a provider layer.
- Suggestion: faster AWS account and Bedrock model access for hackathon participants, for example pre-approved
  access with the hackathon sign-up.
