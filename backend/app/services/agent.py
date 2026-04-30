"""Agent engine implementing the ReAct (Reason + Act) pattern.

Provides ``agent_loop``, an async generator that drives a multi-turn
tool-use conversation with an LLM, yielding SSE events consumed by the
``/api/chat/send`` endpoint.
"""

import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole, Skill
from app.services.chat import build_messages_for_llm, get_conversation_messages
from app.services.knowledge import get_kb_context, retrieve
from app.services.llm import LLMClient, llm_client
from app.services.tools import tool_registry

logger = logging.getLogger(__name__)

DEFAULT_AGENT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to tools. "
    "Think step by step, use tools when needed, and provide clear answers."
)

MAX_ITERATIONS = 15
EXAMPLES_MAX_TURNS = 3  # Stop injecting examples after this many conversation turns


# ---------------------------------------------------------------------------
# Skill prompt builder — progressive loading
# ---------------------------------------------------------------------------


def build_skill_prompt(
    skill: Skill,
    conversation_turn_count: int,
) -> str:
    """Build the system prompt from a modular Skill (Phase 1: always-inject).

    Assembles:
    1. instructions (always)
    2. always-inject references
    3. tool usage guidance
    4. examples (only if early in conversation)
    """
    parts: list[str] = []

    # 1. Core instructions
    if skill.instructions:
        parts.append(skill.instructions)

    # 2. Always-inject references
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
                # knowledge_base type is handled via RAG in Phase 2
            parts.append("\n".join(ref_lines))

    # 3. Tool usage guidance
    if skill.tools:
        tool_lines = ["", "# Available Tools & When to Use Them"]
        for t in skill.tools:
            name = t.get("name", "")
            when = t.get("when", "")
            required = t.get("required", False)
            tag = "[always available]" if required else "[use when needed]"
            tool_lines.append(f"- **{name}** {tag}: {when}")
        parts.append("\n".join(tool_lines))

    # 4. Examples (few-shot, only for early turns)
    if skill.examples and conversation_turn_count < EXAMPLES_MAX_TURNS:
        ex_lines = ["", "# Example Conversations"]
        for ex in skill.examples:
            ex_lines.append(f"\nUser: {ex.get('user', '')}")
            ex_lines.append(f"Assistant: {ex.get('assistant', '')}")
        parts.append("\n".join(ex_lines))

    return "\n\n".join(parts) if parts else DEFAULT_AGENT_SYSTEM_PROMPT


def get_skill_tool_names(skill: Skill) -> list[str]:
    """Extract all tool names declared by a skill."""
    if not skill.tools:
        return []
    return [t.get("name", "") for t in skill.tools if t.get("name")]


async def inject_on_demand_refs(
    skill: Skill,
    user_content: str,
    db: AsyncSession,
) -> str:
    """Phase 2: retrieve on-demand references relevant to user_content.

    Returns a context string to append to the system prompt.
    """
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
            # RAG retrieval from the specified knowledge base
            results = await retrieve([source], user_content, top_k=3)
            if results:
                chunks = "\n".join(f"  [{i+1}] {r['text']}" for i, r in enumerate(results))
                context_parts.append(f"## {title or 'Knowledge Base'}\n{chunks}")

        elif ref_type == "text" and source:
            # Inline text — always include (lightweight)
            context_parts.append(f"## {title or 'Reference'}\n{source}")

        elif ref_type == "url":
            # URL references — include the URL for the LLM to reference
            context_parts.append(f"## {title or 'Reference'}\nSee: {source}")

    if not context_parts:
        return ""

    return "\n\n# On-Demand References\n\n" + "\n\n".join(context_parts)


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------


