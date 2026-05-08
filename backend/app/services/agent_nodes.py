"""LangGraph node implementations for the agent graph."""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command, interrupt

from app.services.agent_events import (
    interrupt_event,
    node_enter,
    node_exit,
    plan_event,
    plan_step_update,
    text_event,
    thinking_event,
    tool_call_event,
    tool_result_event,
)
from app.services.agent_state import AgentState, PlanStep
from app.services.llm import llm_client
from app.services.tools import tool_registry

logger = logging.getLogger(__name__)

MAX_AGENT_ITERATIONS = 15

PLAN_SYSTEM_PROMPT = """You are a planning assistant. Given the user's request and context, create a step-by-step plan.
Return a JSON array of steps: [{"id": "step_1", "title": "...", "description": "..."}]
Each step should be a concrete, actionable task. Keep plans focused — usually 2-5 steps.
Return ONLY the JSON array, no other text."""


def _build_openai_messages(state: AgentState) -> list[dict]:
    """Convert AgentState messages to OpenAI-format dicts."""
    result = [{"role": "system", "content": state["system_prompt"]}]
    for msg in state["messages"]:
        if isinstance(msg, SystemMessage):
            continue
        elif isinstance(msg, HumanMessage):
            result.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            entry: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["args"]),
                        },
                    }
                    for tc in msg.tool_calls
                ]
            result.append(entry)
        elif isinstance(msg, ToolMessage):
            result.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content,
            })
    return result


async def router_node(state: AgentState) -> Command:
    """Decide whether to use simple agent path or planner path."""
    t0 = time.monotonic()
    events = [node_enter("router", "正在分析请求...")]

    skill = state.get("skill_config")
    planning_mode = skill.planning_mode if skill else "never"

    if planning_mode == "never":
        goto = "agent"
        events.append(thinking_event("直接回答模式，无需制定计划"))
    elif planning_mode == "always":
        goto = "planner"
        events.append(thinking_event("该技能要求始终制定计划，进入规划模式"))
    else:
        # auto — ask LLM
        last_user = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_user = msg.content
                break

        response = await llm_client.chat(
            [
                {"role": "system", "content": (
                    "You are a routing assistant. Decide if the user's request needs a multi-step plan or can be answered directly.\n\n"
                    "MUST use planning mode (need_plan: true) when:\n"
                    "- Writing long-form content: articles, reports, documents, essays, proposals, tutorials\n"
                    "- Tasks requiring research + synthesis across multiple sources\n"
                    "- Multi-step workflows (e.g. analyze data then generate report)\n"
                    "- Complex comparisons or evaluations\n"
                    "- Any task that would benefit from outlining before execution\n\n"
                    "Can answer directly (need_plan: false) when:\n"
                    "- Simple Q&A, factual lookups, definitions\n"
                    "- Short translations or summaries (< 200 words)\n"
                    "- Single tool calls (e.g. one web search)\n"
                    "- Code snippets or quick fixes\n"
                    "- Casual conversation\n\n"
                    "Reply with JSON only: {\"need_plan\": true/false}"
                )},
                {"role": "user", "content": last_user},
            ],
            temperature=0,
            max_tokens=50,
        )
        content = response.get("choices", [{}])[0].get("message", {}).get("content") or ""
        try:
            need_plan = json.loads(content).get("need_plan", False)
        except (json.JSONDecodeError, AttributeError):
            need_plan = False
        goto = "planner" if need_plan else "agent"
        events.append(thinking_event(f"分析请求复杂度: {'需要制定计划' if need_plan else '可以直接回答'}"))

    elapsed = int((time.monotonic() - t0) * 1000)
    events.append(node_exit("router", elapsed))

    return Command(goto=goto, update={"sse_events": events})


