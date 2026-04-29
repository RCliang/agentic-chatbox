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
from app.services.knowledge import get_kb_context
from app.services.llm import LLMClient, llm_client
from app.services.tools import tool_registry

logger = logging.getLogger(__name__)

DEFAULT_AGENT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant with access to tools. "
    "Think step by step, use tools when needed, and provide clear answers."
)

MAX_ITERATIONS = 15


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

    # 2. Build system prompt
    system_prompt = DEFAULT_AGENT_SYSTEM_PROMPT
    if conversation.skill_id:
        skill_result = await db.execute(
            select(Skill).where(Skill.id == conversation.skill_id)
        )
        skill = skill_result.scalar_one_or_none()
        if skill:
            system_prompt = skill.system_prompt

    # 3. Build message history
    history = await get_conversation_messages(db, conversation.id, limit=50)
    messages = build_messages_for_llm(history[:-1], system_prompt, user_content)

    # 4. Append RAG context if knowledge_base_id is set
    if conversation.knowledge_base_id:
        rag_context = await get_kb_context(db, conversation.knowledge_base_id, user_content)
        if rag_context:
            # Prepend RAG context to the existing system message
            if messages and messages[0]["role"] == "system":
                messages[0] = {
                    "role": "system",
                    "content": messages[0]["content"] + "\n\n" + rag_context,
                }

    # 5. Get tool schemas
    tool_ids = conversation.enabled_tools
    tools = await tool_registry.get_tool_schemas(tool_ids=tool_ids, db=db)

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
