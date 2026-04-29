"""Tests for Knowledge Base CRUD API."""

import uuid
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token, hash_password
from app.models.department import Department
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseScope
from app.models.knowledge_document import DocumentSource, DocumentStatus, KnowledgeDocument
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _auth_header_for(user: User) -> dict:
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


async def _create_kb(db, *, owner, name="Test KB", scope="personal", department_id=None):
    kb = KnowledgeBase(
        name=name,
        description="A test knowledge base",
        scope=KnowledgeBaseScope(scope),
        owner_id=owner.id,
        department_id=department_id,
        embedding_model="text-embedding-ada-002",
        chunk_size=512,
        chunk_overlap=50,
        milvus_collection=f"kb_{uuid.uuid4()}",
    )
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    return kb


async def _create_user(db, *, username, is_dept_admin=False, department_id=None):
    user = User(
        username=username,
        password_hash=hash_password("password123"),
        display_name=username,
        department_id=department_id,
        position="Engineer",
        is_dept_admin=is_dept_admin,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_create_personal_knowledge_base(client, db_session):
    """Any authenticated user can create a personal knowledge base (201)."""
    user = await _create_user(db_session, username="creator")
    headers = _auth_header_for(user)

    payload = {
        "name": "My Personal KB",
        "description": "Some docs",
        "scope": "personal",
    }
    resp = await client.post("/api/knowledge/bases", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "My Personal KB"
    assert data["scope"] == "personal"
    assert data["owner_id"] == str(user.id)
    assert data["document_count"] == 0
    assert data["milvus_collection"] is not None
    assert data["milvus_collection"].startswith("kb_")


@pytest.mark.anyio
async def test_list_knowledge_bases(client, db_session):
    """User sees personal KBs + department KBs for their department."""
    dept = Department(name="Engineering")
    db_session.add(dept)
    await db_session.flush()

    owner = await _create_user(
        db_session, username="owner", department_id=dept.id, is_dept_admin=True
    )
    other = await _create_user(
        db_session, username="other", department_id=dept.id
    )

    # Create a personal KB for owner
    await _create_kb(db_session, owner=owner, name="Owner Personal", scope="personal")
    # Create a department KB
    await _create_kb(
        db_session,
        owner=owner,
        name="Dept KB",
        scope="department",
        department_id=dept.id,
    )
    # Create a personal KB for other user (should NOT appear for owner)
    await _create_kb(db_session, owner=other, name="Other Personal", scope="personal")

    await db_session.commit()

    headers = _auth_header_for(owner)
    resp = await client.get("/api/knowledge/bases", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    names = [kb["name"] for kb in data]
    assert "Owner Personal" in names
    assert "Dept KB" in names
    assert "Other Personal" not in names


@pytest.mark.anyio
async def test_delete_personal_knowledge_base(client, db_session):
    """Owner can delete their own personal KB (204)."""
    user = await _create_user(db_session, username="owner")
    kb = await _create_kb(db_session, owner=user, name="To Delete", scope="personal")
    await db_session.commit()

    headers = _auth_header_for(user)
    resp = await client.delete(f"/api/knowledge/bases/{kb.id}", headers=headers)
    assert resp.status_code == 204

    # Verify it's gone
    resp2 = await client.get("/api/knowledge/bases", headers=headers)
    assert all(kb_item["id"] != str(kb.id) for kb_item in resp2.json())


@pytest.mark.anyio
async def test_delete_personal_knowledge_base_not_owner(client, db_session):
    """Non-owner cannot delete a personal KB (403)."""
    owner = await _create_user(db_session, username="owner")
    other = await _create_user(db_session, username="other")
    kb = await _create_kb(db_session, owner=owner, name="Owner KB", scope="personal")
    await db_session.commit()

    headers = _auth_header_for(other)
    resp = await client.delete(f"/api/knowledge/bases/{kb.id}", headers=headers)
    assert resp.status_code == 403


@pytest.mark.anyio
async def test_upload_document(client, db_session):
    """Uploading a document creates a KnowledgeDocument record with status pending."""
    user = await _create_user(db_session, username="uploader")
    kb = await _create_kb(db_session, owner=user, name="Doc KB", scope="personal")
    await db_session.commit()

    headers = _auth_header_for(user)

    file_content = b"test document content"
    mock_file = MagicMock()
    mock_file.filename = "test.txt"
    mock_file.read.return_value = file_content
    mock_file.file = BytesIO(file_content)

    with patch("os.makedirs"):
        with patch("builtins.open", create=True):
            resp = await client.post(
                f"/api/knowledge/bases/{kb.id}/documents",
                files={"file": ("test.txt", BytesIO(file_content), "text/plain")},
                headers=headers,
            )

    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "test.txt"
    assert data["status"] == "pending"
    assert "id" in data


@pytest.mark.anyio
async def test_list_documents(client, db_session):
    """Listing documents returns documents belonging to the KB."""
    user = await _create_user(db_session, username="docowner")
    kb = await _create_kb(db_session, owner=user, name="Doc KB", scope="personal")

    doc1 = KnowledgeDocument(
        knowledge_base_id=kb.id,
        source_type=DocumentSource.upload,
        title="doc1.txt",
        uploaded_by=user.id,
        status=DocumentStatus.pending,
    )
    doc2 = KnowledgeDocument(
        knowledge_base_id=kb.id,
        source_type=DocumentSource.upload,
        title="doc2.txt",
        uploaded_by=user.id,
        status=DocumentStatus.ready,
    )
    db_session.add(doc1)
    db_session.add(doc2)
    await db_session.commit()

    headers = _auth_header_for(user)
    resp = await client.get(f"/api/knowledge/bases/{kb.id}/documents", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    titles = [d["title"] for d in data]
    assert "doc1.txt" in titles
    assert "doc2.txt" in titles
