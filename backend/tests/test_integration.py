"""Full flow: login -> create conversation -> send message -> get messages -> delete."""
from unittest.mock import MagicMock, patch

from httpx import AsyncClient


async def _mock_chat_stream(messages):
    """Async generator that yields fake LLM SSE chunks."""
    yield {"choices": [{"delta": {"content": "Integration OK"}, "finish_reason": None}]}
    yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}


async def test_full_normal_chat_flow(client: AsyncClient, test_user, db_session):
    """Exercise the entire normal-mode chat lifecycle end-to-end."""

    # 1. Login
    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "testuser", "password": "password123"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get current user
    me_resp = await client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "testuser"

    # 3. Create conversation
    conv_resp = await client.post(
        "/api/conversations/",
        json={"title": "Integration Test", "mode": "normal"},
        headers=headers,
    )
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # 4. List conversations
    list_resp = await client.get("/api/conversations/", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 5. Send message (mock LLM)
    mock_client = MagicMock()
    mock_client.chat_stream = _mock_chat_stream

    with patch("app.services.chat.llm_client", mock_client):
        send_resp = await client.post(
            "/api/chat/send",
            json={"conversation_id": conv_id, "content": "Test message"},
            headers=headers,
        )
        assert send_resp.status_code == 200
        assert "Integration OK" in send_resp.text

    # 6. Get messages
    msg_resp = await client.get(
        f"/api/chat/conversations/{conv_id}/messages",
        headers=headers,
    )
    assert msg_resp.status_code == 200
    messages = msg_resp.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # 7. Delete conversation
    del_resp = await client.delete(
        f"/api/conversations/{conv_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # 8. Verify deleted
    get_resp = await client.get(
        f"/api/conversations/{conv_id}",
        headers=headers,
    )
    assert get_resp.status_code == 404
