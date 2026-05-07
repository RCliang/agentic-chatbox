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
