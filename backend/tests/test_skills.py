"""Tests for Skill CRUD API endpoints."""

import uuid

import pytest

from app.models import Skill


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_skill(db, *, name="Test Skill", is_builtin=False, **kwargs):
    skill = Skill(
        name=name,
        description="A test skill",
        system_prompt="You are a test assistant.",
        tool_ids=["web_search"],
        is_builtin=is_builtin,
        **kwargs,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_skill(client, auth_header):
    """POST /api/skills creates a new custom skill (201)."""
    payload = {
        "name": "My Skill",
        "description": "A custom skill",
        "system_prompt": "You are a custom assistant.",
        "tool_ids": ["web_search"],
    }
    resp = await client.post("/api/skills/", json=payload, headers=auth_header)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Skill"
    assert data["description"] == "A custom skill"
    assert data["system_prompt"] == "You are a custom assistant."
    assert data["tool_ids"] == ["web_search"]
    assert data["is_builtin"] is False
    assert "id" in data
    assert "created_at" in data


@pytest.mark.anyio
async def test_list_skills(client, auth_header, db_session):
    """GET /api/skills returns all skills."""
    await _create_skill(db_session, name="Skill A")
    await _create_skill(db_session, name="Skill B", is_builtin=True)

    resp = await client.get("/api/skills/", headers=auth_header)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    names = [s["name"] for s in data]
    assert "Skill A" in names
    assert "Skill B" in names


@pytest.mark.anyio
async def test_update_skill(client, auth_header, db_session):
    """PUT /api/skills/{id} performs partial update."""
    skill = await _create_skill(db_session, name="Original Name")

    payload = {"name": "Updated Name", "description": "New description"}
    resp = await client.put(
        f"/api/skills/{skill.id}", json=payload, headers=auth_header
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated Name"
    assert data["description"] == "New description"
    # system_prompt should remain unchanged
    assert data["system_prompt"] == "You are a test assistant."


@pytest.mark.anyio
async def test_delete_custom_skill(client, auth_header, db_session):
    """DELETE /api/skills/{id} deletes a custom skill (204)."""
    skill = await _create_skill(db_session, name="Deletable Skill")

    resp = await client.delete(
        f"/api/skills/{skill.id}", headers=auth_header
    )
    assert resp.status_code == 204

    # Verify it's gone
    resp2 = await client.get("/api/skills/", headers=auth_header)
    ids = [s["id"] for s in resp2.json()]
    assert str(skill.id) not in ids


@pytest.mark.anyio
async def test_delete_builtin_skill(client, auth_header, db_session):
    """DELETE /api/skills/{id} returns 403 for builtin skills."""
    skill = await _create_skill(db_session, name="Builtin Skill", is_builtin=True)

    resp = await client.delete(
        f"/api/skills/{skill.id}", headers=auth_header
    )
    assert resp.status_code == 403
