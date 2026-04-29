"""Conversation CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Conversation, Message, User
from app.schemas.conversation import (
    ConversationCreate,
    ConversationListResponse,
    ConversationResponse,
)

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


async def _get_user_conversation(
    conversation_id: uuid.UUID,
    user: User,
    db: AsyncSession,
) -> Conversation:
    """Fetch a conversation belonging to *user*, or raise 404."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )
    return conversation


@router.get("", response_model=list[ConversationListResponse])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List conversations for the current user, ordered by updated_at desc."""
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new conversation for the current user."""
    conversation = Conversation(
        user_id=user.id,
        title=body.title,
        mode=body.mode,
        skill_id=body.skill_id,
        knowledge_base_id=body.knowledge_base_id,
        enabled_tools=body.tool_ids,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single conversation by ID (must belong to current user)."""
    return await _get_user_conversation(conversation_id, user, db)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation and all its messages."""
    conversation = await _get_user_conversation(conversation_id, user, db)

    # Bulk-delete associated messages first
    await db.execute(
        delete(Message).where(Message.conversation_id == conversation.id)
    )

    await db.delete(conversation)
    await db.commit()
