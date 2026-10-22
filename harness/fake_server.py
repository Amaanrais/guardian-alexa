"""Stand-in Guardian MCP server returning canned responses in the CONTRACT.md format.

    python harness/fake_server.py     # serves http://localhost:8000/mcp
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


@m.tool()
def check_link(url: str) -> dict:
    job = f"job{len(_jobs) + 1}"
    _jobs[job] = time.time()
    return {"quick_verdict": "Be careful", "reasons": ["Web address looks like a bank but isn't"], "job_id": job}


@m.tool()
def get_link_report(job_id: str) -> dict:
    if time.time() - _jobs.get(job_id, 0) < 3:
        return {"status": "running", "verdict": "Be careful", "reasons": [], "screenshot_path": None}
    return {"status": "done", "verdict": "Don't open this link",
            "reasons": ["Pretends to be your bank", "Website created 2 days ago", "Asks for your card PIN"],
            "screenshot_path": "https://placehold.co/640x360?text=Fake+bank+login"}


@m.tool()
def check_message(text: str) -> dict:
    return {"verdict": "Be careful", "reasons": ["Rushes you to act", "Asks for a code"], "job_ids": []}


@m.tool()
def verify_caller(name: str) -> dict:
    return {"verification_id": "ver1"}


@m.tool()
def get_verification(id: str) -> dict:
    return {"status": "denied"}


@m.tool()
def start_incident(description: str) -> dict:
    _incidents["inc1"] = 0
    return {"incident_id": "inc1", "step": STEPS[0]}


@m.tool()
def next_step(incident_id: str) -> dict:
    i = _incidents.get(incident_id, 0) + 1
    _incidents[incident_id] = i
    return {"step": STEPS[i]} if i < len(STEPS) else {"done": True}


@m.tool()
def alert_family(reason: str) -> dict:
    return {"sent": True}


if __name__ == "__main__":
    uvicorn.run(m.streamable_http_app(), port=8000, log_level="warning")
