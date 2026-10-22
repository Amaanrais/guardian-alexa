# Guardian MCP server

Checks links and messages for scam warning signs. It runs as a stateless Streamable HTTP MCP
server at `http://127.0.0.1:8765/mcp` and always negotiates protocol revision **2025-11-25**:
whatever version a client proposes in `initialize`, the answer is 2025-11-25. No client is turned
away. A 2026-07-28 client that probes `server/discover` gets "method not found", which is its cue to
fall back to `initialize`.

| Tool | What it does |
|---|---|
| `check_link(url)` | Fast checks (< 500 ms): SSRF guard, punycode/look-alike vs. a brand list, RDAP domain age. Returns `{quick_verdict, reasons[], job_id}` and starts a background sandbox job. |
| `get_link_report(job_id)` | `{status, verdict, reasons[], screenshot_path}`. `status` is `pending`/`running` (keep polling) or `done`/`error` (final). Links refused for pointing at a private address finish as `done`. `error` means an unknown or expired `job_id`, or a crashed check. `screenshot_path` is `/screens/<job_id>.png` on this server, or `null`. |
| `check_message(text)` | Rule-based red flags (urgency, gift cards, OTP/PIN requests, impersonation, payment pressure), plus `check_link` on up to 5 URLs found in the text. Returns `{verdict, reasons[], job_ids[]}`, with one sandbox job per link. |

Every verdict, for links and messages alike, is `Don't open this link`, `Be careful` or
`No red flags found`. Nothing ever says "safe". The shapes follow `docs/CONTRACT.md`.

`GET /screens/<job_id>.png` serves sandbox screenshots. Only names made of job-id characters
ending in `.png` are served, and the job ids are random and unguessable.

## Run

From the repo root:

```sh
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium        # once, for the sandbox
cp .env.example .env               # optional; every variable has a default
python -m server                   # serves http://127.0.0.1:8765/mcp
```

Settings (all optional, read from `.env`):

| Variable | Default | Notes |
|---|---|---|
| `GUARDIAN_HOST` | `127.0.0.1` | Bind address. |
| `GUARDIAN_PORT` | `8765` | |
| `GUARDIAN_ALLOWED_HOSTS` | *(empty)* | Comma-separated `Host` header values, e.g. `guardian.example.com`. Required for DNS-rebinding protection when binding anything other than localhost. |
| `GUARDIAN_BRANDS_FILE` | `server/brands.json` | Brand list (see below). |
| `GUARDIAN_SCREENS_DIR` | `server/screens/` | Where sandbox screenshots go (S3 later). Git-ignored. |
| `GUARDIAN_SANDBOX_CONCURRENCY` | `2` | Max Chromium instances at once. |

## Brand list

`server/brands.json` maps each brand's display name to its official domains, main domain first.
A brand can instead map to an object with extra options:

```json
{
  "NordBank": ["nordbank.example"],
  "American Express": {"domains": ["americanexpress.com"], "aliases": ["Amex"], "payment": true},
  "Visa": {"domains": ["visa.com"], "payment": true, "match_in_domains": false}
}
```

| Option | Meaning |
|---|---|
| `aliases` | Other names the brand goes by. They're used in every check. |
| `payment` | A payment network or wallet. Honest shops show these at checkout (see below). |
| `match_in_domains` | Set `false` for brands whose name is an ordinary word in domains, e.g. "visa" in `uk-visa-help.com`. Look-alike checks still apply. |

The file is read once at startup. Each brand is used three ways:

- **Look-alike domains.** `n0rdbank.com`, or one-letter typos of the name. Spaces are dropped
  from the name to get the domain form, so "Wells Fargo" matches `wellsfargo`.
- **The brand name in an unrelated domain,** such as `nordbank-verify.net`.
- **Pages that claim to be the brand.** The sandbox reads only the places where a site names
  itself: the page title, h1/h2 headings, logo alt text (an `<img>` whose alt, id, class or src
  says "logo") and `og:site_name`. It ignores body text, where shops routinely write "Pay with
  PayPal". Names must match as written or in capitals. Longer names win, so "Apple Pay" doesn't
  also count as Apple. A claim only counts when the page isn't on the brand's official domain
  *and* it asks for something sensitive:
  - most brands: a password, PIN, one-time/SMS code or card details
  - `payment` brands (PayPal, Visa, Mastercard, American Express, Apple Pay, Google Pay,
    Klarna): only a password, PIN or one-time code, never card fields alone

  A claim that counts is enough on its own for "Don't open this link".

