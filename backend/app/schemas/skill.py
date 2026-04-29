"""Pydantic schemas for Skill CRUD endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SkillCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str
    tool_ids: list[str] | None = None
    knowledge_base_id: str | None = None


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    tool_ids: list[str] | None = None
    knowledge_base_id: str | None = None


class SkillResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    tool_ids: list | None
    knowledge_base_id: uuid.UUID | None
    is_builtin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
