"""Tests for Normal mode chat with SSE streaming."""

from unittest.mock import AsyncMock, MagicMock, patch

from app.models import Conversation, Message, MessageRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_conversation(db, user_id, mode="normal", title="Test Chat"):
    conv = Conversation(user_id=user_id, title=title, mode=mode)
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


async def _create_message(db, conversation_id, role, content):
    msg = Message(conversation_id=conversation_id, role=role, content=content)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def _mock_chat_stream(messages):
    """Async generator that yields fake LLM SSE chunks."""
    yield {"choices": [{"delta": {"content": "Hello!"}}]}
    yield {"choices": [{"delta": {}}]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_send_message_returns_sse(client, auth_header, test_user, db_session):
    """POST /api/chat/send streams SSE events with text + done."""
    conv = await _create_conversation(db_session, test_user.id)

    mock_client = MagicMock()
    mock_client.chat_stream = _mock_chat_stream

    with patch("app.services.chat.llm_client", mock_client):
        resp = await client.post(
            "/api/chat/send",
            json={"conversation_id": str(conv.id), "content": "Hi"},
            headers=auth_header,
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/event-stream; charset=utf-8"

    body = resp.text
    assert "event: text" in body
    assert "event: done" in body
    # Verify the streamed content appears in the SSE data
    assert "Hello!" in body


async def test_send_message_not_found(client, auth_header):
    """POST /api/chat/send with a non-existent conversation returns 404."""
    import uuid

    fake_id = str(uuid.uuid4())
    resp = await client.post(
        "/api/chat/send",
        json={"conversation_id": fake_id, "content": "Hi"},
        headers=auth_header,
    )
    assert resp.status_code == 404


async def test_get_messages(client, auth_header, test_user, db_session):
    """GET /api/chat/conversations/{id}/messages returns message history."""
    conv = await _create_conversation(db_session, test_user.id)
    await _create_message(db_session, conv.id, MessageRole.user, "Hello")
    await _create_message(db_session, conv.id, MessageRole.assistant, "Hi there!")

    resp = await client.get(
        f"/api/chat/conversations/{conv.id}/messages",
        headers=auth_header,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["role"] == "user"
    assert data[0]["content"] == "Hello"
    assert data[1]["role"] == "assistant"
    assert data[1]["content"] == "Hi there!"
