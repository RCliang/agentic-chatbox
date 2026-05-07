# LangGraph Agent Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hand-written ReAct agent loop with a LangGraph StateGraph supporting mixed routing (simple agent / planner→executor), Skill-level planning config, full execution trace visualization, and human-in-the-loop via PostgreSQL checkpointer.

**Architecture:** A LangGraph `StateGraph` with nodes: router → (agent | planner → executor) → tool_node → respond. SSE events stream from each node through FastAPI to the React frontend. The PostgreSQL checkpointer enables interrupt/resume for plan confirmation and sensitive tool approval.

**Tech Stack:** Python (langgraph, langgraph-checkpoint-postgres), FastAPI SSE, React/TypeScript/Zustand

---

## File Structure

### Backend — New Files
| File | Responsibility |
|------|---------------|
| `backend/app/services/agent_state.py` | `AgentState` TypedDict, `PlanStep` TypedDict, `SkillConfig` dataclass |
| `backend/app/services/agent_nodes.py` | Node functions: `router_node`, `planner_node`, `agent_node`, `executor_node`, `tool_node`, `respond_node` |
| `backend/app/services/agent_events.py` | `emit_sse(event, data)` helper, SSE event constants |
| `backend/app/services/checkpointer.py` | `get_checkpointer()` — async PostgreSQL checkpointer singleton |

### Backend — Modified Files
| File | Changes |
|------|---------|
| `backend/app/services/agent.py` | Rewrite: build `StateGraph`, compile with checkpointer, `agent_loop` becomes thin wrapper calling `graph.astream_events()` |
| `backend/app/models/skill.py` | Add columns: `planning_mode`, `confirm_plan`, `confirm_tools` |
| `backend/app/schemas/skill.py` | Add fields to `SkillCreate`, `SkillUpdate`, `SkillResponse` |
| `backend/app/schemas/chat.py` | Add `ResumeRequest` schema |
| `backend/app/api/chat.py` | Add `POST /resume`, `GET /{id}/status` endpoints |

### Frontend — New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/components/PlanView.tsx` | Render plan step list with live status |
| `frontend/src/components/InterruptDialog.tsx` | Modal for plan/tool confirmation |
| `frontend/src/components/NodeTracker.tsx` | Horizontal node execution indicator |

### Frontend — Modified Files
| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | Add new SSE event types, `PlanStep`, `InterruptData`, `NodeStatus` |
| `frontend/src/api/client.ts` | Add `resumeInterrupt()`, `getConversationStatus()` |
| `frontend/src/stores/chatStore.ts` | Add interrupt/plan/node state, `resumeInterrupt` action, handle new events |
| `frontend/src/components/AgentStep.tsx` | Add cases for `node_enter`, `node_exit`, `plan`, `plan_step_update`, `interrupt` |
| `frontend/src/components/ChatArea.tsx` | Integrate `NodeTracker`, `PlanView`, `InterruptDialog` |
| `frontend/src/hooks/useSSE.ts` | Update `SSEEvent['event']` union for new event types |

---

### Task 1: Install Dependencies

**Files:**
- Modify: `backend/requirements.txt` (or `pyproject.toml` — whichever exists)

- [ ] **Step 1: Check which dependency file exists**

Run: `dir backend\requirements.txt backend\pyproject.toml`

- [ ] **Step 2: Add langgraph dependencies**

Add to the dependency file:

```
langgraph>=0.4
langgraph-checkpoint-postgres>=2.0
```

- [ ] **Step 3: Install**

Run: `cd backend && pip install langgraph langgraph-checkpoint-postgres`

- [ ] **Step 4: Verify installation**

Run: `python -c "import langgraph; print(langgraph.__version__)"`
Expected: version number prints without error

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add langgraph dependencies"
```

---

### Task 2: Skill Model — Add Planning Fields

**Files:**
- Modify: `backend/app/models/skill.py`
- Modify: `backend/app/schemas/skill.py`

- [ ] **Step 1: Add columns to Skill model**

In `backend/app/models/skill.py`, add after the `knowledge_base_id` field:

```python
    planning_mode: Mapped[str] = mapped_column(
        String(20), default="auto", server_default="auto"
    )
    confirm_plan: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    confirm_tools: Mapped[list | None] = mapped_column(JSON, default=None)
```

- [ ] **Step 2: Update SkillCreate schema**

In `backend/app/schemas/skill.py`, add to `SkillCreate`:

```python
    planning_mode: str = "auto"
    confirm_plan: bool = True
    confirm_tools: list[str] | None = None
```

- [ ] **Step 3: Update SkillUpdate schema**

Add to `SkillUpdate`:

```python
    planning_mode: str | None = None
    confirm_plan: bool | None = None
    confirm_tools: list[str] | None = None
