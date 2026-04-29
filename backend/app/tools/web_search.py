"""Web search builtin tool (placeholder implementation)."""

from app.services.tools import tool_registry


def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for the given query.

    Args:
        query: The search query string.
        max_results: Maximum number of results to return.

    Returns:
        A string with search results.
    """
    return f"[web_search] Searched for: {query}. Found {max_results} results (placeholder)."


tool_registry.register("web_search", web_search)
