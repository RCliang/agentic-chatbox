"""KnowledgeDocument model."""

import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class DocumentSource(str, enum.Enum):
    upload = "upload"
    feishu = "feishu"


class DocumentStatus(str, enum.Enum):
    pending = "pending"
    indexing = "indexing"
    ready = "ready"
    failed = "failed"


class KnowledgeDocument(BaseMixin):
    __tablename__ = "knowledge_documents"

    knowledge_base_id: Mapped[str] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id"),
        nullable=False,
    )
    source_type: Mapped[DocumentSource] = mapped_column(
        Enum(DocumentSource, name="source_type", native_enum=False),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    feishu_doc_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[str] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", native_enum=False),
        default=DocumentStatus.pending,
        nullable=False,
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    indexed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        back_populates="documents",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument id={self.id} title={self.title!r} status={self.status.value}>"
