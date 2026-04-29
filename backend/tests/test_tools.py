"""Tests for ToolRegistry — builtin registration, execution, and schema generation."""

import pytest

from app.services.tools import ToolRegistry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def registry():
    """Return a fresh ToolRegistry for each test."""
    return ToolRegistry()


def dummy_echo(text: str) -> str:
    """Echo the input text back."""
    return text


def add(a: int, b: int) -> int:
    """Add two integers together."""
    return a + b


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolRegistryBuiltin:
    """Tests for builtin tool registration and schema generation."""

    async def test_registry_builtin(self, registry):
        """Register a dummy tool and verify get_tool_schemas returns it."""
        registry.register("dummy_echo", dummy_echo)

        schemas = await registry.get_tool_schemas()
        assert len(schemas) == 1

        schema = schemas[0]
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "dummy_echo"
        assert schema["function"]["description"] == "Echo the input text back."

        params = schema["function"]["parameters"]
        assert params["type"] == "object"
        assert "text" in params["properties"]
        assert params["properties"]["text"]["type"] == "string"
        assert "text" in params["required"]

    async def test_get_tool_schemas_filters_by_ids(self, registry):
        """get_tool_schemas should only return tools whose names are in tool_ids."""
        registry.register("dummy_echo", dummy_echo)
        registry.register("add", add)

        schemas = await registry.get_tool_schemas(tool_ids=["add"])
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "add"

    async def test_get_tool_schemas_empty_registry(self, registry):
        """get_tool_schemas returns empty list when no tools are registered."""
        schemas = await registry.get_tool_schemas()
        assert schemas == []

    async def test_schema_includes_defaults_as_optional(self, registry):
        """Parameters with defaults should not appear in 'required'."""

        def greet(name: str, greeting: str = "hello") -> str:
            """Greet someone."""
            return f"{greeting}, {name}!"

        registry.register("greet", greet)
        schemas = await registry.get_tool_schemas()
        assert len(schemas) == 1

        params = schemas[0]["function"]["parameters"]
        assert "name" in params["required"]
        assert "greeting" not in params["required"]


class TestToolRegistryExecution:
    """Tests for tool execution."""

    async def test_execute_builtin(self, registry):
        """Register an add function, execute it, and verify the result."""
        registry.register("add", add)

        result = await registry.execute("add", {"a": 3, "b": 4})
        assert result == "7"

    async def test_execute_builtin_sync_string(self, registry):
        """Sync handler returning a string should work."""
        registry.register("dummy_echo", dummy_echo)

        result = await registry.execute("dummy_echo", {"text": "hello"})
        assert result == "hello"

    async def test_execute_not_found(self, registry):
        """Executing a non-existent tool should return a 'not found' error."""
        result = await registry.execute("nonexistent_tool", {"arg": 1})
        assert "not found" in result
        assert "nonexistent_tool" in result

    async def test_execute_builtin_handler_error(self, registry):
        """If a builtin handler raises, the error message should be returned."""

        def bad_tool(x: int) -> int:
            """Always fails."""
            raise ValueError("something went wrong")

        registry.register("bad_tool", bad_tool)
        result = await registry.execute("bad_tool", {"x": 1})
        assert "Error" in result
        assert "something went wrong" in result

    async def test_execute_async_builtin(self, registry):
        """An async builtin handler should work correctly."""

        async def async_greet(name: str) -> str:
            """Greet asynchronously."""
            return f"Hello, {name}!"

        registry.register("async_greet", async_greet)
        result = await registry.execute("async_greet", {"name": "World"})
        assert result == "Hello, World!"
