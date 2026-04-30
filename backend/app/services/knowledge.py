"""Knowledge service: text chunking, embedding, and Milvus retrieval."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy import select

from app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models import User

logger = logging.getLogger(__name__)

GLOBAL_COLLECTION = "knowledge_chunks"


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
# Accessible KB IDs
# ---------------------------------------------------------------------------


async def get_accessible_kb_ids(db: AsyncSession, user: User) -> list[str]:
    """Return all knowledge base IDs that *user* can access.

    Includes: personal KBs owned by user + department KBs + shared KBs.
    """
    from app.models import KnowledgeBase, KnowledgeBaseScope, KnowledgeBaseShare

    # Personal
    personal_q = select(KnowledgeBase.id).where(
        KnowledgeBase.scope == KnowledgeBaseScope.personal,
        KnowledgeBase.owner_id == user.id,
    )
    # Department
    dept_q = select(KnowledgeBase.id).where(
        KnowledgeBase.scope == KnowledgeBaseScope.department,
        KnowledgeBase.department_id == user.department_id,
    )
    # Shared
    shared_q = select(KnowledgeBaseShare.knowledge_base_id).where(
        KnowledgeBaseShare.shared_with_user_id == user.id,
    )

    results = set()
    for q in (personal_q, dept_q, shared_q):
        rows = await db.execute(q)
        for (kb_id,) in rows.all():
            results.add(str(kb_id))

    return list(results)


# ---------------------------------------------------------------------------
# Milvus retrieval
# ---------------------------------------------------------------------------


async def retrieve(
    kb_ids: list[str],
    query: str,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Search the global Milvus collection for chunks matching *query*.

    Uses a filter expression ``kb_id in [...]`` to restrict results to the
    given knowledge base IDs.
    """
    if not kb_ids:
        return []

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

    try:
        from pymilvus import utility

        if not utility.has_collection(GLOBAL_COLLECTION):
            logger.info("Collection %s does not exist yet", GLOBAL_COLLECTION)
            return []

        collection = Collection(GLOBAL_COLLECTION)
        collection.load()

        # Build filter expression
        ids_str = ", ".join(f'"{kb_id}"' for kb_id in kb_ids)
        filter_expr = f"kb_id in [{ids_str}]"

        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 16},
        }

        results = collection.search(
            data=[query_vector],
            anns_field="embedding",
            param=search_params,
            limit=top_k,
            expr=filter_expr,
            output_fields=["text", "doc_id", "kb_id", "chunk_index"],
        )

        all_results: list[dict[str, Any]] = []
        for hit in results[0]:
            all_results.append(
                {
                    "score": hit.score,
                    "text": hit.entity.get("text", ""),
                    "doc_id": hit.entity.get("doc_id", ""),
                    "kb_id": hit.entity.get("kb_id", ""),
                    "chunk_index": hit.entity.get("chunk_index", 0),
                }
            )

        all_results.sort(key=lambda x: x["score"], reverse=True)
        return all_results[:top_k]

    except Exception:
        logger.warning("Failed to query collection %s", GLOBAL_COLLECTION, exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Build RAG context
# ---------------------------------------------------------------------------


async def get_kb_context(
    db: AsyncSession | None = None,
    knowledge_base_id: str = "",
    query: str = "",
) -> str:
    """Build a RAG context string from a single knowledge base."""
    results = await retrieve([knowledge_base_id], query, top_k=5)
    if not results:
        return ""

    parts: list[str] = []
    for idx, r in enumerate(results, 1):
        parts.append(f"[{idx}] {r['text']}")

    return "\n\n".join(parts)