```

- [ ] **Step 4: Update SkillResponse schema**

Add to `SkillResponse`:

```python
    planning_mode: str
    confirm_plan: bool
    confirm_tools: list[str] | None
```

- [ ] **Step 5: Update SkillRefItem for on_step inject**

In `backend/app/schemas/skill.py`, update `SkillRefItem`:

```python
class SkillRefItem(BaseModel):
    type: Literal["knowledge_base", "text", "url"]
    source: str
    title: str = ""
    inject: Literal["always", "on_demand", "on_step"] = "always"
    match_tools: list[str] | None = None
```

- [ ] **Step 6: Create Alembic migration**

Run: `cd backend && alembic revision --autogenerate -m "add skill planning fields"`

- [ ] **Step 7: Apply migration**

Run: `cd backend && alembic upgrade head`

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/skill.py backend/app/schemas/skill.py backend/alembic/versions/
git commit -m "feat: add planning_mode, confirm_plan, confirm_tools to Skill model"
```

---

### Task 3: AgentState Definition

**Files:**
- Create: `backend/app/services/agent_state.py`

- [ ] **Step 1: Create agent_state.py**

```python
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
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.services.agent_state import AgentState, PlanStep, SkillConfig; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/agent_state.py
git commit -m "feat: add AgentState, PlanStep, SkillConfig definitions"
```

---

### Task 4: SSE Event Helpers

**Files:**
- Create: `backend/app/services/agent_events.py`

- [ ] **Step 1: Create agent_events.py**

```python
"""SSE event builder helpers for the LangGraph agent."""

from __future__ import annotations

import json
from typing import Any


def sse_event(event: str, data: dict[str, Any]) -> dict:
    """Build an SSE event dict for yielding from graph nodes."""
    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def node_enter(node: str, label: str) -> dict:
    return sse_event("node_enter", {"node": node, "label": label})


def node_exit(node: str, duration_ms: int) -> dict:
    return sse_event("node_exit", {"node": node, "duration_ms": duration_ms})


def plan_event(steps: list[dict]) -> dict:
    return sse_event("plan", {"steps": steps})


def plan_step_update(step_id: str, status: str) -> dict:
    return sse_event("plan_step_update", {"step_id": step_id, "status": status})


def interrupt_event(interrupt_type: str, payload: dict) -> dict:
    return sse_event("interrupt", {"type": interrupt_type, "payload": payload})


def thinking_event(content: str) -> dict:
    return sse_event("thinking", {"content": content})


def tool_call_event(call_id: str, name: str, arguments: dict) -> dict:
    return sse_event("tool_call", {"id": call_id, "name": name, "arguments": arguments})


def tool_result_event(call_id: str, name: str, result: str) -> dict:
    return sse_event("tool_result", {"id": call_id, "name": name, "result": result})


def text_event(content: str) -> dict:
    return sse_event("text", {"content": content})


def done_event(message_id: str) -> dict:
    return sse_event("done", {"message_id": message_id})
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.services.agent_events import sse_event, node_enter; print(node_enter('router', 'Routing'))"`
Expected: dict with event/data keys

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/agent_events.py
git commit -m "feat: add SSE event builder helpers"
```

---

### Task 5: PostgreSQL Checkpointer

**Files:**
- Create: `backend/app/services/checkpointer.py`

- [ ] **Step 1: Create checkpointer.py**

```python
"""LangGraph PostgreSQL checkpointer setup."""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings

_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Get or create the async PostgreSQL checkpointer singleton.

    Uses the sync database URL (standard psycopg format) since
    langgraph-checkpoint-postgres uses psycopg3 directly, not SQLAlchemy.
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = AsyncPostgresSaver.from_conn_string(
            settings.database_url_sync
        )
        await _checkpointer.setup()
    return _checkpointer
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.services.checkpointer import get_checkpointer; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/checkpointer.py
git commit -m "feat: add PostgreSQL checkpointer for LangGraph"
```

---

### Task 6: Agent Nodes Implementation

**Files:**
- Create: `backend/app/services/agent_nodes.py`

- [ ] **Step 1: Create agent_nodes.py with router_node**

```python
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
    done_event,
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


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

