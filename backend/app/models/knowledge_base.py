"""KnowledgeBase model."""

import enum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class KnowledgeBaseScope(str, enum.Enum):
    personal = "personal"
    department = "department"


class KnowledgeBase(BaseMixin):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[KnowledgeBaseScope] = mapped_column(
        Enum(KnowledgeBaseScope, name="knowledge_base_scope", native_enum=False),
        nullable=False,
    )
    owner_id: Mapped[str] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )
    department_id: Mapped[str | None] = mapped_column(
        Uuid,
        ForeignKey("departments.id"),
        nullable=True,
    )
    embedding_model: Mapped[str] = mapped_column(
        String(255),
        default="text-embedding-ada-002",
        nullable=False,
    )
    chunk_size: Mapped[int] = mapped_column(Integer, default=512, nullable=False)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    milvus_collection: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="knowledge_base",
    )
    documents: Mapped[list["KnowledgeDocument"]] = relationship(
        "KnowledgeDocument",
        back_populates="knowledge_base",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeBase id={self.id} name={self.name!r} scope={self.scope.value}>"
