"""LangGraph agent state definitions."""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages


class PlanStep(TypedDict):
    id: str
    title: str
    description: str
    status: Literal["pending", "running", "done", "failed"]


@dataclass
class SkillConfig:
    """Subset of Skill model fields needed during graph execution."""

    skill_id: str
    instructions: str
    planning_mode: Literal["auto", "always", "never"]
    confirm_plan: bool
    confirm_tools: list[str]
    tool_names: list[str]
    references: list[dict] = field(default_factory=list)
    examples: list[dict] = field(default_factory=list)
    knowledge_base_id: str | None = None


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    plan: list[PlanStep] | None
    current_step: int
    skill_config: SkillConfig | None
    tools_available: list[str]
    sse_events: Annotated[list[dict], operator.add]
    system_prompt: str
    conversation_id: str
    tool_schemas: list[dict]