async def agent_node(state: AgentState) -> dict:
    """Simple agent — direct LLM call with tool use, looping until done."""
    t0 = time.monotonic()
    events = [node_enter("agent", "正在思考...")]

    messages = _build_openai_messages(state)
    tools = state.get("tool_schemas") or None
    skill = state.get("skill_config")
    confirm_tools = skill.confirm_tools if skill else []

    full_content = ""

    for _ in range(MAX_AGENT_ITERATIONS):
        response = await llm_client.chat(messages, tools=tools)
        choices = response.get("choices", [])
        if not choices:
            break

        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls")

        if not tool_calls:
            content = message.get("content", "")
            if content:
                full_content = content
                events.append(text_event(content))
            break

        # Thinking
        thinking = message.get("content", "") or ""
        if thinking:
            events.append(thinking_event(thinking))
        else:
            tool_names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
            events.append(thinking_event(f"决定调用工具: {', '.join(tool_names)}"))

        messages.append(message)

        for tc in tool_calls:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            try:
                arguments = json.loads(fn.get("arguments", "{}"))
            except json.JSONDecodeError:
                arguments = {}

            call_id = tc.get("id", str(uuid.uuid4()))
            events.append(tool_call_event(call_id, tool_name, arguments))

            # Check if tool needs confirmation
            if tool_name in confirm_tools:
                elapsed = int((time.monotonic() - t0) * 1000)
                events.append(node_exit("agent", elapsed))
                events.append(interrupt_event("tool", {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "call_id": call_id,
                }))
                user_decision = interrupt({
                    "type": "tool_confirmation",
                    "tool_name": tool_name,
                    "arguments": arguments,
                })
                if user_decision.get("action") == "reject":
                    result = f"Tool call '{tool_name}' was rejected by user."
                else:
                    result = await tool_registry.execute(tool_name, arguments)
            else:
                result = await tool_registry.execute(tool_name, arguments)

            events.append(tool_result_event(call_id, tool_name, result))
            messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": result,
            })

    elapsed = int((time.monotonic() - t0) * 1000)
    events.append(node_exit("agent", elapsed))

    new_messages = []
    if full_content:
        new_messages.append(AIMessage(content=full_content))

    return {"sse_events": events, "messages": new_messages}


async def planner_node(state: AgentState) -> dict:
    """Generate a multi-step plan for complex tasks."""
    t0 = time.monotonic()
    events = [node_enter("planner", "正在制定计划...")]

    system = state["system_prompt"] + "\n\n" + PLAN_SYSTEM_PROMPT
    messages = [{"role": "system", "content": system}]
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            messages.append({"role": "assistant", "content": msg.content or ""})

    response = await llm_client.chat(messages, temperature=0.3, max_tokens=2048)
    content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

    try:
        raw_steps = json.loads(content)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            raw_steps = json.loads(match.group())
        else:
            raw_steps = [{"id": "step_1", "title": "Execute request", "description": content}]

    plan_steps: list[PlanStep] = []
    for i, step in enumerate(raw_steps):
        plan_steps.append(PlanStep(
            id=step.get("id", f"step_{i+1}"),
            title=step.get("title", f"Step {i+1}"),
            description=step.get("description", ""),
            status="pending",
        ))

    events.append(plan_event([dict(s) for s in plan_steps]))

    elapsed = int((time.monotonic() - t0) * 1000)
    events.append(node_exit("planner", elapsed))

    # Check if plan confirmation is needed
    skill = state.get("skill_config")
    if skill and skill.confirm_plan:
        events.append(interrupt_event("plan", {"steps": [dict(s) for s in plan_steps]}))
        user_decision = interrupt({
            "type": "plan_confirmation",
            "steps": [dict(s) for s in plan_steps],
        })
        action = user_decision.get("action", "approve")
        if action == "reject":
            return {
                "sse_events": events + [text_event("Plan was rejected. Please provide more details.")],
                "plan": None,
                "messages": [AIMessage(content="Plan was rejected. Please provide more details.")],
            }
        elif action == "edit":
            edited = user_decision.get("steps", plan_steps)
            plan_steps = [PlanStep(**s) for s in edited]

    return {"sse_events": events, "plan": plan_steps, "current_step": 0}