async def router_node(state: AgentState) -> Command:
    """Decide whether to use simple agent path or planner path."""
    t0 = time.monotonic()
    events = [node_enter("router", "正在分析请求...")]

    skill = state.get("skill_config")
    planning_mode = skill.planning_mode if skill else "never"

    if planning_mode == "never":
        goto = "agent"
    elif planning_mode == "always":
        goto = "planner"
    else:
        # auto — ask LLM
        last_user = ""
        for msg in reversed(state["messages"]):
            if isinstance(msg, HumanMessage):
                last_user = msg.content
                break

        response = await llm_client.chat(
            [
                {"role": "system", "content": "Decide if this request needs a multi-step plan. Reply with JSON: {\"need_plan\": true/false}"},
                {"role": "user", "content": last_user},
            ],
            temperature=0,
            max_tokens=50,
        )
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        try:
            need_plan = json.loads(content).get("need_plan", False)
        except (json.JSONDecodeError, AttributeError):
            need_plan = False
        goto = "planner" if need_plan else "agent"

    elapsed = int((time.monotonic() - t0) * 1000)
    events.append(node_exit("router", elapsed))

    return Command(goto=goto, update={"sse_events": events})
```

- [ ] **Step 2: Add agent_node**

Append to `agent_nodes.py`:

```python
# ---------------------------------------------------------------------------
# Agent (simple path)
# ---------------------------------------------------------------------------

MAX_AGENT_ITERATIONS = 15


async def agent_node(state: AgentState) -> dict:
    """Simple agent — direct LLM call with tool use, looping until done."""
    t0 = time.monotonic()
    events = [node_enter("agent", "正在思考...")]

    messages = _build_openai_messages(state)
    tools = state.get("tool_schemas") or None
    skill = state.get("skill_config")
    confirm_tools = skill.confirm_tools if skill else []

    full_content = ""
    tool_calls_made: list[dict] = []

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
                # Interrupt — graph pauses here
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
            tool_calls_made.append({
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result,
            })

    elapsed = int((time.monotonic() - t0) * 1000)
    events.append(node_exit("agent", elapsed))

    new_messages = []
    if full_content:
        new_messages.append(AIMessage(content=full_content))

    return {"sse_events": events, "messages": new_messages}


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
```

- [ ] **Step 3: Add planner_node**

Append to `agent_nodes.py`:

```python
# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

PLAN_SYSTEM_PROMPT = """You are a planning assistant. Given the user's request and context, create a step-by-step plan.
Return a JSON array of steps: [{"id": "step_1", "title": "...", "description": "..."}]
Each step should be a concrete, actionable task. Keep plans focused — usually 2-5 steps.
Return ONLY the JSON array, no other text."""


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
        # Try to extract JSON array from content
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
```

- [ ] **Step 4: Add executor_node**

Append to `agent_nodes.py`:

```python
# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


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

    # Build messages for this step
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

    # Determine which tools this step might use (from description)
    step_text = f"{step.get('title', '')} {step.get('description', '')}"
    parts: list[str] = []

    for ref in on_step_refs:
        match_tools = ref.get("match_tools", [])
        # Include if any match_tool name appears in step text, or if no filter
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
```

- [ ] **Step 5: Add respond_node**

Append to `agent_nodes.py`:

```python
# ---------------------------------------------------------------------------
# Respond (final summary for plan path)
# ---------------------------------------------------------------------------


async def respond_node(state: AgentState) -> dict:
    """Generate final response summarizing plan execution."""
    t0 = time.monotonic()
    events = [node_enter("respond", "正在生成总结...")]

    plan = state.get("plan")
    if not plan:
        # Simple path — agent_node already produced text
        elapsed = int((time.monotonic() - t0) * 1000)
        events.append(node_exit("respond", elapsed))
        return {"sse_events": events}

    # Summarize plan execution results
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
```

- [ ] **Step 6: Verify all nodes import correctly**

Run: `cd backend && python -c "from app.services.agent_nodes import router_node, agent_node, planner_node, executor_node, respond_node; print('OK')"`
Expected: `OK`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/agent_nodes.py
git commit -m "feat: implement LangGraph agent nodes (router, agent, planner, executor, respond)"
```

---

### Task 7: Rewrite agent.py — Graph Definition

**Files:**
- Modify: `backend/app/services/agent.py`

- [ ] **Step 1: Rewrite agent.py**

Replace the entire content of `backend/app/services/agent.py` with:

