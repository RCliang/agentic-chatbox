"""Tests for the OpenAI-compatible LLM client."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.llm import LLMClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_response(content: str = "Hello!") -> dict:
    """Build a minimal OpenAI-compatible chat completion response."""
    return {
        "id": "chatcmpl-abc123",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _fake_sse_chunks(text: str = "Hello!") -> list[str]:
    """Return a list of SSE lines mimicking an OpenAI stream response."""
    chunk = {
        "id": "chatcmpl-abc123",
        "object": "chat.completion.chunk",
        "choices": [
            {
                "index": 0,
                "delta": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
    }
    return [
        f"data: {json.dumps(chunk)}",
        "data: [DONE]",
    ]


# ---------------------------------------------------------------------------
# Non-streaming test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_non_streaming():
    """chat() sends the correct payload and returns the parsed response."""
    messages = [{"role": "user", "content": "Hi"}]
    fake_resp = _make_fake_response("Hello!")

    # Build a fake httpx.Response
    mock_response = httpx.Response(200, json=fake_resp)
    mock_response.request = MagicMock()

    client = LLMClient(base_url="https://api.example.com/v1", api_key="sk-test", default_model="gpt-4")

    with patch("app.services.llm.httpx.AsyncClient") as MockAsyncClient:
        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockAsyncClient.return_value = mock_instance

        result = await client.chat(messages)

    # Verify the POST was called with the correct URL and payload
    mock_instance.post.assert_called_once()
    call_args = mock_instance.post.call_args
    assert call_args[0][0] == "https://api.example.com/v1/chat/completions"
    sent_payload = call_args[1]["json"]
    assert sent_payload["model"] == "gpt-4"
    assert sent_payload["messages"] == messages
    assert sent_payload["temperature"] == 0.7
    assert sent_payload["max_tokens"] == 4096
    assert "stream" not in sent_payload

    # Verify returned content
    assert result["choices"][0]["message"]["content"] == "Hello!"


@pytest.mark.asyncio
async def test_chat_non_streaming_with_tools():
    """chat() includes tools in the payload when provided."""
    messages = [{"role": "user", "content": "What is the weather?"}]
    tools = [{"type": "function", "function": {"name": "get_weather", "parameters": {}}}]
    fake_resp = _make_fake_response("Sunny, 72F")

    mock_response = httpx.Response(200, json=fake_resp)
    mock_response.request = MagicMock()

    client = LLMClient(base_url="https://api.example.com/v1", api_key="sk-test", default_model="gpt-4")

    with patch("app.services.llm.httpx.AsyncClient") as MockAsyncClient:
        mock_instance = AsyncMock()
        mock_instance.post.return_value = mock_response
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockAsyncClient.return_value = mock_instance

        result = await client.chat(messages, tools=tools)

    sent_payload = mock_instance.post.call_args[1]["json"]
    assert sent_payload["tools"] == tools
    assert result["choices"][0]["message"]["content"] == "Sunny, 72F"


# ---------------------------------------------------------------------------
# Streaming test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_chat_streaming():
    """chat_stream() yields parsed SSE chunks from the stream."""
    messages = [{"role": "user", "content": "Hi"}]
    sse_lines = _fake_sse_chunks("Hello!")

    client = LLMClient(base_url="https://api.example.com/v1", api_key="sk-test", default_model="gpt-4")

    # We need to mock client.stream() which returns a context manager
    # whose __aenter__ gives an object with aiter_lines() and raise_for_status().
    with patch("app.services.llm.httpx.AsyncClient") as MockAsyncClient:
        mock_instance = AsyncMock()

        # Mock the stream context manager.
        # httpx's client.stream() is a regular (non-async) method that returns
        # an async context manager.  We use MagicMock (not AsyncMock) so the
        # return value is not auto-wrapped in a coroutine.
        mock_stream_response = MagicMock()
        mock_stream_response.raise_for_status = MagicMock()
        mock_stream_response.aiter_lines = MagicMock(return_value=AsyncIteratorWrapper(sse_lines))
        stream_cm = MagicMock()
        stream_cm.__aenter__ = AsyncMock(return_value=mock_stream_response)
        stream_cm.__aexit__ = AsyncMock(return_value=False)
        # Override the auto-created AsyncMock with a plain MagicMock
        type(mock_instance).stream = MagicMock(return_value=stream_cm)

        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        MockAsyncClient.return_value = mock_instance

        chunks = []
        async for chunk in client.chat_stream(messages):
            chunks.append(chunk)

    # Should have yielded exactly one parsed chunk (the [DONE] line is skipped)
    assert len(chunks) == 1
    assert chunks[0]["choices"][0]["delta"]["content"] == "Hello!"
    assert chunks[0]["choices"][0]["finish_reason"] == "stop"

    # Verify the stream POST was called correctly
    mock_instance.stream.assert_called_once()
    call_args = mock_instance.stream.call_args
    assert call_args[0][0] == "POST"
    assert call_args[0][1] == "https://api.example.com/v1/chat/completions"
    sent_payload = call_args[1]["json"]
    assert sent_payload["model"] == "gpt-4"
    assert sent_payload["messages"] == messages
    assert sent_payload["stream"] is True


# ---------------------------------------------------------------------------
# Minimal async iterator wrapper for mocking aiter_lines()
# ---------------------------------------------------------------------------


class AsyncIteratorWrapper:
    """Wraps a list of strings to behave like an async iterator."""

    def __init__(self, items: list[str]):
        self._items = items

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._items:
            raise StopAsyncIteration
        return self._items.pop(0)
