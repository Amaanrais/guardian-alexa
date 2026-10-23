# Friction log

Anything confusing or broken while building Guardian (AWS sign-up, Bedrock, Alexa+ docs, tooling).
Newest first. Copy the template, keep it short, add a screenshot path if you have one.

```
## YYYY-MM-DD HH:MM · Area (AWS / Bedrock / Alexa+ / Telegram / tooling) · who
- Tried:
- Expected:
- Happened:   (exact error text)
- Workaround:
```

---

## 2026-10-23 · Setup · tooling
- Tried: `cp .env.example .env`, then `python -m server`, as the README says.
- Expected: the server starts with defaults.
- Happened: `ValueError: invalid literal for int() with base 10: ''`. Blank `KEY=` lines overrode the defaults.
- Workaround: blank now means "use the default" (`server/config.py`), and `.env.example` lists only the 6 usual settings.

## 2026-10-23 · OpenRouter · tooling
- Tried: `nvidia/nemotron-3.5-embed-1b:free` as the agent model.
- Expected: the agent answers and calls tools.
- Happened: not listed on OpenRouter, and an embedding model can't chat or call tools anyway.
- Workaround: `nvidia/nemotron-3.5-lightning:free` (has tool calling). The model also answered links before the sandbox
  finished, so the harness now waits for `get_link_report` itself.

## 2026-10-23 · Demo site · tooling
- Tried: planning to serve the NordBank demo page from `localhost` and check it with `check_link`.
- Expected: a sandbox report with a screenshot.
- Happened: the SSRF guard (correctly) refuses every private address, so `check_link` would answer "This link
  points to a private or internal network address, so it can't be checked." Caught while reading `netguard.py`.
- Workaround: host `site/` on a public static host (Netlify / Cloudflare Pages / GitHub Pages) and check that URL.

## 2026-10-23 · LLM providers · tooling
- Tried: running the agent on something other than Bedrock while AWS access was still pending.
- Expected: one setting to switch provider.
- Happened: the agent was hard-wired to Bedrock Converse; Groq/OpenRouter use the OpenAI tool-call format.
- Workaround: `harness/llm.py` gateway, `AGENT_PROVIDER` / `AGENT_MODEL` / `AGENT_API_KEY` / `AGENT_BASE_URL`.