```python
"""LangGraph-based agent engine.

Replaces the hand-written ReAct loop with a StateGraph supporting:
- Mixed routing (simple agent / planner→executor)
- Skill-level planning config
- Human-in-the-loop via PostgreSQL checkpointer
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph

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
from app.services.chat import build_messages_for_llm, get_conversation_messages
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

    # router → agent or planner (via Command)
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
    checkpointer = await get_checkpointer()
    graph = build_graph()
    compiled = graph.compile(checkpointer=checkpointer)

    config = {"configurable": {"thread_id": str(conversation.id)}}

    # Collect all SSE events and final content
    agent_steps: list[dict] = []
    full_content = ""

    async for event in compiled.astream(initial_state, config=config, stream_mode="updates"):
        for node_name, node_output in event.items():
            if not isinstance(node_output, dict):
                continue
            sse_events = node_output.get("sse_events", [])
            for sse in sse_events:
                yield sse
                # Track tool calls for agent_steps
                parsed = json.loads(sse["data"]) if isinstance(sse["data"], str) else sse["data"]
                if sse["event"] == "text":
                    full_content = parsed.get("content", "")
                elif sse["event"] == "tool_call":
                    agent_steps.append({
                        "tool_name": parsed.get("name", ""),
                        "arguments": parsed.get("arguments", {}),
                    })
                elif sse["event"] == "tool_result":
                    # Match with last agent_step
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

    # Save assistant message
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
    checkpointer = await get_checkpointer()
    config = {"configurable": {"thread_id": conversation_id}}
    snapshot = await checkpointer.aget(config)

    if snapshot and snapshot.metadata and snapshot.metadata.get("pending_sends"):
        return {
            "state": "waiting_for_input",
            "interrupt_data": snapshot.metadata.get("pending_sends"),
        }
    return {"state": "idle", "interrupt_data": None}
```

- [ ] **Step 2: Verify import**

Run: `cd backend && python -c "from app.services.agent import agent_loop, resume_agent, build_graph; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/services/agent.py
git commit -m "feat: rewrite agent.py with LangGraph StateGraph"
```

---

### Task 8: API Endpoints — Resume & Status

**Files:**
- Modify: `backend/app/schemas/chat.py` (add `ResumeRequest`)
- Modify: `backend/app/api/chat.py` (add endpoints)

- [ ] **Step 1: Add ResumeRequest schema**

In `backend/app/schemas/chat.py` (currently named `message.py` — check actual filename), add:

```python
class ResumeRequest(BaseModel):
    conversation_id: str
    action: str  # "approve" | "reject" | "edit"
    payload: dict = {}
```

- [ ] **Step 2: Add resume endpoint to api/chat.py**

Add these imports at the top of `backend/app/api/chat.py`:

```python
from app.services.agent import resume_agent, get_agent_status
from app.schemas.message import ResumeRequest
```

Add after the existing `send_message` endpoint:

```python
@router.post("/resume")
async def resume_conversation(
    body: ResumeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resume an interrupted agent graph execution."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == body.conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    async def event_generator():
        async for event in resume_agent(conversation, body.action, body.payload, db):
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/conversations/{conversation_id}/status")
async def conversation_status(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if a conversation has a pending interrupt."""
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    status = await get_agent_status(conversation_id)
    return status
```

- [ ] **Step 3: Verify server starts**

Run: `cd backend && python -c "from app.api.chat import router; print('Routes:', [r.path for r in router.routes])"`

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas/ backend/app/api/chat.py
git commit -m "feat: add /resume and /status API endpoints"
```

---

### Task 9: Frontend Types Update

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Update SSEEvent type and add new interfaces**

In `frontend/src/types/index.ts`, replace the `SSEEvent` interface and add new types:

```typescript
// Replace existing SSEEvent
export interface SSEEvent {
  event: 'text' | 'thinking' | 'tool_call' | 'tool_result' | 'done'
    | 'node_enter' | 'node_exit' | 'plan' | 'plan_step_update' | 'interrupt';
  data: unknown;
}

// Add these new interfaces
export interface PlanStep {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'running' | 'done' | 'failed';
}

export interface InterruptData {
  type: 'plan' | 'tool';
  payload: {
    steps?: PlanStep[];
    tool_name?: string;
    arguments?: Record<string, unknown>;
    call_id?: string;
  };
}

