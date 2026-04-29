"""Knowledge service: text chunking, embedding, and Milvus retrieval."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import httpx

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Split *text* into overlapping chunks of roughly *chunk_size* characters.

    The function walks through *text* in strides of ``chunk_size - overlap``
    characters, producing chunks that are at most *chunk_size* characters long.
    Leading/trailing whitespace is stripped from each chunk, and empty chunks
    are dropped.
    """
    if not text:
        return []

    chunks: list[str] = []
    start = 0
    stride = max(chunk_size - overlap, 1)

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += stride

    return chunks


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


async def get_embedding(text: str) -> list[float]:
    """Return an embedding vector for *text* via the OpenAI-compatible API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.llm_base_url}/embeddings",
            json={"input": text, "model": settings.llm_default_model},
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        )
        resp.raise_for_status()
        data = resp.json()
        # OpenAI returns {"data": [{"embedding": [...]}]}
        return data["data"][0]["embedding"]


# ---------------------------------------------------------------------------
# Milvus retrieval
# ---------------------------------------------------------------------------


async def retrieve(
    kb_ids: list[str],
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search Milvus collections for chunks most similar to *query*.

    For each knowledge-base ID a separate collection ``kb_{kb_id}`` is
    queried.  Results from all collections are merged, sorted by descending
    score, and the top *top_k* entries are returned.

    The function degrades gracefully: if Milvus is unreachable or a
    collection does not exist, the error is logged and that collection is
    skipped.
    """
    try:
        from pymilvus import Collection, connections
    except ImportError:
        logger.warning("pymilvus not installed; retrieval is disabled")
        return []

    query_vector = await get_embedding(query)

    try:
        connections.connect(
            alias="default",
            uri=settings.milvus_uri,
        )
    except Exception:
        logger.warning("Could not connect to Milvus at %s", settings.milvus_uri)
        return []

    all_results: list[dict[str, Any]] = []

    for kb_id in kb_ids:
        collection_name = f"kb_{kb_id}"
        try:
            collection = Collection(collection_name)
            collection.load()

            search_params = {
                "metric_type": "COSINE",
                "params": {"nprobe": 16},
            }

            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param=search_params,
                limit=top_k,
                output_fields=["text", "doc_id", "chunk_index"],
            )

            for hit in results[0]:
                all_results.append(
                    {
                        "score": hit.score,
                        "text": hit.entity.get("text", ""),
                        "doc_id": hit.entity.get("doc_id", ""),
                        "chunk_index": hit.entity.get("chunk_index", 0),
                        "kb_id": kb_id,
                    }
                )
        except Exception:
            logger.warning("Failed to query collection %s", collection_name, exc_info=True)

    # Sort by score descending and take top_k
    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:top_k]


# ---------------------------------------------------------------------------
# Build RAG context
# ---------------------------------------------------------------------------


async def get_kb_context(
    db: AsyncSession | None = None,
    knowledge_base_id: str = "",
    query: str = "",
) -> str:
    """Build a RAG context string from a single knowledge base.

    The *db* parameter is accepted for backward compatibility with existing
    callers but is no longer required — the context is built entirely from
    Milvus retrieval.
    """
    results = await retrieve([knowledge_base_id], query, top_k=5)
    if not results:
        return ""

    parts: list[str] = []
    for idx, r in enumerate(results, 1):
        parts.append(f"[{idx}] {r['text']}")

    return "\n\n".join(parts)
