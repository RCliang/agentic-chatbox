"""Tests for JWT authentication endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, test_user):
    """POST /api/auth/login with correct credentials returns a JWT."""
    resp = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "password123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, test_user):
    """POST /api/auth/login with wrong password returns 401."""
    resp = await client.post("/api/auth/login", json={
        "username": "testuser",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(client: AsyncClient):
    """POST /api/auth/login with unknown username returns 401."""
    resp = await client.post("/api/auth/login", json={
        "username": "nonexistent",
        "password": "whatever",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_header):
    """GET /api/auth/me with valid token returns the current user."""
    resp = await client.get("/api/auth/me", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "testuser"
    assert data["display_name"] == "Test User"
    assert data["position"] == "Engineer"
    assert data["is_dept_admin"] is False


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    """GET /api/auth/me without a token returns 401."""
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
