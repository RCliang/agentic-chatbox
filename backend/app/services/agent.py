"""LangGraph-based agent engine.

Replaces the hand-written ReAct loop with a StateGraph supporting:
- Mixed routing (simple agent / planner->executor)
- Skill-level planning config
- Human-in-the-loop via PostgreSQL checkpointer
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole, Skill
from app.services.agent_events import done_event
from app.services.agent_nodes import (
    agent_node,
    executor_node,
    planner_node,
    respond_node,
    router_node,
)
from app.services.agent_state import AgentState, SkillConfig
from app.services.chat import get_conversation_messages
from app.services.checkpointer import get_checkpointer
from app.services.knowledge import get_kb_context, retrieve
from app.services.tools import tool_registry

logger = logging.getLogger(__name__)

DEFAULT_AGENT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to tools. "
    "Think step by step, use tools when needed, and provide clear answers."
)

EXAMPLES_MAX_TURNS = 3


# ---------------------------------------------------------------------------
# Skill prompt builder (reused from original, unchanged logic)
# ---------------------------------------------------------------------------


def build_skill_prompt(skill: Skill, conversation_turn_count: int) -> str:
    """Build the system prompt from a modular Skill."""
    parts: list[str] = []

    if skill.instructions:
        parts.append(skill.instructions)

    if skill.references:
        always_refs = [r for r in skill.references if r.get("inject") == "always"]
        if always_refs:
            ref_lines = ["", "# Reference Materials"]
            for ref in always_refs:
                title = ref.get("title", "")
                source = ref.get("source", "")
                ref_type = ref.get("type", "text")
                if ref_type == "text":
                    ref_lines.append(f"\n## {title}" if title else "")
                    ref_lines.append(source)
                elif ref_type == "url":
                    ref_lines.append(f"\n## {title}" if title else "")
                    ref_lines.append(f"Reference URL: {source}")
            parts.append("\n".join(ref_lines))

    if skill.tools:
        tool_lines = ["", "# Available Tools & When to Use Them"]
        for t in skill.tools:
            name = t.get("name", "")
            when = t.get("when", "")
            required = t.get("required", False)
            tag = "[always available]" if required else "[use when needed]"
            tool_lines.append(f"- **{name}** {tag}: {when}")
        parts.append("\n".join(tool_lines))

    if skill.examples and conversation_turn_count < EXAMPLES_MAX_TURNS:
        ex_lines = ["", "# Example Conversations"]
        for ex in skill.examples:
            ex_lines.append(f"\nUser: {ex.get('user', '')}")
            ex_lines.append(f"Assistant: {ex.get('assistant', '')}")
        parts.append("\n".join(ex_lines))

    return "\n\n".join(parts) if parts else DEFAULT_AGENT_SYSTEM_PROMPT


async def inject_on_demand_refs(skill: Skill, user_content: str, db: AsyncSession) -> str:
    """Phase 2: retrieve on-demand references relevant to user_content."""
    if not skill.references:
        return ""

    on_demand = [r for r in skill.references if r.get("inject") == "on_demand"]
    if not on_demand:
        return ""

    context_parts: list[str] = []
    for ref in on_demand:
        ref_type = ref.get("type", "text")
        source = ref.get("source", "")
        title = ref.get("title", "")

        if ref_type == "knowledge_base" and source:
            results = await retrieve([source], user_content, top_k=3)
            if results:
                chunks = "\n".join(f"  [{i+1}] {r['text']}" for i, r in enumerate(results))
                context_parts.append(f"## {title or 'Knowledge Base'}\n{chunks}")
        elif ref_type == "text" and source:
            context_parts.append(f"## {title or 'Reference'}\n{source}")
        elif ref_type == "url":
            context_parts.append(f"## {title or 'Reference'}\nSee: {source}")

    if not context_parts:
        return ""
    return "\n\n# On-Demand References\n\n" + "\n\n".join(context_parts)


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _should_continue_executor(state: AgentState) -> str:
    """Conditional edge: continue executing steps or go to respond."""
    plan = state.get("plan") or []
    idx = state.get("current_step", 0)
    if idx < len(plan):
        return "executor"
    return "respond"


def build_graph() -> StateGraph:
    """Build the agent StateGraph (uncompiled)."""
    graph = StateGraph(AgentState)

    graph.add_node("router", router_node)
    graph.add_node("agent", agent_node)
    graph.add_node("planner", planner_node)
    graph.add_node("executor", executor_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("router")

    # router uses Command(goto=...) so no explicit edges from router
    graph.add_edge("agent", "respond")
    graph.add_conditional_edges("planner", _should_continue_executor, {"executor": "executor", "respond": "respond"})
    graph.add_conditional_edges("executor", _should_continue_executor, {"executor": "executor", "respond": "respond"})
    graph.add_edge("respond", END)

    return graph


# ---------------------------------------------------------------------------
# Agent loop — public API
# ---------------------------------------------------------------------------


async def agent_loop(
    conversation: Conversation,
    user_content: str,
    db: AsyncSession,
) -> AsyncIterator[dict]:
    """Run the LangGraph agent, yielding SSE event dicts.

    Drop-in replacement for the old hand-written ReAct loop.
    Same SSE event interface: {event: str, data: str}.
    """
    # 1. Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=user_content,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # 2. Build system prompt
    system_prompt = DEFAULT_AGENT_SYSTEM_PROMPT
    skill_config: SkillConfig | None = None
    skill: Skill | None = None

    if conversation.skill_id:
        skill_result = await db.execute(
            select(Skill).where(Skill.id == conversation.skill_id)
        )
        skill = skill_result.scalar_one_or_none()

    if skill:
        history_for_count = await get_conversation_messages(db, conversation.id, limit=100)
        turn_count = sum(1 for m in history_for_count if m.role == MessageRole.user)

        system_prompt = build_skill_prompt(skill, turn_count)

        on_demand_context = await inject_on_demand_refs(skill, user_content, db)
        if on_demand_context:
            system_prompt += "\n\n" + on_demand_context

        skill_config = SkillConfig(
            skill_id=str(skill.id),
            instructions=skill.instructions or "",
            planning_mode=getattr(skill, "planning_mode", "auto"),
            confirm_plan=getattr(skill, "confirm_plan", True),
            confirm_tools=getattr(skill, "confirm_tools", None) or [],
            tool_names=[t.get("name", "") for t in (skill.tools or []) if t.get("name")],
            references=skill.references or [],
            examples=skill.examples or [],
            knowledge_base_id=str(skill.knowledge_base_id) if skill.knowledge_base_id else None,
        )

    # 3. RAG context
    kb_id = None
    if conversation.knowledge_base_id:
        kb_id = conversation.knowledge_base_id
    elif skill and skill.knowledge_base_id:
        kb_id = skill.knowledge_base_id

    if kb_id:
        try:
            rag_context = await get_kb_context(db, kb_id, user_content)
            if rag_context:
                system_prompt += "\n\n" + rag_context
        except Exception:
            logger.warning("RAG context retrieval failed for kb_id=%s", kb_id, exc_info=True)

    # 4. Get tool schemas
    skill_tool_names = skill_config.tool_names if skill_config else []
    tool_ids = list(set((conversation.enabled_tools or []) + skill_tool_names))
    tool_schemas = await tool_registry.get_tool_schemas(tool_ids=tool_ids or None, db=db)

    # 5. Build initial state
    initial_state: AgentState = {
        "messages": [HumanMessage(content=user_content)],
        "plan": None,
        "current_step": 0,
        "skill_config": skill_config,
        "tools_available": tool_ids,
        "sse_events": [],
        "system_prompt": system_prompt,
        "conversation_id": str(conversation.id),
        "tool_schemas": tool_schemas,
    }

    # 6. Compile and run graph
    print("[DEBUG] agent_loop: getting checkpointer...")
    checkpointer = await get_checkpointer()
    print("[DEBUG] agent_loop: checkpointer ready, building graph...")
    graph = build_graph()
    compiled = graph.compile(checkpointer=checkpointer)
    print("[DEBUG] agent_loop: graph compiled, starting stream...")

    config = {"configurable": {"thread_id": str(conversation.id)}}

    agent_steps: list[dict] = []
    full_content = ""

    async for event in compiled.astream(initial_state, config=config, stream_mode="updates"):
        logger.info("agent_loop: got stream event: %s", list(event.keys()))
        for node_name, node_output in event.items():
            if not isinstance(node_output, dict):
                continue
            sse_events = node_output.get("sse_events", [])
            for sse in sse_events:
                yield sse
                parsed = json.loads(sse["data"]) if isinstance(sse["data"], str) else sse["data"]
                if sse["event"] == "text":
                    full_content = parsed.get("content", "")
                elif sse["event"] == "tool_call":
                    agent_steps.append({
                        "tool_name": parsed.get("name", ""),
                        "arguments": parsed.get("arguments", {}),
                    })
                elif sse["event"] == "tool_result":
                    if agent_steps:
                        agent_steps[-1]["result"] = parsed.get("result", "")

    # 7. Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=full_content,
        agent_steps=agent_steps if agent_steps else None,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    # 8. Yield done
    yield done_event(str(assistant_msg.id))


# ---------------------------------------------------------------------------
# Resume — for human-in-the-loop
# ---------------------------------------------------------------------------


async def resume_agent(
    conversation: Conversation,
    action: str,
    payload: dict,
    db: AsyncSession,
) -> AsyncIterator[dict]:
    """Resume an interrupted graph execution after user decision."""
    checkpointer = await get_checkpointer()
    graph = build_graph()
    compiled = graph.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": str(conversation.id)}}
    resume_value = {"action": action, **payload}

    agent_steps: list[dict] = []
    full_content = ""

    async for event in compiled.astream(
        Command(resume=resume_value), config=config, stream_mode="updates"
    ):
        for node_name, node_output in event.items():
            if not isinstance(node_output, dict):
                continue
            sse_events = node_output.get("sse_events", [])
            for sse in sse_events:
                yield sse
                parsed = json.loads(sse["data"]) if isinstance(sse["data"], str) else sse["data"]
                if sse["event"] == "text":
                    full_content = parsed.get("content", "")
                elif sse["event"] == "tool_call":
                    agent_steps.append({
                        "tool_name": parsed.get("name", ""),
                        "arguments": parsed.get("arguments", {}),
                    })
                elif sse["event"] == "tool_result":
                    if agent_steps:
                        agent_steps[-1]["result"] = parsed.get("result", "")

    if full_content:
        assistant_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.assistant,
            content=full_content,
            agent_steps=agent_steps if agent_steps else None,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)
        yield done_event(str(assistant_msg.id))


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------


async def get_agent_status(conversation_id: str) -> dict:
    """Check if a conversation has a pending interrupt."""
    try:
        checkpointer = await get_checkpointer()
        graph = build_graph()
        compiled = graph.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": conversation_id}}
        state = await compiled.aget_state(config)

        if state and state.next:
            return {
                "state": "waiting_for_input",
                "interrupt_data": None,
            }
        return {"state": "idle", "interrupt_data": None}
    except Exception:
        return {"state": "idle", "interrupt_data": None}
