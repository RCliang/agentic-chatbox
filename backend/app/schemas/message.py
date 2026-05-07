"""Pydantic schemas for chat message endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str | None = None
    tool_calls: dict | None = None
    tool_call_id: str | None = None
    agent_steps: dict | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatSendRequest(BaseModel):
    conversation_id: str
    content: str
    attachments: list[str] | None = None


class ResumeRequest(BaseModel):
    conversation_id: str
    action: str  # "approve" | "reject" | "edit"
    payload: dict = {}
