"""Pydantic schemas for Skill CRUD endpoints."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Sub-models for modular skill content
# ---------------------------------------------------------------------------


class SkillToolItem(BaseModel):
    """A tool declaration within a skill."""
    name: str
    when: str = ""
    required: bool = False


class SkillRefItem(BaseModel):
    """A reference (knowledge base, inline text, or URL) within a skill."""
    type: Literal["knowledge_base", "text", "url"]
    source: str
    title: str = ""
    inject: Literal["always", "on_demand", "on_step"] = "on_demand"
    match_tools: list[str] | None = None


class SkillExampleItem(BaseModel):
    """A few-shot example conversation pair."""
    user: str
    assistant: str


# ---------------------------------------------------------------------------
# CRUD schemas
# ---------------------------------------------------------------------------


class SkillCreate(BaseModel):
    name: str
    description: str | None = None
    instructions: str = ""
    tools: list[SkillToolItem] | None = None
    references: list[SkillRefItem] | None = None
    examples: list[SkillExampleItem] | None = None
    knowledge_base_id: str | None = None
    planning_mode: str = "auto"
    confirm_plan: bool = True
    confirm_tools: list[str] | None = None


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    instructions: str | None = None
    tools: list[SkillToolItem] | None = None
    references: list[SkillRefItem] | None = None
    examples: list[SkillExampleItem] | None = None
    knowledge_base_id: str | None = None
    planning_mode: str | None = None
    confirm_plan: bool | None = None
    confirm_tools: list[str] | None = None


class SkillResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    instructions: str
    tools: list[SkillToolItem] | None
    references: list[SkillRefItem] | None
    examples: list[SkillExampleItem] | None
    knowledge_base_id: uuid.UUID | None
    planning_mode: str
    confirm_plan: bool
    confirm_tools: list[str] | None
    is_builtin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
