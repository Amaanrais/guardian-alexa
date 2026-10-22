"""Guardian MCP server: stateless Streamable HTTP at /mcp, protocol 2025-11-25."""

import json
import logging
from typing import Literal

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import BaseModel
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import config, linkcheck, message
from .scoring import LinkVerdict, MessageVerdict

log = logging.getLogger(__name__)

mcp = MCPServer(
    name="guardian",
    instructions=(
        "Guardian helps people decide whether a link or message is a scam. Call check_link for a URL, "
        "then get_link_report with the job_id a few seconds later for the full result. Call check_message "
        "for a whole text or email. Relay verdicts as given; never tell the user something is safe."
    ),
)

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


class LinkCheck(BaseModel):
    quick_verdict: LinkVerdict
    reasons: list[str]
    job_id: str


class LinkReport(BaseModel):
    status: Literal["pending", "running", "done", "blocked", "not_found"]
    verdict: LinkVerdict
    reasons: list[str]
    screenshot_path: str | None


class MessageLink(LinkCheck):
    url: str


class MessageCheck(BaseModel):
    verdict: MessageVerdict
    reasons: list[str]
    links: list[MessageLink]


@mcp.tool(annotations=_READ_ONLY)
async def check_link(url: str) -> LinkCheck:
    """Quickly check a web link for scam warning signs and start a deeper background check.

    Returns a quick verdict now plus a job_id; pass it to get_link_report for the full result.
    """
    return LinkCheck.model_validate(await linkcheck.check_link(url))


@mcp.tool(annotations=_READ_ONLY)
async def get_link_report(job_id: str) -> LinkReport:
    """Get the full report for a link check started by check_link. Poll until status is not pending/running."""
    return LinkReport.model_validate(linkcheck.get_link_report(job_id))


@mcp.tool(annotations=_READ_ONLY)
async def check_message(text: str) -> MessageCheck:
    """Check a text message or email for common scam red flags, including any links inside it."""
    return MessageCheck.model_validate(await message.check_message(text))


class ProtocolNegotiation:
    """Makes every client end up on config.PROTOCOL_VERSION, without rejecting anyone.

    `initialize` is answered with PROTOCOL_VERSION whatever the client proposed (the SDK would
    otherwise agree to older revisions it knows). Any other MCP-Protocol-Version header is
    rewritten to PROTOCOL_VERSION, so requests are always handled as 2025-11-25; for a 2026
    client that means `server/discover` gets "method not found", its cue to fall back to
    `initialize`.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        version = config.PROTOCOL_VERSION.encode()
        headers = [(k, version if k.lower() == b"mcp-protocol-version" else v) for k, v in scope["headers"]]
        scope = {**scope, "headers": headers}
        if scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        while True:
            msg = await receive()
            if msg["type"] == "http.disconnect":
                return
            chunks.append(msg.get("body", b""))
            if not msg.get("more_body"):
                break
        body = b"".join(chunks)
        rewritten = self._rewrite_initialize(body)
        if rewritten is not None:
            body = rewritten
            scope["headers"] = [(k, v) for k, v in headers if k.lower() != b"content-length"]
            scope["headers"].append((b"content-length", str(len(body)).encode()))

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    def _rewrite_initialize(body: bytes) -> bytes | None:
        """Body with every initialize's protocolVersion set to PROTOCOL_VERSION, or None if unchanged."""
        try:
            payload = json.loads(body)
        except ValueError:
            return None
        changed = False
        for item in payload if isinstance(payload, list) else [payload]:
            if isinstance(item, dict) and item.get("method") == "initialize" and isinstance(item.get("params"), dict):
                if item["params"].get("protocolVersion") != config.PROTOCOL_VERSION:
                    item["params"]["protocolVersion"] = config.PROTOCOL_VERSION
                    changed = True
        return json.dumps(payload).encode() if changed else None


def build_app() -> ASGIApp:
    security = None
    if config.ALLOWED_HOSTS:
        security = TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=config.ALLOWED_HOSTS,
            allowed_origins=[f"https://{h}" for h in config.ALLOWED_HOSTS],
        )
    elif config.HOST not in ("127.0.0.1", "localhost", "::1"):
        log.warning("GUARDIAN_ALLOWED_HOSTS is empty while binding %s: DNS-rebinding protection is off", config.HOST)
    starlette_app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        transport_security=security,
        host=config.HOST,
    )
    return ProtocolNegotiation(starlette_app)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(build_app(), host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
