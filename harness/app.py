import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

load_dotenv(Path(__file__).parent.parent / ".env")
import agent  # noqa: E402  (after load_dotenv so env is set)

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
    return {"mcp_url": os.getenv("MCP_URL", "http://localhost:8765/mcp"),
            "mode": "bedrock" if os.getenv("USE_BEDROCK") == "1" else "mock"}


@app.get("/")
async def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
