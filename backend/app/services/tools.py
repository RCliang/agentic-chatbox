"""ToolRegistry: builtin tool dispatch and MCP client proxy.

Provides a unified interface for executing both builtin Python tools
and remote MCP (Model Context Protocol) tools via HTTP.
"""

import inspect
import json
import logging
from typing import Any, Callable

import httpx

from app.models import Tool, ToolType

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for builtin tools with MCP fallback support.

    Builtin tools are registered in-memory as ``{name: callable}`` pairs.
    MCP tools are looked up from the database and called via HTTP POST to
    ``{mcp_server_url}/tools/call``.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, Callable] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, name: str, handler: Callable) -> None:
        """Register a builtin tool handler.

        Args:
            name: Unique tool name.
            handler: A callable that accepts keyword arguments and returns a string.
        """
        self._handlers[name] = handler
        logger.debug("Registered builtin tool: %s", name)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        db=None,
    ) -> str:
        """Execute a tool by name.

        For builtin tools the handler is called directly (synchronous handlers
        are wrapped so the caller can always ``await`` the result).

        For MCP tools an HTTP POST is sent to ``{mcp_server_url}/tools/call``.

        Args:
            tool_name: The name of the tool to execute.
            arguments: Keyword arguments forwarded to the tool handler.
            db: Optional async database session (used to look up MCP tools).

        Returns:
            The tool result as a string.
        """
        # Try builtin first
        if tool_name in self._handlers:
            handler = self._handlers[tool_name]
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(**arguments)
                else:
                    # Run sync handler in a thread to avoid blocking the event loop
                    loop = __import__("asyncio").get_event_loop()
                    result = await loop.run_in_executor(None, lambda: handler(**arguments))
                return str(result) if result is not None else ""
            except Exception as exc:
                logger.exception("Builtin tool %s failed", tool_name)
                return f"Error executing tool '{tool_name}': {exc}"

        # Fall back to MCP tool lookup via DB
        if db is not None:
            from sqlalchemy import select

            stmt = select(Tool).where(
                Tool.name == tool_name,
                Tool.type == ToolType.mcp,
                Tool.is_enabled.is_(True),
            )
            result = await db.execute(stmt)
            mcp_tool = result.scalar_one_or_none()

            if mcp_tool is not None:
                return await self._call_mcp(
                    mcp_server_url=mcp_tool.mcp_server_url,
                    mcp_tool_name=mcp_tool.mcp_tool_name or tool_name,
                    arguments=arguments,
                )

        return f"Error: tool '{tool_name}' not found."

    # ------------------------------------------------------------------
    # MCP HTTP client
    # ------------------------------------------------------------------

    @staticmethod
    async def _call_mcp(
        mcp_server_url: str,
        mcp_tool_name: str,
        arguments: dict[str, Any],
    ) -> str:
        """Call a remote MCP tool via HTTP POST.

        Args:
            mcp_server_url: Base URL of the MCP server.
            mcp_tool_name: Name of the tool on the MCP server.
            arguments: Tool arguments dict.

        Returns:
            The tool result as a string.
        """
        url = f"{mcp_server_url.rstrip('/')}/tools/call"
        payload = {
            "name": mcp_tool_name,
            "arguments": arguments,
        }
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                data = resp.json()
                # MCP tools/call response shape: {"content": [{"type": "text", "text": "..."}]}
                if isinstance(data, dict) and "content" in data:
                    texts = [
                        item["text"]
                        for item in data["content"]
                        if item.get("type") == "text"
                    ]
                    return "\n".join(texts)
                return json.dumps(data)
        except httpx.HTTPError as exc:
            logger.exception("MCP call to %s failed", url)
            return f"Error calling MCP tool '{mcp_tool_name}': {exc}"

    # ------------------------------------------------------------------
    # Schema generation
    # ------------------------------------------------------------------

    async def get_tool_schemas(
        self,
        tool_ids: list[str] | None = None,
        db=None,
    ) -> list[dict]:
        """Return OpenAI-compatible tool schema list.

        For builtin tools, the schema is inferred from the function signature.
        For MCP tools registered in the DB, the stored ``parameters_schema``
        is used.

        Args:
            tool_ids: Optional list of tool names to include.  If ``None``,
                all registered builtin tools (and, when *db* is provided,
                all enabled MCP tools) are included.
            db: Optional async database session for MCP tool lookup.

        Returns:
            A list of OpenAI tool dicts, e.g.:
            ``{"type": "function", "function": {"name": ..., "parameters": ...}}``
        """
        schemas: list[dict] = []

        # Builtin tools
        for name, handler in self._handlers.items():
            if tool_ids is not None and name not in tool_ids:
                continue
            schema = self._function_to_schema(name, handler)
            schemas.append(schema)

        # MCP tools from DB
        if db is not None:
            from sqlalchemy import select

            stmt = select(Tool).where(
                Tool.type == ToolType.mcp,
                Tool.is_enabled.is_(True),
            )
            if tool_ids is not None:
                stmt = stmt.where(Tool.name.in_(tool_ids))

            result = await db.execute(stmt)
            for mcp_tool in result.scalars().all():
                if tool_ids is not None and mcp_tool.name not in tool_ids:
                    continue
                schemas.append(
                    {
                        "type": "function",
                        "function": {
                            "name": mcp_tool.name,
                            "description": mcp_tool.description or "",
                            "parameters": mcp_tool.parameters_schema or {
                                "type": "object",
                                "properties": {},
                            },
                        },
                    }
                )

        return schemas

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _function_to_schema(name: str, handler: Callable) -> dict:
        """Build an OpenAI-compatible tool schema from a Python function.

        Uses the first paragraph of the docstring as the description and
        infers JSON Schema properties from type annotations.
        """
        sig = inspect.signature(handler)
        doc = inspect.getdoc(handler) or ""
        description = doc.split("\n\n")[0].strip()

        properties: dict[str, Any] = {}
        required: list[str] = []

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue

            # Determine JSON type from annotation
            annotation = param.annotation
            if annotation is inspect.Parameter.empty:
                json_type = "string"
            else:
                origin = getattr(annotation, "__origin__", None)
                if origin is list:
                    json_type = "array"
                elif origin is dict:
                    json_type = "object"
                elif annotation is int:
                    json_type = "integer"
                elif annotation is float:
                    json_type = "number"
                elif annotation is bool:
                    json_type = "boolean"
                else:
                    json_type = "string"

            properties[param_name] = {"type": json_type}

            if param.default is inspect.Parameter.empty:
                required.append(param_name)

        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

tool_registry = ToolRegistry()


# ---------------------------------------------------------------------------
# Auto-register all builtin tools
# ---------------------------------------------------------------------------


def register_builtin_tools() -> None:
    """Import all builtin tool modules to trigger their registrations.

    Each tool module calls ``tool_registry.register(...)`` at import time,
    so simply importing the package is enough.
    """
    import importlib

    try:
        importlib.import_module("app.tools.web_search")
    except ImportError:
        logger.warning("Could not import app.tools.web_search")

    try:
        importlib.import_module("app.tools.web_reader")
    except ImportError:
        logger.warning("Could not import app.tools.web_reader")

    try:
        importlib.import_module("app.tools.knowledge_search")
    except ImportError:
        logger.warning("Could not import app.tools.knowledge_search")