async def agent_loop(
    conversation: Conversation,
    user_content: str,
    db: AsyncSession,
    llm: LLMClient | None = None,
) -> AsyncIterator[dict]:
    """Run a ReAct agent loop, yielding SSE event dicts.

    Each yielded dict has keys ``event`` (str) and ``data`` (str).

    Events: ``thinking``, ``tool_call``, ``tool_result``, ``text``, ``done``
    """
    client = llm or llm_client
    agent_steps: list[dict] = []

    # 1. Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.user,
        content=user_content,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # 2. Build system prompt — progressive skill loading
    system_prompt = DEFAULT_AGENT_SYSTEM_PROMPT
    skill_tool_names: list[str] = []
    skill: Skill | None = None

    if conversation.skill_id:
        skill_result = await db.execute(
            select(Skill).where(Skill.id == conversation.skill_id)
        )
        skill = skill_result.scalar_one_or_none()

    if skill:
        # Count existing conversation turns for example injection control
        history_for_count = await get_conversation_messages(db, conversation.id, limit=100)
        turn_count = sum(1 for m in history_for_count if m.role == MessageRole.user)

        # Phase 1: build base prompt from skill modules
        system_prompt = build_skill_prompt(skill, turn_count)
        skill_tool_names = get_skill_tool_names(skill)

        # Phase 2: inject on-demand references
        on_demand_context = await inject_on_demand_refs(skill, user_content, db)
        if on_demand_context:
            system_prompt += "\n\n" + on_demand_context

    # 3. Build message history
    history = await get_conversation_messages(db, conversation.id, limit=50)
    messages = build_messages_for_llm(history[:-1], system_prompt, user_content)

    # 4. Append RAG context if knowledge_base_id is set
    kb_id = None
    if conversation.knowledge_base_id:
        kb_id = conversation.knowledge_base_id
    elif skill and skill.knowledge_base_id:
        kb_id = skill.knowledge_base_id

    if kb_id:
        rag_context = await get_kb_context(db, kb_id, user_content)
        if rag_context:
            if messages and messages[0]["role"] == "system":
                messages[0] = {
                    "role": "system",
                    "content": messages[0]["content"] + "\n\n" + rag_context,
                }

    # 5. Get tool schemas — merge conversation tools + skill tools
    tool_ids = list(set((conversation.enabled_tools or []) + skill_tool_names))
    tools = await tool_registry.get_tool_schemas(tool_ids=tool_ids or None, db=db)

    # 6. ReAct loop
    full_content = ""
    for iteration in range(MAX_ITERATIONS):
        # Call LLM (non-streaming for agent loop to inspect tool_calls)
        try:
            response = await client.chat(messages, tools=tools or None)
        except Exception as exc:
            logger.exception("LLM call failed in agent loop")
            full_content = f"Error: LLM call failed — {exc}"
            break

        choices = response.get("choices", [])
        if not choices:
            break

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            # No tool calls — final text response
            content = message.get("content", "")
            if content:
                full_content = content
                yield {"event": "text", "data": json.dumps({"content": content})}
            break

        # --- Tool call branch ---
        # Yield thinking event
        thinking = message.get("content", "") or ""
        yield {"event": "thinking", "data": json.dumps({"content": thinking})}

        # Append assistant message with tool_calls to conversation history
        messages.append(message)

        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            arguments_str = fn.get("arguments", "{}")

            try:
                arguments = json.loads(arguments_str)
            except json.JSONDecodeError:
                arguments = {}

            # Yield tool_call event
            yield {
                "event": "tool_call",
                "data": json.dumps({
                    "id": tc.get("id", ""),
                    "name": tool_name,
                    "arguments": arguments,
                }),
            }

            # Execute tool
            result = await tool_registry.execute(tool_name, arguments, db=db)

            # Yield tool_result event
            yield {
                "event": "tool_result",
                "data": json.dumps({
                    "id": tc.get("id", ""),
                    "name": tool_name,
                    "result": result,
                }),
            }

            # Append tool result to messages
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
                "content": result,
            })

            agent_steps.append({
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
            })

    else:
        # Max iterations exceeded — force a final summary
        messages.append({
            "role": "user",
            "content": "You have reached the maximum number of tool calls. Please provide a final summary of your findings.",
        })
        try:
            response = await client.chat(messages)
            choices = response.get("choices", [])
            if choices:
                content = choices[0].get("message", {}).get("content", "")
                if content:
                    full_content = content
                    yield {"event": "text", "data": json.dumps({"content": content})}
        except Exception as exc:
            logger.exception("LLM summary call failed after max iterations")
            full_content = f"Error: agent reached max iterations — {exc}"

    # 8. Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.assistant,
        content=full_content,
        agent_steps=agent_steps if agent_steps else None,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    # 9. Yield done event
    yield {
        "event": "done",
        "data": json.dumps({"message_id": str(assistant_msg.id)}),
    }
