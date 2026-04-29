"""Chat endpoints: send messages (SSE streaming) and retrieve history."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Conversation, Message, User
from app.schemas.message import ChatSendRequest, MessageResponse
from app.services.agent import agent_loop
from app.services.chat import normal_chat_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/send")
async def send_message(
    body: ChatSendRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send a user message and stream the assistant reply via SSE.

    Supports both ``normal`` and ``agentic`` conversation modes.
    """
    conv_uuid = uuid.UUID(body.conversation_id)
    stmt = select(Conversation).where(
        Conversation.id == conv_uuid,
        Conversation.user_id == user.id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if conversation.mode == "agentic":
        stream_fn = lambda: agent_loop(conversation, body.content, db)
    else:
        stream_fn = lambda: normal_chat_stream(conversation, body.content, db)

    async def event_generator():
        async for event in stream_fn():
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all messages for a conversation (must belong to current user)."""
    conv_uuid = uuid.UUID(conversation_id)
    stmt = select(Conversation).where(
        Conversation.id == conv_uuid,
        Conversation.user_id == user.id,
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conv_uuid)
        .order_by(Message.created_at.asc())
    )
    msg_result = await db.execute(msg_stmt)
    return [MessageResponse.model_validate(m) for m in msg_result.scalars().all()]
