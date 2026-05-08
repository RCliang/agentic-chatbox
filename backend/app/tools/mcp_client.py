"""Generic MCP JSON-RPC client for calling remote MCP tools via HTTP SSE."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def call_mcp_tool(
    server_url: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    timeout: float = 60,
) -> str:
    """Call a remote MCP tool using JSON-RPC 2.0 over HTTP and parse the SSE response.

    Args:
        server_url: Base URL of the MCP server (may include query params like api_key).
        tool_name: Name of the tool on the MCP server.
        arguments: Tool arguments dict.
        timeout: HTTP request timeout in seconds.

    Returns:
        The tool result as a string.
    """
    payload = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "id": 1,
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }

    logger.debug("MCP call: url=%s tool=%s args=%s", server_url, tool_name, arguments)

    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream(
            "POST",
            server_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        ) as resp:
            resp.raise_for_status()

            # Parse SSE stream, accumulate data lines
            result_data: dict[str, Any] | None = None
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[len("data:"):].strip()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                # Look for the final result (has "result" key from tools/call)
                if "result" in msg:
                    result_data = msg["result"]

    if result_data is None:
        return "Error: no result received from MCP server."

    # Extract text content from MCP result
    if "content" in result_data:
        contents = result_data["content"]
        if isinstance(contents, list):
            texts = [
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in contents
            ]
            return "\n".join(texts)
        return str(contents)

    return json.dumps(result_data, ensure_ascii=False)
