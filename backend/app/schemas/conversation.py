"""Pydantic schemas for conversation endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    mode: str = "normal"
    skill_id: str | None = None
    knowledge_base_id: str | None = None
    tool_ids: list[str] | None = None


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    mode: str
    skill_id: uuid.UUID | None = None
    knowledge_base_id: uuid.UUID | None = None
    enabled_tools: list | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    id: uuid.UUID
    title: str
    mode: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
