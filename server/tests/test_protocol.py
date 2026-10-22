"""The MCP endpoint itself: stateless Streamable HTTP at /mcp, always negotiating 2025-11-25."""

import pytest
from starlette.testclient import TestClient

from server import app as app_module
from server import config

ALL_TOOLS = {"check_link", "get_link_report", "check_message", "verify_caller", "get_verification",
             "start_incident", "next_step", "alert_family"}
HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
def client():
    with TestClient(app_module.build_app(), base_url="http://127.0.0.1:8765") as c:
        yield c


def rpc(client, method, params=None, *, version="2025-11-25", id=1):
    headers = dict(HEADERS)
    if version and method != "initialize":
        headers["MCP-Protocol-Version"] = version
    return client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": id, "method": method, "params": params or {}})


def init_params(version="2025-11-25"):
    return {"protocolVersion": version, "capabilities": {}, "clientInfo": {"name": "pytest", "version": "0"}}


def test_initialize_negotiates_2025_11_25(client):
    resp = rpc(client, "initialize", init_params())
    assert resp.status_code == 200
    assert resp.json()["result"]["protocolVersion"] == "2025-11-25"
    assert "mcp-session-id" not in resp.headers  # stateless


def test_client_proposing_2026_gets_2025_11_25(client):
    resp = rpc(client, "initialize", init_params("2026-07-28"))
    assert resp.status_code == 200
    assert resp.json()["result"]["protocolVersion"] == "2025-11-25"


@pytest.mark.parametrize("version", ["2024-11-05", "2025-06-18", "1999-01-01", "not-a-version"])
def test_any_proposed_version_gets_2025_11_25(client, version):
    resp = rpc(client, "initialize", init_params(version))
    assert resp.status_code == 200
    assert resp.json()["result"]["protocolVersion"] == "2025-11-25"


@pytest.mark.parametrize("version", ["2025-06-18", "2026-07-28"])
def test_other_version_headers_are_served_not_rejected(client, version):
    resp = rpc(client, "tools/list", version=version)
    assert resp.status_code == 200
    assert {t["name"] for t in resp.json()["result"]["tools"]} == ALL_TOOLS


def test_discover_says_method_not_found(client):
    """A 2026 client probing server/discover is told to fall back to initialize, not refused."""
    resp = rpc(client, "server/discover", version="2026-07-28")
    assert resp.status_code == 200
    assert resp.json()["error"]["code"] == -32601


def test_tools_listed(client):
    resp = rpc(client, "tools/list")
    names = {t["name"] for t in resp.json()["result"]["tools"]}
    assert names == ALL_TOOLS


def test_call_check_link_over_http(client, fake_dns, fake_rdap, no_sandbox):
    resp = rpc(client, "tools/call", {"name": "check_link", "arguments": {"url": "http://169.254.169.254/latest/meta-data/"}})
    result = resp.json()["result"]
    assert not result.get("isError")
    out = result["structuredContent"]
    assert set(out) == {"quick_verdict", "reasons", "job_id"}
    report = rpc(client, "tools/call", {"name": "get_link_report", "arguments": {"job_id": out["job_id"]}}, id=2)
    report = report.json()["result"]["structuredContent"]
    assert report["status"] == "done"  # refused up front is a finished check, so the harness stops polling
    assert set(report) == {"status", "verdict", "reasons", "screenshot_path"}


def test_call_check_message_matches_contract(client, fake_dns, fake_rdap, no_sandbox):
    fake_dns["paypa1.com"] = ["93.184.215.14"]
    text = "Your account is locked, act now: https://paypa1.com/verify"
    resp = rpc(client, "tools/call", {"name": "check_message", "arguments": {"text": text}})
    out = resp.json()["result"]["structuredContent"]
    assert set(out) == {"verdict", "reasons", "job_ids"}
    assert out["verdict"] in ("Don't open this link", "Be careful", "No red flags found")
    assert len(out["job_ids"]) == 1


def test_screenshots_are_served(client, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "SCREENS_DIR", tmp_path)
    (tmp_path / "abc_DEF-123.png").write_bytes(b"\x89PNG fake")
    (tmp_path / "notes.txt").write_text("secret")
    resp = client.get("/screens/abc_DEF-123.png")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    for bad in ["missing.png", "notes.txt", "..%2Fconfig.py", "..%2F..%2F.env", "%2Fetc%2Fpasswd"]:
        assert client.get(f"/screens/{bad}").status_code == 404, bad


def test_foreign_host_header_rejected(client):
    resp = client.post("/mcp", headers={**HEADERS, "Host": "evil.example"}, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": init_params()})
    assert resp.status_code in (400, 421)


def call(client, tool, args, id=1):
    return rpc(client, "tools/call", {"name": tool, "arguments": args}, id=id).json()["result"]


def test_recovery_tools_over_http(client):
    start = call(client, "start_incident", {"description": "I gave someone my code"})["structuredContent"]
    assert set(start) == {"incident_id", "playbook_title", "step"}
    assert set(start["step"]) == {"text", "step_number", "total_steps"}  # no action on step 1: key omitted
    steps = [call(client, "next_step", {"incident_id": start["incident_id"]})["structuredContent"] for _ in range(3)]
    assert [set(s) for s in steps] == [{"step"}, {"step"}, {"done", "summary"}]

    ask = call(client, "start_incident", {"description": "something odd happened"})["structuredContent"]
    assert ask["incident_id"] is None and ask["step"]["step_number"] == 0


def test_family_tools_over_http(client):
    started = call(client, "verify_caller", {"name": "Rahul"})["structuredContent"]
    assert started["status"] == "waiting" and started["verification_id"]
    assert call(client, "get_verification", {"id": started["verification_id"]})["structuredContent"] == {"status": "waiting"}
    assert call(client, "alert_family", {"reason": "test"})["structuredContent"] == {"sent": True, "recipients": ["Rahul"]}


def test_spoken_errors_are_tool_errors(client):
    res = call(client, "verify_caller", {"name": "Zed"})
    assert res["isError"] is True
    assert "I don't have Zed in your family circle yet." in res["content"][0]["text"]
    res = call(client, "next_step", {"incident_id": "nope"})
    assert res["isError"] is True and "can't find that recovery" in res["content"][0]["text"]
