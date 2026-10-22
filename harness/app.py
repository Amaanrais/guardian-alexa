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


@app.get("/api/health")
async def health():
    url = os.getenv("MCP_URL", "http://localhost:8000/mcp")
    try:
        async with asyncio.timeout(3):
            async with connect(url) as client:
                tools = len((await client.list_tools()).tools)
    except Exception:
        tools = None
    return {"mcp_url": url, "mcp_ok": tools is not None, "tools": tools,
            "mode": "bedrock" if os.getenv("USE_BEDROCK") == "1" else "mock"}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
