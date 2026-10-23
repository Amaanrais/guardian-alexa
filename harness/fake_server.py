"""Stand-in Guardian MCP server returning canned responses in the CONTRACT.md format.

    python harness/fake_server.py     # serves http://localhost:8765/mcp

No browser, no Telegram. The real server with TELEGRAM_FAKE=1 is closer to the demo.
"""
import time

import uvicorn
from mcp.server.mcpserver import MCPServer

m = MCPServer("guardian-fake")
_jobs: dict[str, float] = {}
STEPS = ["Call your bank using the number on the back of your card.",
         "Ask them to block your card and any transfers.",
         "Change the password of the account you were using."]
_incidents: dict[str, int] = {}


def _step(i: int) -> dict:
    return {"text": STEPS[i], "step_number": i + 1, "total_steps": len(STEPS)}


@m.tool()
def check_link(url: str) -> dict:
    job = f"job{len(_jobs) + 1}"
    _jobs[job] = time.time()
    return {"quick_verdict": "Be careful", "reasons": ["The web address imitates nordbank.example but isn't the real site."],
            "job_id": job}


@m.tool()
def get_link_report(job_id: str) -> dict:
    if job_id not in _jobs:
        return {"status": "error", "verdict": "Be careful", "reasons": ["We don't have a report for this check."],
                "screenshot_path": None}
    if time.time() - _jobs[job_id] < 3:
        return {"status": "running", "verdict": "Be careful", "reasons": ["We're still opening the page to look closer."],
                "screenshot_path": None}
    return {"status": "done", "verdict": "Don't open this link",
            "reasons": ["The page says it's NordBank, but it isn't on nordbank.example, and it asks for private details.",
                        "This website was only set up 2 days ago.", "The page asks for a PIN."],
            "screenshot_path": "https://placehold.co/640x360?text=Fake+bank+login"}


@m.tool()
def check_message(text: str) -> dict:
    return {"verdict": "Be careful", "job_ids": [],
            "reasons": ["It pressures you to act quickly.", "It asks for a security code or PIN. Never share these with anyone."]}


@m.tool()
def verify_caller(name: str) -> dict:
    return {"verification_id": "ver1", "status": "waiting"}


@m.tool()
def get_verification(id: str) -> dict:
    return {"status": "denied"}


@m.tool()
def start_incident(description: str) -> dict:
    _incidents["inc1"] = 0
    return {"incident_id": "inc1", "playbook_title": "I gave someone my code / OTP / PIN", "step": _step(0)}


@m.tool()
def next_step(incident_id: str) -> dict:
    i = _incidents.get(incident_id, 0) + 1
    _incidents[incident_id] = i
    return {"step": _step(i)} if i < len(STEPS) else {"done": True, "summary": f"You finished all {len(STEPS)} steps."}


@m.tool()
def alert_family(reason: str) -> dict:
    return {"sent": True, "recipients": ["Rahul"]}


@m.tool()
def get_family_circle() -> dict:
    return {"members": [{"name": "Rahul"}]}


if __name__ == "__main__":
    uvicorn.run(m.streamable_http_app(), port=8765, log_level="warning")
