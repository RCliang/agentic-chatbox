"""Core chat service for normal-mode conversations with SSE streaming."""

import json
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole
from app.services.llm import LLMClient, llm_client

DEFAULT_SYSTEM_PROMPT = "You are a helpful AI assistant."


async def get_conversation_messages(
    db: AsyncSession, conversation_id, limit: int = 50
):
    """Return the most recent *limit* messages for a conversation, oldest first."""
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def build_messages_for_llm(
    history: list[Message], system_prompt: str, user_content: str
) -> list[dict]:
    """Convert DB message history into the OpenAI-compatible messages list."""
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        if msg.role == MessageRole.user:
            messages.append({"role": "user", "content": msg.content or ""})
        elif msg.role == MessageRole.assistant:
            messages.append({"role": "assistant", "content": msg.content or ""})
    messages.append({"role": "user", "content": user_content})
    return messages


async def normal_chat_stream(
    conversation: Conversation,
    user_content: str,
    db: AsyncSession,
    llm: LLMClient | None = None,
) -> AsyncIterator[dict]:
    """Stream a normal-mode chat.  Yields SSE event dicts.

    Each yielded dict has keys ``event`` (str) and ``data`` (str).
    """
    client = llm or llm_client

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=user_content,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Build history (exclude the user msg we just saved so it isn't doubled)
    history = await get_conversation_messages(db, conversation.id, limit=50)
    llm_messages = build_messages_for_llm(
        history[:-1], DEFAULT_SYSTEM_PROMPT, user_content
    )

    # Stream from LLM
    full_content = ""
    async for chunk in client.chat_stream(llm_messages):
        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        content = delta.get("content", "")
        if content:
            full_content += content
            yield {"event": "text", "data": json.dumps({"content": content})}

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=full_content,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    yield {
        "event": "done",
        "data": json.dumps({"message_id": str(assistant_msg.id)}),
    }
