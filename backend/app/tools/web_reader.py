"""Web reader builtin tool (placeholder implementation)."""

from app.services.tools import tool_registry


def web_reader(url: str) -> str:
    """Read and extract content from a web URL.

    Args:
        url: The URL to read content from.

    Returns:
        A string with the page content.
    """
    return f"[web_reader] Read content from: {url} (placeholder)."


tool_registry.register("web_reader", web_reader)
