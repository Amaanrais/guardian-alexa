import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).parent.parent / ".env")
import agent  # noqa: E402  (after load_dotenv so env is set)
import history  # noqa: E402
import weather  # noqa: E402
from card import FAMILY_CIRCLE  # noqa: E402
from mcp_client import connect  # noqa: E402

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="Guardian harness")


class Chat(BaseModel):
    session_id: str = "default"
    message: str


class Action(BaseModel):
    session_id: str = "default"
    tool: str
    args: dict = {}


@app.post("/api/chat")
async def chat(body: Chat):
    return await agent.respond(body.session_id, body.message)


@app.post("/api/action")
async def action(body: Action):
    return await agent.act(body.session_id, body.tool, body.args)


def _mcp_url() -> str:
    return os.getenv("MCP_URL", "http://localhost:8765/mcp")


async def _tool_names() -> list[str] | None:
    """The MCP server's tool names, or None if it can't be reached within 3 s."""
    try:
        async with asyncio.timeout(3):
            async with connect(_mcp_url()) as client:
                return [t.name for t in (await client.list_tools()).tools]
    except Exception:
        return None


@app.get("/api/health")
async def health():
    tools = await _tool_names()
    return {"mcp_url": _mcp_url(), "mcp_ok": tools is not None, "tools": len(tools) if tools is not None else None,
            "mode": "bedrock" if os.getenv("USE_BEDROCK") == "1" else "mock"}


@app.get("/api/home")
async def home():
    """Data for the home screen cards. "Ready to verify calls" is only claimed when the server can."""
    tools = await _tool_names()
    return {**history.summary(),
            "family": [{"name": n, "initial": n[0]} for n in FAMILY_CIRCLE],
            "mcp_ok": tools is not None,
            "verify_ready": bool(tools and "verify_caller" in tools)}


@app.get("/api/weather")
async def current_weather():
    """Top-bar weather (WEATHER_LAT / WEATHER_LON, default London); null if unavailable."""
    return await weather.current()


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


@app.get("/demo")
async def demo():
    """Every card state with fake data, for screenshots and the video."""
    return FileResponse(STATIC / "demo.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
