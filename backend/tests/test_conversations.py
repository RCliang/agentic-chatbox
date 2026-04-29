"""Tests for conversation CRUD endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_conversation(client: AsyncClient, auth_header: dict):
    """POST /api/conversations returns 201 with title and mode."""
    payload = {"title": "My Chat", "mode": "normal"}
    resp = await client.post("/api/conversations/", json=payload, headers=auth_header)

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "My Chat"
    assert data["mode"] == "normal"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_list_conversations(client: AsyncClient, auth_header: dict):
    """GET /api/conversations returns all conversations for the user."""
    # Create two conversations
    await client.post(
        "/api/conversations/", json={"title": "Chat A"}, headers=auth_header
    )
    await client.post(
        "/api/conversations/", json={"title": "Chat B"}, headers=auth_header
    )

    resp = await client.get("/api/conversations/", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_conversation(client: AsyncClient, auth_header: dict):
    """GET /api/conversations/{id} returns the conversation details."""
    create_resp = await client.post(
        "/api/conversations/", json={"title": "Detailed Chat"}, headers=auth_header
    )
    conv_id = create_resp.json()["id"]

    resp = await client.get(
        f"/api/conversations/{conv_id}", headers=auth_header
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Detailed Chat"
    assert data["id"] == conv_id


@pytest.mark.asyncio
async def test_get_conversation_not_found(client: AsyncClient, auth_header: dict):
    """GET /api/conversations/{id} returns 404 for non-existent id."""
    import uuid

    fake_id = str(uuid.uuid4())
    resp = await client.get(
        f"/api/conversations/{fake_id}", headers=auth_header
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient, auth_header: dict):
    """DELETE /api/conversations/{id} returns 204; subsequent GET returns 404."""
    create_resp = await client.post(
        "/api/conversations/", json={"title": "To Delete"}, headers=auth_header
    )
    conv_id = create_resp.json()["id"]

    delete_resp = await client.delete(
        f"/api/conversations/{conv_id}", headers=auth_header
    )
    assert delete_resp.status_code == 204

    get_resp = await client.get(
        f"/api/conversations/{conv_id}", headers=auth_header
    )
    assert get_resp.status_code == 404
