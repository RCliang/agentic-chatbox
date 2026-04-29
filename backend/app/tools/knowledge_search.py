"""Knowledge search builtin tool using RAG retrieval."""

import asyncio

from app.services.tools import tool_registry


def knowledge_search(
    query: str,
    knowledge_base_id: str,
    top_k: int = 5,
) -> str:
    """Search a knowledge base for relevant documents using RAG.

    Args:
        query: The search query string.
        knowledge_base_id: UUID of the knowledge base to search.
        top_k: Maximum number of results to return.

    Returns:
        A formatted string with ranked results.
    """
    from app.services.knowledge import retrieve

    results = asyncio.run(retrieve([knowledge_base_id], query, top_k))
    if not results:
        return "No relevant documents found."

    output = [
        f"[{i + 1}] (score: {r['score']:.3f}) {r['text'][:500]}"
        for i, r in enumerate(results)
    ]
    return "\n".join(output)


tool_registry.register("knowledge_search", knowledge_search)