Card fields by themselves weigh too little to reach "Be careful". An honest checkout page gets
"No red flags found", and card fields only add weight to other signals.

"NordBank" (`nordbank.example`) is a fictional brand for demos.

## Test

```sh
.venv/bin/python -m pytest server            # everything (~10 s, launches headless Chromium)
.venv/bin/python -m pytest server -m "not browser"   # skip the Chromium tests
```

The tests don't touch the internet, apart from a few that resolve real DNS names such as
`localhost` and `127.0.0.1.nip.io` (those skip if resolution fails). DNS and RDAP are faked,
and the browser sandbox tests serve pages from an `httpx.MockTransport`. The SSRF cases cover
127.0.0.1, 169.254.169.254, 10.x, other private and reserved ranges, IPv6 forms that embed IPv4,
decimal and hex IP notation, mixed public/private DNS answers, and redirects to private IPs (both
HTTP 3xx and script navigations inside Chromium).

## Try it with MCP Inspector

Start the server, then in another terminal:

```sh
npx @modelcontextprotocol/inspector
```

In the Inspector UI, set **Transport Type** to *Streamable HTTP* and **URL** to
`http://127.0.0.1:8765/mcp`, then click **Connect**. Open **Tools**, run `check_link` with a URL,
copy the `job_id`, wait a few seconds and run `get_link_report`.

Or use the Inspector CLI without the UI:

```sh
inspect() { npx -y @modelcontextprotocol/inspector --cli http://127.0.0.1:8765/mcp --transport http "$@"; }
inspect --method tools/list
inspect --method tools/call --tool-name check_link --tool-arg url=https://paypa1-login.com
inspect --method tools/call --tool-name get_link_report --tool-arg job_id=<job_id>
inspect --method tools/call --tool-name check_message --tool-arg 'text=URGENT: buy a gift card and read me the code'
```

## How it's put together

| Module | Role |
|---|---|
| `app.py` | MCP tools, the stateless Streamable HTTP app, and protocol-version negotiation. |
| `netguard.py` | SSRF guard. Resolves DNS itself and rejects private, loopback, link-local, reserved, CGNAT, multicast and IPv4-embedded IPv6 addresses. If *any* DNS answer is private, the URL is rejected. Each fetch connects to the IP that was checked (Host header and TLS SNI keep the real name), so DNS rebinding can't swap the address afterwards. It never follows redirects itself. |
| `lookalike.py` | Loads `brands.json`. Punycode, brand look-alikes (confusable letters, digit swaps, `rn`→`m`, one-edit typos), brand names on unrelated domains, pages claiming a brand, shorteners, risky TLDs, `user@host` tricks. |
| `rdap.py` | Domain age through the IANA RDAP bootstrap, falling back to rdap.org. 300 ms timeout, in-memory cache (24 h for hits, 10 min for misses). |
| `sandbox.py` | Headless Chromium with a fresh context, 10 s budget, downloads off, service workers blocked, form submission disabled. |
| `linkcheck.py` | The `check_link` fast path, the in-memory job store and `get_link_report`. |
| `message.py` | Message rules and URL extraction. |
| `scoring.py` | Fixed weights and thresholds (≥ 60 is the top verdict, ≥ 25 is `Be careful`). The only place scores are set. |

**How the sandbox stays contained.** Chromium never makes a network request of its own. Every
request is intercepted and fetched in Python through `netguard`, so each redirect hop,
sub-resource and script-driven navigation gets the same checks. Only GET and HEAD requests are
allowed through, so form POSTs and beacons never leave the sandbox. As a backstop, Chromium is
pointed at a dead proxy with loopback bypass turned off, and WebRTC and WebSockets are disabled.
Anything that slipped past the interceptor would have nowhere to go.

One detail: Chromium follows a fulfilled 3xx response *without* routing the next hop back
through the interceptor. So the sandbox never gives the browser a redirect. It aborts main-frame
redirects and navigates to the next hop itself, and it follows sub-resource redirects in Python.

## Known limits (tonight's scope)

- Jobs and the RDAP cache live in process memory. They're lost on restart and not shared between
  workers, so run a single process.
- The registrable domain is worked out from a short list of two-level suffixes (`co.uk`,
  `com.au`, ...), not the full Public Suffix List.
- The brand list and message rules are small and English-only.
- Screenshots go to local disk. S3 comes later.
