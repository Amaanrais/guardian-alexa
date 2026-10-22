import pytest

from server import config, llm


def test_default_is_none():
    assert config.LLM_PROVIDER == "none" or config.LLM_PROVIDER in llm.PROVIDERS
    assert llm.get_provider("none") is None


@pytest.mark.parametrize("name", ["bedrock", "anthropic", "openai"])
@pytest.mark.anyio
async def test_providers_are_stubs_for_now(name):
    provider = llm.get_provider(name)
    assert provider.name == name
    with pytest.raises(NotImplementedError):
        await provider.complete("system", [{"role": "user", "content": "hi"}])


def test_unknown_provider():
    with pytest.raises(ValueError, match="LLM_PROVIDER must be one of"):
        llm.get_provider("gpt-9")


@pytest.fixture
def anyio_backend():
    return "asyncio"