export interface NodeStatus {
  node: string;
  label: string;
  status: 'running' | 'done';
  duration_ms?: number;
}
```

Also update `SkillRefItem` to support `on_step`:

```typescript
export interface SkillRefItem {
  type: 'knowledge_base' | 'text' | 'url';
  source: string;
  title: string;
  inject: 'always' | 'on_demand' | 'on_step';
  match_tools?: string[];
}
```

And update `Skill` interface to add planning fields:

```typescript
export interface Skill {
  id: string;
  name: string;
  description: string | null;
  instructions: string;
  tools: SkillToolItem[] | null;
  references: SkillRefItem[] | null;
  examples: SkillExampleItem[] | null;
  knowledge_base_id: string | null;
  is_builtin: boolean;
  created_at: string;
  planning_mode: 'auto' | 'always' | 'never';
  confirm_plan: boolean;
  confirm_tools: string[] | null;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add LangGraph SSE event types and planning interfaces"
```

---

### Task 10: Frontend API Client — Resume & Status

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add API functions**

Append to `frontend/src/api/client.ts`:

```typescript
export async function resumeInterruptAPI(conversationId: string, action: string, payload: Record<string, unknown> = {}) {
  return api.post('/api/chat/resume', {
    conversation_id: conversationId,
    action,
    payload,
  });
}

export async function getConversationStatus(conversationId: string) {
  return api.get(`/api/chat/conversations/${conversationId}/status`);
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add resume and status API client functions"
```

---

### Task 11: Frontend Components — NodeTracker

**Files:**
- Create: `frontend/src/components/NodeTracker.tsx`

- [ ] **Step 1: Create NodeTracker.tsx**

```tsx
import type { NodeStatus } from '../types';

interface NodeTrackerProps {
  nodes: NodeStatus[];
}

export default function NodeTracker({ nodes }: NodeTrackerProps) {
  if (nodes.length === 0) return null;

  return (
    <div className="flex items-center gap-2 mb-3 px-4 py-2 rounded-lg text-xs"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
      {nodes.map((node, i) => (
        <div key={node.node + i} className="flex items-center gap-1">
          {i > 0 && <span style={{ color: 'var(--text-muted)' }}>→</span>}
          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full ${
            node.status === 'running' ? 'animate-pulse' : ''
          }`} style={{
            background: node.status === 'done' ? 'var(--success)' : 'var(--accent)',
            color: '#fff',
          }}>
            {node.status === 'done' ? '✓' : '●'} {node.label}
            {node.duration_ms !== undefined && (
              <span className="opacity-70">{(node.duration_ms / 1000).toFixed(1)}s</span>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/NodeTracker.tsx
git commit -m "feat: add NodeTracker component for execution flow visualization"
```

---

### Task 12: Frontend Components — PlanView

**Files:**
- Create: `frontend/src/components/PlanView.tsx`

- [ ] **Step 1: Create PlanView.tsx**

```tsx
import { useState } from 'react';
import type { PlanStep } from '../types';

interface PlanViewProps {
  steps: PlanStep[];
}

const STATUS_ICONS: Record<PlanStep['status'], string> = {
  pending: '○',
  running: '🔄',
  done: '✅',
  failed: '❌',
};

export default function PlanView({ steps }: PlanViewProps) {
  const [expanded, setExpanded] = useState(true);

  return (
    <div className="mb-3 rounded-lg overflow-hidden"
      style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
      <div
        className="flex items-center justify-between px-4 py-2 cursor-pointer"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-xs font-medium" style={{ color: 'var(--accent-light)' }}>
          Plan ({steps.filter(s => s.status === 'done').length}/{steps.length})
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          {expanded ? '收起' : '展开'}
        </span>
      </div>
      {expanded && (
        <div className="px-4 pb-3">
          {steps.map((step, i) => (
            <div key={step.id} className="flex items-start gap-2 py-1">
              <span className="text-sm mt-0.5">{STATUS_ICONS[step.status]}</span>
              <div className="flex-1 min-w-0">
                <p className={`text-sm ${step.status === 'running' ? 'font-medium' : ''}`}
                  style={{ color: step.status === 'done' ? 'var(--text-muted)' : 'var(--text-primary)' }}>
                  {i + 1}. {step.title}
                </p>
                {step.description && step.status === 'running' && (
                  <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                    {step.description}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/PlanView.tsx
git commit -m "feat: add PlanView component for plan step visualization"
```

---

### Task 13: Frontend Components — InterruptDialog

**Files:**
- Create: `frontend/src/components/InterruptDialog.tsx`

- [ ] **Step 1: Create InterruptDialog.tsx**

```tsx
import { useState } from 'react';
import type { InterruptData, PlanStep } from '../types';

interface InterruptDialogProps {
  data: InterruptData;
  onAction: (action: 'approve' | 'reject' | 'edit', payload?: Record<string, unknown>) => void;
}

export default function InterruptDialog({ data, onAction }: InterruptDialogProps) {
  const [editedSteps, setEditedSteps] = useState<PlanStep[] | null>(null);

  if (data.type === 'plan') {
    const steps = editedSteps || data.payload.steps || [];
    return (
      <div className="mb-4 rounded-lg p-4" style={{
        background: 'var(--bg-surface)',
        border: '2px solid var(--accent)',
      }}>
        <p className="text-sm font-medium mb-3" style={{ color: 'var(--accent-light)' }}>
          Plan Confirmation
        </p>
        <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
          Review the plan below. You can approve, reject, or edit steps.
        </p>
        <div className="mb-3 space-y-2">
          {steps.map((step, i) => (
            <div key={step.id} className="flex items-start gap-2 p-2 rounded"
              style={{ background: 'var(--bg-primary)' }}>
              <span className="text-xs mt-1 font-mono" style={{ color: 'var(--text-muted)' }}>
                {i + 1}.
              </span>
              <div className="flex-1">
                <input
                  className="w-full text-sm bg-transparent border-none outline-none"
                  style={{ color: 'var(--text-primary)' }}
                  value={step.title}
                  onChange={(e) => {
                    const newSteps = [...steps];
                    newSteps[i] = { ...step, title: e.target.value };
                    setEditedSteps(newSteps);
                  }}
                />
                <input
                  className="w-full text-xs bg-transparent border-none outline-none mt-1"
                  style={{ color: 'var(--text-secondary)' }}
                  value={step.description}
                  onChange={(e) => {
                    const newSteps = [...steps];
                    newSteps[i] = { ...step, description: e.target.value };
                    setEditedSteps(newSteps);
                  }}
                />
              </div>
              <button
                className="text-xs px-1 hover:opacity-70"
                style={{ color: 'var(--error)' }}
                onClick={() => {
                  const newSteps = steps.filter((_, j) => j !== i);
                  setEditedSteps(newSteps);
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <div className="flex gap-2">
          <button
            className="px-3 py-1.5 rounded-lg text-sm text-white"
            style={{ background: 'var(--success)' }}
            onClick={() => {
              if (editedSteps) {
                onAction('edit', { steps: editedSteps });
              } else {
                onAction('approve');
              }
            }}
          >
            {editedSteps ? 'Approve Edited Plan' : 'Approve'}
          </button>
          <button
            className="px-3 py-1.5 rounded-lg text-sm"
            style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}
            onClick={() => onAction('reject')}
          >
            Reject
          </button>
        </div>
      </div>
    );
  }

  // Tool confirmation
  return (
    <div className="mb-4 rounded-lg p-4" style={{
      background: 'var(--bg-surface)',
      border: '2px solid var(--accent)',
    }}>
      <p className="text-sm font-medium mb-2" style={{ color: 'var(--accent-light)' }}>
        Tool Confirmation
      </p>
      <p className="text-xs mb-2" style={{ color: 'var(--text-secondary)' }}>
        The agent wants to use the following tool. Approve or reject?
      </p>
      <div className="p-2 rounded mb-3 font-mono text-sm" style={{ background: 'var(--bg-primary)', color: 'var(--success)' }}>
        {data.payload.tool_name}({JSON.stringify(data.payload.arguments, null, 2)})
      </div>
      <div className="flex gap-2">
        <button
          className="px-3 py-1.5 rounded-lg text-sm text-white"
          style={{ background: 'var(--success)' }}
          onClick={() => onAction('approve')}
        >
          Approve
        </button>
        <button
          className="px-3 py-1.5 rounded-lg text-sm"
          style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-color)' }}
          onClick={() => onAction('reject')}
        >
          Reject
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/InterruptDialog.tsx
git commit -m "feat: add InterruptDialog component for plan/tool confirmation"
```

---

### Task 14: Update chatStore — Handle New Events

**Files:**
- Modify: `frontend/src/stores/chatStore.ts`

- [ ] **Step 1: Add new state fields to ChatState interface**

In `frontend/src/stores/chatStore.ts`, update the `ChatState` interface to add:

```typescript
  interruptData: InterruptData | null;
  planSteps: PlanStep[];
  activeNodes: NodeStatus[];
  resumeInterrupt: (action: string, payload?: Record<string, unknown>) => Promise<void>;
```

Add imports at the top:

```typescript
import type { Conversation, KnowledgeBase, Message, Skill, SSEEvent, InterruptData, PlanStep, NodeStatus } from '../types';
import { createSSEStream } from '../hooks/useSSE';
```

- [ ] **Step 2: Add initial state values**

In the store's return object, add:

```typescript
    interruptData: null,
    planSteps: [],
    activeNodes: [],
```

- [ ] **Step 3: Update sendMessage SSE event handler**

In the `sendMessage` function's SSE `onEvent` callback, add cases for new events. Replace the switch statement:

```typescript
      await sse.stream('http://localhost:8000/api/chat/send', { conversation_id: convId, content }, (event: SSEEvent) => {
        switch (event.event) {
          case 'text': {
            assistantContent += (event.data as { content: string }).content;
            set((state) => {
              const msgs = [...state.messages];
              const lastMsg = msgs[msgs.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                msgs[msgs.length - 1] = { ...lastMsg, content: assistantContent };
              } else {
                msgs.push({
                  id: `stream-${Date.now()}`,
                  conversation_id: convId,
                  role: 'assistant',
                  content: assistantContent,
                  tool_calls: null,
                  tool_call_id: null,
                  agent_steps: null,
                  created_at: new Date().toISOString(),
                });
              }
              return { messages: msgs };
            });
            break;
          }
          case 'thinking':
          case 'tool_call':
          case 'tool_result': {
            set((state) => ({ agentEvents: [...state.agentEvents, event] }));
            break;
          }
          case 'node_enter': {
            const d = event.data as { node: string; label: string };
            set((state) => ({
              activeNodes: [...state.activeNodes, { node: d.node, label: d.label, status: 'running' as const }],
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'node_exit': {
            const d = event.data as { node: string; duration_ms: number };
            set((state) => ({
              activeNodes: state.activeNodes.map((n) =>
                n.node === d.node ? { ...n, status: 'done' as const, duration_ms: d.duration_ms } : n
              ),
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'plan': {
            const d = event.data as { steps: PlanStep[] };
            set((state) => ({
              planSteps: d.steps,
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'plan_step_update': {
            const d = event.data as { step_id: string; status: string };
            set((state) => ({
              planSteps: state.planSteps.map((s) =>
                s.id === d.step_id ? { ...s, status: d.status as PlanStep['status'] } : s
              ),
              agentEvents: [...state.agentEvents, event],
            }));
            break;
          }
          case 'interrupt': {
            const d = event.data as InterruptData;
            set({ interruptData: d, isStreaming: false });
            break;
          }
          case 'done': {
            set({ agentEvents: [], isStreaming: false, activeNodes: [], planSteps: [], interruptData: null });
            get().fetchConversations();
            break;
          }
        }
      });
```

- [ ] **Step 4: Add resumeInterrupt action**

Add after the `sendMessage` function:

```typescript
    resumeInterrupt: async (action: string, payload: Record<string, unknown> = {}) => {
      const convId = get().currentConversationId;
      if (!convId) return;

      set({ isStreaming: true, interruptData: null });

      let assistantContent = '';

      await sse.stream('http://localhost:8000/api/chat/resume', {
        conversation_id: convId,
        action,
        payload,
      }, (event: SSEEvent) => {
        switch (event.event) {
          case 'text': {
            assistantContent += (event.data as { content: string }).content;
            set((state) => {
              const msgs = [...state.messages];
              const lastMsg = msgs[msgs.length - 1];
              if (lastMsg && lastMsg.role === 'assistant') {
                msgs[msgs.length - 1] = { ...lastMsg, content: assistantContent };
              } else {
                msgs.push({
                  id: `stream-${Date.now()}`,
                  conversation_id: convId,
                  role: 'assistant',
                  content: assistantContent,
                  tool_calls: null,
                  tool_call_id: null,
                  agent_steps: null,
                  created_at: new Date().toISOString(),
                });
              }
              return { messages: msgs };
            });
            break;
          }
          case 'thinking':
          case 'tool_call':
          case 'tool_result':
          case 'node_enter':
          case 'node_exit':
          case 'plan':
          case 'plan_step_update': {
            set((state) => ({ agentEvents: [...state.agentEvents, event] }));
            break;
          }
          case 'interrupt': {
            const d = event.data as InterruptData;
            set({ interruptData: d, isStreaming: false });
            break;
          }
          case 'done': {
            set({ agentEvents: [], isStreaming: false, activeNodes: [], planSteps: [], interruptData: null });
            get().fetchConversations();
            break;
          }
        }
      });

      set({ isStreaming: false });
    },
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/stores/chatStore.ts
git commit -m "feat: update chatStore with LangGraph event handling and resume support"
```

---

### Task 15: Update AgentStep — New Event Rendering

**Files:**
- Modify: `frontend/src/components/AgentStep.tsx`

- [ ] **Step 1: Update AgentStep to handle new events**

Replace the content of `frontend/src/components/AgentStep.tsx`:

```tsx
import { useState } from 'react';
import type { SSEEvent } from '../types';

interface AgentStepProps {
  event: SSEEvent;
}

export default function AgentStep({ event }: AgentStepProps) {
  const [expanded, setExpanded] = useState(false);

  switch (event.event) {
    case 'thinking': {
      const content = (event.data as { content: string }).content;
      return (
        <div className="mb-2 border-l-2 rounded-r-lg px-4 py-2" style={{ borderLeftColor: 'var(--accent-light)', background: 'var(--bg-surface)' }}>
          <p className="text-xs mb-1 font-medium" style={{ color: 'var(--accent-light)' }}>Thinking</p>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{content}</p>
        </div>
      );
    }

    case 'tool_call': {
      const data = event.data as { name: string; arguments: unknown };
      let argsStr = '';
      if (typeof data.arguments === 'string') {
        try { argsStr = JSON.stringify(JSON.parse(data.arguments), null, 2); } catch { argsStr = data.arguments; }
      } else {
        argsStr = JSON.stringify(data.arguments, null, 2);
      }
      return (
        <div className="mb-2 rounded-lg px-4 py-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
          <p className="text-xs mb-1 font-medium" style={{ color: 'var(--text-muted)' }}>Tool Call</p>
          <p className="text-sm font-mono" style={{ color: 'var(--success)' }}>
            {data.name}({argsStr.length > 200 ? argsStr.slice(0, 200) + '...' : argsStr})
          </p>
        </div>
      );
    }

    case 'tool_result': {
      const data = event.data as { name: string; result: string };
      const content = data.result;
      const isLong = content.length > 300;
      return (
        <div className="mb-2 rounded-lg px-4 py-2" style={{ background: 'var(--bg-surface)', border: '1px solid var(--border-color)' }}>
          <div className="flex items-center justify-between cursor-pointer" onClick={() => setExpanded(!expanded)}>
            <p className="text-xs font-medium" style={{ color: 'var(--text-muted)' }}>Tool Result</p>
            {isLong && (
              <span className="text-xs cursor-pointer" style={{ color: 'var(--accent-light)' }}>
                {expanded ? '收起' : '展开'}
              </span>
            )}
          </div>
          <pre className="text-sm whitespace-pre-wrap font-mono mt-1" style={{ color: 'var(--text-secondary)' }}>
            {isLong && !expanded ? content.slice(0, 300) + '...' : content}
          </pre>
        </div>
      );
    }

    case 'node_enter':
    case 'node_exit':
    case 'plan':
    case 'plan_step_update':
    case 'interrupt':
      // These are handled by dedicated components (NodeTracker, PlanView, InterruptDialog)
      return null;

    default:
      return null;
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AgentStep.tsx
git commit -m "feat: update AgentStep to handle new LangGraph event types"
```

---

### Task 16: Update ChatArea — Integrate New Components

**Files:**
- Modify: `frontend/src/components/ChatArea.tsx`

- [ ] **Step 1: Add imports**

At the top of `frontend/src/components/ChatArea.tsx`, add:

```typescript
import NodeTracker from './NodeTracker';
import PlanView from './PlanView';
import InterruptDialog from './InterruptDialog';
```

- [ ] **Step 2: Add new state selectors**

In the component, add these selectors alongside the existing ones:

```typescript
  const interruptData = useChatStore((s) => s.interruptData);
  const planSteps = useChatStore((s) => s.planSteps);
  const activeNodes = useChatStore((s) => s.activeNodes);
  const resumeInterrupt = useChatStore((s) => s.resumeInterrupt);
```

- [ ] **Step 3: Add components to the message rendering area**

In the messages section of the JSX (after the agent events loop and before the streaming dots), add:

```tsx
          {/* Node execution tracker */}
          {activeNodes.length > 0 && <NodeTracker nodes={activeNodes} />}

          {/* Plan view */}
          {planSteps.length > 0 && <PlanView steps={planSteps} />}

          {/* Interrupt dialog */}
          {interruptData && (
            <InterruptDialog
              data={interruptData}
              onAction={(action, payload) => resumeInterrupt(action, payload)}
            />
          )}
```

- [ ] **Step 4: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds without type errors

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ChatArea.tsx
git commit -m "feat: integrate NodeTracker, PlanView, InterruptDialog into ChatArea"
```

---

### Task 17: Integration Smoke Test

- [ ] **Step 1: Start backend**

Run: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`

Verify: Server starts without import errors.

- [ ] **Step 2: Start frontend**

Run: `cd frontend && npm run dev`

Verify: Vite dev server starts, page loads at http://localhost:5173.

- [ ] **Step 3: Test simple agent path**

1. Create a new conversation in agentic mode
2. Select a skill (or none)
3. Send a simple message like "Hello"
4. Verify: `node_enter(router)` → `node_exit(router)` → `node_enter(agent)` → `text` → `node_exit(agent)` → `node_enter(respond)` → `node_exit(respond)` → `done` events flow correctly
5. Verify: NodeTracker shows the execution flow
6. Verify: Final text renders as a message bubble

- [ ] **Step 4: Test plan path (if a skill with planning_mode="always" exists)**

1. Create/update a skill with `planning_mode: "always"` and `confirm_plan: true`
2. Send a complex request
3. Verify: Plan renders in PlanView
4. Verify: InterruptDialog appears for plan confirmation
5. Click Approve
6. Verify: Executor steps execute and plan_step_update events update PlanView

- [ ] **Step 5: Commit final state**

```bash
git add -A
git commit -m "feat: complete LangGraph agent refactor with full execution visualization"
```
