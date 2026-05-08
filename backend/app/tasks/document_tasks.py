"""Celery task for asynchronous document processing (chunking + embedding + Milvus indexing)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, update

from app.core.celery_app import celery_app
from app.core.config import settings
from app.models.base import Base
from app.models.knowledge_document import DocumentStatus, KnowledgeDocument
from app.services.knowledge import GLOBAL_COLLECTION, chunk_text, _milvus_connect

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sync DB helper for use inside Celery workers
# ---------------------------------------------------------------------------


def _get_sync_session():
    """Return a synchronous SQLAlchemy session bound to the configured DB."""
    from sqlalchemy.orm import Session

    sync_engine = create_engine(settings.database_url_sync, echo=False)
    SessionLocal = Session(sync_engine, expire_on_commit=False)
    return SessionLocal


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@celery_app.task(bind=True, max_retries=2)
def process_document(self, doc_id: str) -> dict:
    """Chunk, embed, and index a document into Milvus.

    Steps:
    1. Load document from DB, set status="indexing".
    2. Read the file from ``file_path``.
    3. Split text into overlapping chunks.
    4. Embed each chunk and insert into the global Milvus collection.
    5. Update document status to "ready" and record chunk_count.
    """
    session = _get_sync_session()
    try:
        # 1. Load document
        doc = session.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)
        ).scalar_one_or_none()
        if doc is None:
            logger.error("Document %s not found", doc_id)
            return {"error": "document not found"}

        # Set status to indexing
        session.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == doc_id)
            .values(status=DocumentStatus.indexing)
        )
        session.commit()

        # 2. Read file
        file_path = doc.file_path
        if not file_path:
            raise FileNotFoundError("document has no file_path")

        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

        # 3. Chunk text
        chunks = chunk_text(text)
        if not chunks:
            session.execute(
                update(KnowledgeDocument)
                .where(KnowledgeDocument.id == doc_id)
                .values(
                    status=DocumentStatus.failed,
                    chunk_count=0,
                )
            )
            session.commit()
            return {"error": "no chunks produced", "doc_id": doc_id}

        # 4-5. Embed and insert into Milvus (run async code in sync context)
        inserted_count = asyncio.run(
            _embed_and_insert(str(doc.knowledge_base_id), doc_id, chunks)
        )

        # 6. Mark ready
        session.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == doc_id)
            .values(
                status=DocumentStatus.ready,
                chunk_count=inserted_count,
                indexed_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        return {"doc_id": doc_id, "chunk_count": inserted_count}

    except Exception as exc:
        logger.exception("Failed to process document %s", doc_id)
        session.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == doc_id)
            .values(status=DocumentStatus.failed)
        )
        session.commit()
        raise self.retry(exc=exc, countdown=30)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _embed_and_insert(
    knowledge_base_id: str,
    doc_id: str,
    chunks: list[str],
) -> int:
    """Embed every chunk and insert into the global Milvus collection."""
    from pymilvus import Collection, CollectionSchema, DataType, FieldSchema

    from app.services.knowledge import get_embedding

    # Connect to Milvus
    _milvus_connect()

    # --- Determine embedding dimension by embedding the first chunk ---
    first_embedding = await get_embedding(chunks[0])
    dim = len(first_embedding)

    # --- Create global collection if it doesn't exist ---
    from pymilvus import utility

    if not utility.has_collection(GLOBAL_COLLECTION):
        fields = [
            FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
            FieldSchema(name="kb_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="chunk_index", dtype=DataType.INT64),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=4096),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
        ]
        schema = CollectionSchema(fields, description="Global knowledge chunks collection")
        collection = Collection(GLOBAL_COLLECTION, schema=schema)

        # Create IVF_FLAT index for COSINE similarity
        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name="embedding", index_params=index_params)
    else:
        collection = Collection(GLOBAL_COLLECTION)

    # --- Embed remaining chunks ---
    embeddings = [first_embedding]
    for chunk in chunks[1:]:
        emb = await get_embedding(chunk)
        embeddings.append(emb)

    # --- Prepare data for insertion ---
    ids = [str(uuid.uuid4()) for _ in chunks]
    kb_ids = [knowledge_base_id for _ in chunks]
    doc_ids = [doc_id for _ in chunks]
    chunk_indices = list(range(len(chunks)))

    entities = [
        ids,
        kb_ids,
        doc_ids,
        chunk_indices,
        chunks,
        embeddings,
    ]

    collection.insert(entities)
    collection.flush()
    return len(chunks)
