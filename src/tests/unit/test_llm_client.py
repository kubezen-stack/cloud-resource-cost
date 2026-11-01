import json

import httpx
import pytest

from app.core.config import settings
from app.services.llm_client import (
    LLMError,
    LLMNotConfigured,
    OpenAICompatibleClient,
    get_llm_client,
)


def make_client(handler):
    return OpenAICompatibleClient(
        api_key="secret-key",
        base_url="https://llm.test/v1",
        model="chat-model",
        embedding_model="embed-model",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_complete_json_sends_json_mode_and_returns_content():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"ok": true}'}}]})

    answer = await make_client(handler).complete_json("system text", "user text")

    assert answer == '{"ok": true}'
    assert seen["url"] == "https://llm.test/v1/chat/completions"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"]["model"] == "chat-model"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]


@pytest.mark.asyncio
async def test_embed_returns_vectors_in_input_order():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [
            {"index": 1, "embedding": [2.0]},
            {"index": 0, "embedding": [1.0]},
        ]})

    assert await make_client(handler).embed(["a", "b"]) == [[1.0], [2.0]]


@pytest.mark.asyncio
async def test_embed_nothing_makes_no_request():
    def handler(request):
        raise AssertionError("no request expected")

    assert await make_client(handler).embed([]) == []


@pytest.mark.asyncio
async def test_http_error_raises_llm_error_without_leaking_body():
    def handler(request):
        return httpx.Response(401, json={"error": "invalid key sk-leaked"})

    with pytest.raises(LLMError) as error:
        await make_client(handler).complete_json("s", "u")

    assert "401" in str(error.value)
    assert "sk-leaked" not in str(error.value)


@pytest.mark.asyncio
async def test_network_failure_raises_llm_error():
    def handler(request):
        raise httpx.ConnectError("boom")

    with pytest.raises(LLMError):
        await make_client(handler).embed(["a"])


@pytest.mark.asyncio
async def test_unexpected_payload_raises_llm_error():
    def handler(request):
        return httpx.Response(200, json={"unexpected": 1})

    client = make_client(handler)
    with pytest.raises(LLMError):
        await client.complete_json("s", "u")
    with pytest.raises(LLMError):
        await client.embed(["a"])


@pytest.mark.asyncio
async def test_embedding_count_mismatch_raises_llm_error():
    def handler(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0]}]})

    with pytest.raises(LLMError):
        await make_client(handler).embed(["a", "b"])


def test_get_llm_client_requires_api_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "")
    with pytest.raises(LLMNotConfigured):
        get_llm_client()


def test_get_llm_client_rejects_unknown_provider(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "key")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "mystery")
    with pytest.raises(LLMNotConfigured):
        get_llm_client()


def test_get_llm_client_builds_openai_client(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", "key")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    client = get_llm_client()
    assert client.model == settings.LLM_MODEL
    assert client.embedding_model == settings.EMBEDDING_MODEL
