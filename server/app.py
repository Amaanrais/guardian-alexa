"""Guardian MCP server: stateless Streamable HTTP at /mcp, protocol 2025-11-25."""

import asyncio
import contextlib
import json
import logging
import re
from typing import Any, Literal

import uvicorn
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp_types import ToolAnnotations
from pydantic import BaseModel, model_serializer
from starlette.requests import Request
from starlette.responses import FileResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import config, family, linkcheck, message, recovery
from .scoring import LinkVerdict

log = logging.getLogger(__name__)

mcp = MCPServer(
    name="guardian",
    instructions=(
        "Guardian helps people decide whether a link or message is a scam. Call check_link for a URL, "
        "then get_link_report with the job_id a few seconds later for the full result. Call check_message "
        "for a whole text or email. Relay verdicts as given; never tell the user something is safe. "
        "If someone says they already shared a code or clicked a link, call start_incident and then "
        "next_step one step at a time. To check a caller really is family, call verify_caller and poll "
        "get_verification. alert_family tells the family; never ask for passwords, codes, PINs or card numbers."
    ),
)

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
_SENDS = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)


class LinkCheck(BaseModel):
    quick_verdict: LinkVerdict
    reasons: list[str]
    job_id: str


class LinkReport(BaseModel):
    status: Literal["pending", "running", "done", "error"]
    verdict: LinkVerdict
    reasons: list[str]
    screenshot_path: str | None  # path on this server, e.g. /screens/<job_id>.png


class MessageCheck(BaseModel):
    verdict: LinkVerdict
    reasons: list[str]
    job_ids: list[str]  # one sandbox job per link found, for get_link_report


@mcp.tool(annotations=_READ_ONLY)
async def check_link(url: str) -> LinkCheck:
    """Quickly check a web link for scam warning signs and start a deeper background check.

    Returns a quick verdict now plus a job_id; pass it to get_link_report for the full result.
    """
    return LinkCheck.model_validate(await linkcheck.check_link(url))


@mcp.tool(annotations=_READ_ONLY)
async def get_link_report(job_id: str) -> LinkReport:
    """Get the full report for a link check started by check_link.

    Poll while status is pending or running; done and error are final.
    """
    return LinkReport.model_validate(linkcheck.get_link_report(job_id))


@mcp.tool(annotations=_READ_ONLY)
async def check_message(text: str) -> MessageCheck:
    """Check a text message or email for common scam red flags, including any links inside it."""
    return MessageCheck.model_validate(await message.check_message(text))


_SCREENSHOT_NAME = re.compile(r"^[A-Za-z0-9_-]{1,64}\.png$")


class _OmitNone(BaseModel):
    """Leaves unset optional fields out of the JSON, so shapes match docs/CONTRACT.md exactly."""

    @model_serializer(mode="wrap")
    def _omit_none(self, handler):
        return {k: v for k, v in handler(self).items() if v is not None}


class StepAction(BaseModel):
    label: str
    tool: str
    args: dict[str, Any] = {}


class Step(_OmitNone):
    text: str
    step_number: int  # 0 = a clarifying question, not a step
    total_steps: int
    action: StepAction | None = None


class IncidentStart(BaseModel):
    incident_id: str | None
    playbook_title: str | None
    step: Step


class NextStep(_OmitNone):
    step: Step | None = None
    done: bool | None = None
    summary: str | None = None


class VerificationStarted(BaseModel):
    verification_id: str
    status: Literal["waiting"]


class VerificationStatus(BaseModel):
    status: Literal["waiting", "confirmed", "denied", "no_reply"]


class FamilyAlert(BaseModel):
    sent: bool
    recipients: list[str]


@contextlib.contextmanager
def _spoken_errors():
    """Plain-language problems become MCP tool errors the harness can read out."""
    try:
        yield
    except (recovery.RecoveryError, family.FamilyError) as exc:
        raise ToolError(str(exc)) from None


@mcp.tool(annotations=_SENDS)
async def start_incident(description: str) -> IncidentStart:
    """Start step-by-step recovery after someone already shared a code or clicked a bad link.

    Describe what happened in their words. Returns step 1, or (step_number 0) one clarifying
    question to answer by calling start_incident again. Also tells the family.
    """
    with _spoken_errors():
        return IncidentStart.model_validate(await recovery.start_incident(description))


@mcp.tool(annotations=_SENDS)
async def next_step(incident_id: str) -> NextStep:
    """The next recovery step once the person has done the current one, or {done, summary} at the end."""
    with _spoken_errors():
        return NextStep.model_validate(await recovery.next_step(incident_id))


@mcp.tool(annotations=_SENDS)
async def verify_caller(name: str) -> VerificationStarted:
    """Ask a family member, by their first name, whether they are the one calling right now.

    Poll get_verification with the returned id about every 3 seconds.
    """
    with _spoken_errors():
        return VerificationStarted.model_validate(await family.verify_caller(name))


@mcp.tool(annotations=_READ_ONLY)
async def get_verification(id: str) -> VerificationStatus:  # noqa: A002 - name fixed by the contract
    """Whether the family member answered: waiting, confirmed, denied, or no_reply after 120 seconds."""
    with _spoken_errors():
        return VerificationStatus.model_validate(await family.get_verification(id))


@mcp.tool(annotations=_SENDS)
async def alert_family(reason: str) -> FamilyAlert:
    """Message everyone in the family circle with a short reason. Recipients are set on the server."""
    with _spoken_errors():
        return FamilyAlert.model_validate(await family.alert_family(reason))


@mcp.custom_route("/screens/{name}", methods=["GET"])
async def screenshot(request: Request) -> Response:
    """Serves sandbox screenshots. Names are unguessable job ids; nothing else is reachable."""
    name = request.path_params["name"]
    path = config.SCREENS_DIR / name
    if not _SCREENSHOT_NAME.match(name) or not path.is_file():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


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
    # Run the Telegram poller for as long as the server runs (not per request: the MCP side is stateless).
    sdk_lifespan = starlette_app.router.lifespan_context

    @contextlib.asynccontextmanager
    async def lifespan(app):
        async with sdk_lifespan(app) as state:
            poller = family.start_polling()
            try:
                yield state
            finally:
                if poller:
                    poller.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await poller

    starlette_app.router.lifespan_context = lifespan
    return ProtocolNegotiation(starlette_app)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    for handler in logging.getLogger().handlers:
        handler.addFilter(family.RedactToken())
    uvicorn.run(build_app(), host=config.HOST, port=config.PORT)


if __name__ == "__main__":
    main()