async def executor_node(state: AgentState) -> dict:
    """Execute the current plan step using LLM + tools."""
    t0 = time.monotonic()
    plan = state.get("plan") or []
    idx = state.get("current_step", 0)

    if idx >= len(plan):
        return {"sse_events": [node_enter("executor", "计划执行完成")]}

    step = plan[idx]
    events = [
        node_enter("executor", f"正在执行: {step['title']}"),
        plan_step_update(step["id"], "running"),
    ]

    # Phase 3: on_step reference loading
    step_context = await _load_step_references(state, step)

    system = state["system_prompt"]
    if step_context:
        system += "\n\n# Step-Specific References\n\n" + step_context

    step_prompt = f"Execute this step of the plan:\n\nStep {idx+1}: {step['title']}\n{step['description']}\n\nUse tools as needed. Provide a clear result."

    messages = _build_openai_messages(state)
    messages.append({"role": "user", "content": step_prompt})

    tools = state.get("tool_schemas") or None
    skill = state.get("skill_config")
    confirm_tools = skill.confirm_tools if skill else []

    response = await llm_client.chat(messages, tools=tools)
    choices = response.get("choices", [])
    result_content = ""

    if choices:
        message = choices[0].get("message", {})
        tool_calls = message.get("tool_calls")

        if tool_calls:
            thinking = message.get("content", "") or ""
            if thinking:
                events.append(thinking_event(thinking))

            for tc in tool_calls:
                fn = tc.get("function", {})
                tool_name = fn.get("name", "")
                try:
                    arguments = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}

                call_id = tc.get("id", str(uuid.uuid4()))
                events.append(tool_call_event(call_id, tool_name, arguments))

                if tool_name in confirm_tools:
                    events.append(interrupt_event("tool", {
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "call_id": call_id,
                    }))
                    user_decision = interrupt({
                        "type": "tool_confirmation",
                        "tool_name": tool_name,
                        "arguments": arguments,
                    })
                    if user_decision.get("action") == "reject":
                        result = f"Tool call '{tool_name}' was rejected by user."
                    else:
                        result = await tool_registry.execute(tool_name, arguments)
                else:
                    result = await tool_registry.execute(tool_name, arguments)

                events.append(tool_result_event(call_id, tool_name, result))

            # Get final answer after tool use
            messages.append(message)
            for tc in tool_calls:
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": result,
                })
            followup = await llm_client.chat(messages)
            fc = followup.get("choices", [{}])[0].get("message", {}).get("content", "")
            result_content = fc
        else:
            result_content = message.get("content", "")

    # Update plan step status
    updated_plan = list(plan)
    updated_plan[idx] = {**step, "status": "done"}
    events.append(plan_step_update(step["id"], "done"))

    elapsed = int((time.monotonic() - t0) * 1000)
    events.append(node_exit("executor", elapsed))

    new_messages = []
    if result_content:
        new_messages.append(AIMessage(content=f"[Step {idx+1} result]: {result_content}"))

    return {
        "sse_events": events,
        "plan": updated_plan,
        "current_step": idx + 1,
        "messages": new_messages,
    }


async def _load_step_references(state: AgentState, step: dict) -> str:
    """Phase 3: load on_step references matching current step's tools."""
    skill = state.get("skill_config")
    if not skill or not skill.references:
        return ""

    on_step_refs = [r for r in skill.references if r.get("inject") == "on_step"]
    if not on_step_refs:
        return ""

    step_text = f"{step.get('title', '')} {step.get('description', '')}"
    parts: list[str] = []

    for ref in on_step_refs:
        match_tools = ref.get("match_tools", [])
        if not match_tools or any(t.lower() in step_text.lower() for t in match_tools):
            ref_type = ref.get("type", "text")
            source = ref.get("source", "")
            title = ref.get("title", "")

            if ref_type == "knowledge_base" and source:
                from app.services.knowledge import retrieve
                results = await retrieve([source], step_text, top_k=3)
                if results:
                    chunks = "\n".join(f"  [{i+1}] {r['text']}" for i, r in enumerate(results))
                    parts.append(f"## {title or 'Reference'}\n{chunks}")
            elif ref_type == "text" and source:
                parts.append(f"## {title or 'Reference'}\n{source}")

    return "\n\n".join(parts)


async def respond_node(state: AgentState) -> dict:
    """Generate final response summarizing plan execution."""
    t0 = time.monotonic()
    events = [node_enter("respond", "正在生成总结...")]

    plan = state.get("plan")
    if not plan:
        elapsed = int((time.monotonic() - t0) * 1000)
        events.append(node_exit("respond", elapsed))
        return {"sse_events": events}

    summary_prompt = "Summarize the results of the executed plan steps into a clear, concise final answer for the user."
    messages = _build_openai_messages(state)
    messages.append({"role": "user", "content": summary_prompt})

    response = await llm_client.chat(messages, max_tokens=4096)
    content = response.get("choices", [{}])[0].get("message", {}).get("content", "")

    if content:
        events.append(text_event(content))

    elapsed = int((time.monotonic() - t0) * 1000)
    events.append(node_exit("respond", elapsed))

    return {
        "sse_events": events,
        "messages": [AIMessage(content=content)] if content else [],
    }
