"""Knowledge base CRUD endpoints."""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import (
    DocumentSource,
    DocumentStatus,
    KnowledgeBase,
    KnowledgeBaseScope,
    KnowledgeDocument,
    User,
)
from app.schemas.knowledge import (
    DocumentResponse,
    DocumentUploadResponse,
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
)

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


async def _get_kb_or_404(
    kb_id: uuid.UUID,
    db: AsyncSession,
) -> KnowledgeBase:
    """Fetch a knowledge base by ID or raise 404."""
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
    )
    kb = result.scalar_one_or_none()
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge base not found",
        )
    return kb


def _check_kb_permission(kb: KnowledgeBase, user: User) -> None:
    """Raise 403 if the user lacks permission to operate on this KB.

    Personal KBs require ownership. Department KBs require is_dept_admin.
    """
    if kb.scope == KnowledgeBaseScope.personal:
        if kb.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not the owner of this personal knowledge base",
            )
    elif kb.scope == KnowledgeBaseScope.department:
        if not user.is_dept_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only department admins can manage department knowledge bases",
            )


# ---------------------------------------------------------------------------
# Knowledge Base endpoints
# ---------------------------------------------------------------------------


@router.get("/bases", response_model=list[KnowledgeBaseResponse])
async def list_knowledge_bases(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return personal KBs owned by the user + department KBs matching user's department."""
    # Personal knowledge bases
    personal_q = select(KnowledgeBase).where(
        KnowledgeBase.scope == KnowledgeBaseScope.personal,
        KnowledgeBase.owner_id == user.id,
    )

    # Department knowledge bases visible to the user
    dept_q = select(KnowledgeBase).where(
        KnowledgeBase.scope == KnowledgeBaseScope.department,
        KnowledgeBase.department_id == user.department_id,
    )

    personal_result = await db.execute(personal_q)
    dept_result = await db.execute(dept_q)

    personal_kbs = list(personal_result.scalars().all())
    dept_kbs = list(dept_result.scalars().all())
    all_kbs = personal_kbs + dept_kbs

    # Annotate each KB with document_count
    result = []
    for kb in all_kbs:
        doc_count_result = await db.execute(
            select(func.count(KnowledgeDocument.id)).where(
                KnowledgeDocument.knowledge_base_id == kb.id
            )
        )
        doc_count = doc_count_result.scalar() or 0
        resp = KnowledgeBaseResponse.model_validate(kb)
        resp.document_count = doc_count
        result.append(resp)

    return result


@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new knowledge base.

    Personal: anyone can create. Department: only is_dept_admin.
    """
    scope = KnowledgeBaseScope(body.scope)

    if scope == KnowledgeBaseScope.department:
        if not user.is_dept_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only department admins can create department knowledge bases",
            )

    kb = KnowledgeBase(
        name=body.name,
        description=body.description,
        scope=scope,
        owner_id=user.id,
        department_id=body.department_id,
        embedding_model=body.embedding_model,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        milvus_collection=None,  # set below after id is assigned
    )
    db.add(kb)
    await db.flush()  # assign kb.id

    kb.milvus_collection = f"kb_{kb.id}"
    await db.commit()
    await db.refresh(kb)

    resp = KnowledgeBaseResponse.model_validate(kb)
    resp.document_count = 0
    return resp


@router.delete("/bases/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a knowledge base. Owner-only for personal, dept-admin for department."""
    kb = await _get_kb_or_404(kb_id, db)
    _check_kb_permission(kb, user)

    await db.delete(kb)
    await db.commit()


# ---------------------------------------------------------------------------
# Document endpoints
# ---------------------------------------------------------------------------


@router.post("/bases/{kb_id}/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    kb_id: uuid.UUID,
    file: UploadFile,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a document to a knowledge base."""
    kb = await _get_kb_or_404(kb_id, db)
    _check_kb_permission(kb, user)

    upload_dir = os.path.join("uploads", str(kb_id))
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc = KnowledgeDocument(
        knowledge_base_id=kb.id,
        source_type=DocumentSource.upload,
        title=file.filename,
        file_path=file_path,
        uploaded_by=user.id,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return DocumentUploadResponse(
        id=doc.id,
        title=doc.title,
        status=doc.status.value,
    )


@router.get("/bases/{kb_id}/documents", response_model=list[DocumentResponse])
async def list_documents(
    kb_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List documents in a knowledge base."""
    kb = await _get_kb_or_404(kb_id, db)
    _check_kb_permission(kb, user)

    result = await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.knowledge_base_id == kb.id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    return result.scalars().all()


@router.delete("/bases/{kb_id}/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    kb_id: uuid.UUID,
    doc_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document from a knowledge base."""
    kb = await _get_kb_or_404(kb_id, db)
    _check_kb_permission(kb, user)

    result = await db.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_id,
            KnowledgeDocument.knowledge_base_id == kb.id,
        )
    )
    doc = result.scalar_one_or_none()
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    await db.delete(doc)
    await db.commit()
