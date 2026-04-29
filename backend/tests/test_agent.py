"""Tests for Agent Engine (agentic mode) with mocked LLM."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Conversation, ConversationMode, Message, MessageRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_conversation(db, user_id, mode="agentic", title="Agent Chat", **kwargs):
    conv = Conversation(user_id=user_id, title=title, mode=mode, **kwargs)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def _collect_events(gen):
    """Drain an async generator and return a list of event dicts."""
    events = []
    async for event in gen:
        events.append(event)
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_agentic_mode_no_tools(client, auth_header, test_user, db_session):
    """Agentic conversation where LLM returns no tool_calls — expect text + done events."""
    conv = await _create_conversation(db_session, test_user.id, mode="agentic")

    # Mock LLM to return a plain text response (no tool_calls)
    mock_response = {
        "choices": [
            {"message": {"role": "assistant", "content": "Hello from agent!"}}
        ]
    }

    mock_client = MagicMock()
    mock_client.chat = AsyncMock(return_value=mock_response)

    with patch("app.services.agent.llm_client", mock_client):
        events = await _collect_events(
            _agent_loop_direct(conv, "Hi", db_session, mock_client)
        )

    event_types = [e["event"] for e in events]
    assert "text" in event_types
    assert "done" in event_types

    # Verify text content
    text_events = [e for e in events if e["event"] == "text"]
    assert any("Hello from agent!" in e["data"] for e in text_events)

    # Verify done event has message_id
    done_events = [e for e in events if e["event"] == "done"]
    assert len(done_events) == 1
    done_data = json.loads(done_events[0]["data"])
    assert "message_id" in done_data


@pytest.mark.anyio
async def test_agentic_mode_with_tool_call(client, auth_header, test_user, db_session):
    """Agentic conversation where LLM calls a tool then returns final text."""
    conv = await _create_conversation(
        db_session, test_user.id, mode="agentic",
        enabled_tools=["web_search"],
    )

    call_count = 0

    async def mock_chat_side_effect(messages, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: LLM returns a tool_call
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Let me search for that.",
                            "tool_calls": [
                                {
                                    "id": "call_123",
                                    "type": "function",
                                    "function": {
                                        "name": "web_search",
                                        "arguments": json.dumps({"query": "test query"}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            }
        else:
            # Second call: LLM returns final text
            return {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Here is what I found: test results.",
                        }
                    }
                ]
            }

    mock_client = MagicMock()
    mock_client.chat = AsyncMock(side_effect=mock_chat_side_effect)

    # Also mock tool_registry.execute to return a known result
    with (
        patch("app.services.agent.llm_client", mock_client),
        patch("app.services.agent.tool_registry") as mock_registry,
    ):
        mock_registry.get_tool_schemas = AsyncMock(return_value=[
            {
                "type": "function",
                "function": {
                    "name": "web_search",
                    "description": "Search the web",
                    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
                },
            }
        ])
        mock_registry.execute = AsyncMock(return_value="Search result: found 3 items.")

        events = await _collect_events(
            _agent_loop_direct(conv, "Search for something", db_session, mock_client)
        )

    event_types = [e["event"] for e in events]
    assert "thinking" in event_types
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "text" in event_types
    assert "done" in event_types

    # Verify tool_call data
    tc_events = [e for e in events if e["event"] == "tool_call"]
    assert len(tc_events) == 1
    tc_data = json.loads(tc_events[0]["data"])
    assert tc_data["name"] == "web_search"
    assert tc_data["arguments"]["query"] == "test query"

    # Verify tool_result data
    tr_events = [e for e in events if e["event"] == "tool_result"]
    assert len(tr_events) == 1
    tr_data = json.loads(tr_events[0]["data"])
    assert "Search result" in tr_data["result"]


# ---------------------------------------------------------------------------
# Direct agent_loop helper (avoids going through the HTTP layer)
# ---------------------------------------------------------------------------


async def _agent_loop_direct(conversation, user_content, db, llm=None):
    """Call agent_loop directly for unit testing (bypasses HTTP)."""
    from app.services.agent import agent_loop

    async for event in agent_loop(conversation, user_content, db, llm=llm):
        yield event
