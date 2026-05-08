"""Web search builtin tool — calls the configured MCP websearch service."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import settings
from app.services.tools import tool_registry
from app.tools.mcp_client import call_mcp_tool

logger = logging.getLogger(__name__)


async def web_search(query: str) -> str:
    """Search the web for the given query and return results.

    Args:
        query: The search query string.

    Returns:
        A formatted string with search results including titles, URLs, and snippets.
    """
    server_url = settings.mcp_websearch_url
    if not server_url:
        return "Error: web search is not configured (MCP_WEBSEARCH_URL is empty)."

    # Append api_key as query parameter if configured
    if settings.mcp_websearch_api_key:
        sep = "&" if "?" in server_url else "?"
        server_url = f"{server_url}{sep}api_key={settings.mcp_websearch_api_key}"

    raw_result = await call_mcp_tool(
        server_url=server_url,
        tool_name="websearch",
        arguments={"input": query},
    )

    # Try to parse the JSON result and format it nicely
    try:
        data = json.loads(raw_result)
        if isinstance(data, dict) and "output" in data:
            return _format_search_results(data["output"], query)
    except (json.JSONDecodeError, TypeError):
        pass

    # Fallback: return raw text
    return raw_result


def _format_search_results(output: list[Any] | dict, query: str) -> str:
    """Format structured search results into readable text."""
    lines: list[str] = [f"Search results for: {query}\n"]

    # Handle the case where output is a list of items with "json" key
    items: list[dict] = []
    if isinstance(output, list):
        for item in output:
            if isinstance(item, dict) and "json" in item:
                items.append(item["json"])
            elif isinstance(item, dict) and "results" in item:
                items.extend(item["results"])
    elif isinstance(output, dict) and "results" in output:
        items = output["results"]

    if not items:
        # Fallback to raw json
        return json.dumps(output, ensure_ascii=False, indent=2)

    for i, item in enumerate(items, 1):
        title = item.get("title", "No title")
        url = item.get("url", item.get("displayUrl", ""))
        snippet = item.get("snippet", "")
        lines.append(f"[{i}] {title}")
        if url:
            lines.append(f"    URL: {url}")
        if snippet:
            lines.append(f"    {snippet}")
        lines.append("")

    return "\n".join(lines)


tool_registry.register("web_search", web_search)
