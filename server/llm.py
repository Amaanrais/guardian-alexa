"""LLM provider setting (LLM_PROVIDER = bedrock | anthropic | openai | none). Interface only for now.

Nothing in the server calls an LLM yet; checks stay rule-based. Providers are filled in later.
"""

from typing import Protocol

from . import config

PROVIDERS = ("bedrock", "anthropic", "openai", "none")


class LLMProvider(Protocol):
    name: str

    async def complete(self, system: str, messages: list[dict]) -> str:
        """Return the model's reply to `messages` ([{role, content}]) under the `system` prompt."""
        ...


class _NotWiredYet:
    def __init__(self, name: str):
        self.name = name

    async def complete(self, system: str, messages: list[dict]) -> str:
        raise NotImplementedError(f"LLM_PROVIDER={self.name} isn't wired up yet")


def get_provider(name: str | None = None) -> LLMProvider | None:
    """The configured provider, or None for "none"."""
    name = (name or config.LLM_PROVIDER or "none").lower()
    if name not in PROVIDERS:
        raise ValueError(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}, not {name!r}")
    return None if name == "none" else _NotWiredYet(name)
