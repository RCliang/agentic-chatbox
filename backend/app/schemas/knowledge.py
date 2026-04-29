"""Pydantic schemas for knowledge base endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    scope: str = "personal"
    department_id: uuid.UUID | None = None
    embedding_model: str = "text-embedding-ada-002"
    chunk_size: int = 512
    chunk_overlap: int = 50


class KnowledgeBaseResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    scope: str
    owner_id: uuid.UUID
    department_id: uuid.UUID | None = None
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    milvus_collection: str | None = None
    document_count: int = 0
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_type: str
    title: str
    file_path: str | None = None
    feishu_doc_id: str | None = None
    uploaded_by: uuid.UUID
    status: str
    chunk_count: int
    indexed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
