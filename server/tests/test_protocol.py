"""The MCP endpoint itself: stateless Streamable HTTP at /mcp, always negotiating 2025-11-25."""

import pytest
from starlette.testclient import TestClient

from server import app as app_module

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
    assert {t["name"] for t in resp.json()["result"]["tools"]} == {"check_link", "get_link_report", "check_message"}


def test_discover_says_method_not_found(client):
    """A 2026 client probing server/discover is told to fall back to initialize, not refused."""
    resp = rpc(client, "server/discover", version="2026-07-28")
    assert resp.status_code == 200
    assert resp.json()["error"]["code"] == -32601


def test_tools_listed(client):
    resp = rpc(client, "tools/list")
    names = {t["name"] for t in resp.json()["result"]["tools"]}
    assert names == {"check_link", "get_link_report", "check_message"}


def test_call_check_link_over_http(client, fake_dns, fake_rdap, no_sandbox):
    resp = rpc(client, "tools/call", {"name": "check_link", "arguments": {"url": "http://169.254.169.254/latest/meta-data/"}})
    result = resp.json()["result"]
    assert not result.get("isError")
    out = result["structuredContent"]
    assert set(out) == {"quick_verdict", "reasons", "job_id"}
    report = rpc(client, "tools/call", {"name": "get_link_report", "arguments": {"job_id": out["job_id"]}}, id=2)
    assert report.json()["result"]["structuredContent"]["status"] == "blocked"


def test_foreign_host_header_rejected(client):
    resp = client.post("/mcp", headers={**HEADERS, "Host": "evil.example"}, json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": init_params()})
    assert resp.status_code in (400, 421)
