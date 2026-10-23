"""LLM gateway for the agent: Bedrock, or any OpenAI-compatible API (Groq, OpenRouter, OpenAI, Ollama, ...).

    AGENT_PROVIDER  bedrock | groq | openrouter | openai | ollama | mock (default: mock, no LLM)
                    or any other name together with AGENT_BASE_URL
    AGENT_MODEL     model id for that provider, e.g. llama-3.3-70b-versatile, anthropic/claude-sonnet-4.5
    AGENT_API_KEY   API key (not needed for bedrock, which uses the AWS credentials, or ollama)
    AGENT_BASE_URL  overrides the preset, e.g. https://api.together.xyz/v1

Each provider keeps chat history in its own format; the agent only uses user(), complete() and results().
"""
import asyncio
import json
import os

import httpx

PRESETS = {
    "groq": "https://api.groq.com/openai/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "openai": "https://api.openai.com/v1",
    "ollama": "http://localhost:11434/v1",
}


def name() -> str:
    if os.getenv("USE_BEDROCK") == "1":  # the older switch still works
        return "bedrock"
    return (os.getenv("AGENT_PROVIDER") or "mock").strip().lower()


def model() -> str:
    if name() == "bedrock":
        return os.getenv("AGENT_MODEL") or os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
    return os.getenv("AGENT_MODEL", "")


class Bedrock:
    def __init__(self):
        import boto3
        self._client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
        self.model = model()

    def user(self, text: str) -> dict:
        return {"role": "user", "content": [{"text": text}]}

    async def complete(self, system: str, messages: list, tools: list[dict]):
        """Returns (assistant message to store, [(call_id, tool, args)], reply text)."""
        cfg = {"tools": [{"toolSpec": {"name": t["name"], "description": t["description"],
                                       "inputSchema": {"json": t["schema"]}}} for t in tools]}
        resp = await asyncio.to_thread(self._client.converse, modelId=self.model, system=[{"text": system}],
                                       messages=messages, toolConfig=cfg)
        msg = resp["output"]["message"]
        calls = [(b["toolUse"]["toolUseId"], b["toolUse"]["name"], b["toolUse"]["input"])
                 for b in msg["content"] if "toolUse" in b]
        return msg, calls, "".join(b.get("text", "") for b in msg["content"]).strip()

    def results(self, results: list[tuple[str, dict]]) -> list[dict]:
        return [{"role": "user", "content": [{"toolResult": {"toolUseId": cid, "content": [{"json": data}]}}
                                             for cid, data in results]}]


class OpenAICompatible:
    def __init__(self, provider: str, transport: httpx.AsyncBaseTransport | None = None):
        base = os.getenv("AGENT_BASE_URL") or PRESETS.get(provider)
        if not base:
            raise ValueError(f"AGENT_PROVIDER={provider} needs AGENT_BASE_URL (presets: {', '.join(PRESETS)})")
        self.model = model()
        if not self.model:
            raise ValueError(f"AGENT_PROVIDER={provider} needs AGENT_MODEL")
        key = os.getenv("AGENT_API_KEY", "")
        self._url = base.rstrip("/") + "/chat/completions"
        self._headers = {"Authorization": f"Bearer {key}"} if key else {}
        self._transport = transport

    def user(self, text: str) -> dict:
        return {"role": "user", "content": text}

    async def complete(self, system: str, messages: list, tools: list[dict]):
        body = {"model": self.model, "messages": [{"role": "system", "content": system}, *messages],
                "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"],
                                                            "parameters": t["schema"]}} for t in tools]}
        async with httpx.AsyncClient(timeout=60, transport=self._transport) as client:
            resp = await client.post(self._url, json=body, headers=self._headers)
        if resp.status_code != 200:
            # the body says why (bad key, unknown model, no tool support); never echo the key
            raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:300]}")
        msg = resp.json()["choices"][0]["message"]
        stored = {"role": "assistant", "content": msg.get("content") or ""}
        if msg.get("tool_calls"):
            stored["tool_calls"] = msg["tool_calls"]
        calls = [(c["id"], c["function"]["name"], json.loads(c["function"].get("arguments") or "{}"))
                 for c in msg.get("tool_calls") or []]
        return stored, calls, (msg.get("content") or "").strip()

    def results(self, results: list[tuple[str, dict]]) -> list[dict]:
        return [{"role": "tool", "tool_call_id": cid, "content": json.dumps(data)} for cid, data in results]


_provider = None


def provider():
    """The configured provider (built once), or None in mock mode."""
    global _provider
    if name() == "mock":
        return None
    if _provider is None:
        _provider = Bedrock() if name() == "bedrock" else OpenAICompatible(name())
    return _provider


if __name__ == "__main__":
    # Self-check of the OpenAI-compatible path against a fake server: python harness/llm.py
    def fake(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer k"
        assert body["model"] == "m" and body["messages"][0]["role"] == "system"
        assert body["tools"][0]["function"]["name"] == "check_link"
        if body["messages"][-1]["role"] == "tool":
            assert json.loads(body["messages"][-1]["content"]) == {"verdict": "Be careful"}
            return httpx.Response(200, json={"choices": [{"message": {"content": "Be careful with that link."}}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
            {"id": "c1", "type": "function", "function": {"name": "check_link", "arguments": '{"url": "http://x.co"}'}}]}}]})

    async def demo():
        os.environ.update(AGENT_PROVIDER="groq", AGENT_MODEL="m", AGENT_API_KEY="k")
        p = OpenAICompatible("groq", httpx.MockTransport(fake))
        tools = [{"name": "check_link", "description": "d", "schema": {"type": "object"}}]
        history = [p.user("is http://x.co a scam?")]
        msg, calls, _ = await p.complete("sys", history, tools)
        assert calls == [("c1", "check_link", {"url": "http://x.co"})]
        history += [msg, *p.results([("c1", {"verdict": "Be careful"})])]
        _, calls, reply = await p.complete("sys", history, tools)
        assert calls == [] and reply == "Be careful with that link."
        print("ok")

    asyncio.run(demo())
