"""Thin wrapper over the official MCP Python SDK client (Streamable HTTP)."""
import json
from contextlib import asynccontextmanager

from mcp import Client


@asynccontextmanager
async def connect(url: str):
    async with Client(url) as client:
        yield client


def tool_specs(tools) -> list[dict]:
    return [{"name": t.name, "description": t.description or "", "schema": t.input_schema}
            for t in tools]


def parse_result(result) -> dict:
    """Prefer structured content; otherwise parse the first JSON text block."""
    if getattr(result, "structured_content", None):
        return dict(result.structured_content)
    for block in result.content or []:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                return data if isinstance(data, dict) else {"result": data}
            except ValueError:
                return {"text": text}
    return {}
