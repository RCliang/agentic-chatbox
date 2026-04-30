"""KnowledgeBaseShare model — tracks knowledge base sharing between users."""

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class KnowledgeBaseShare(BaseMixin):
    __tablename__ = "knowledge_base_shares"
    __table_args__ = (
        UniqueConstraint("knowledge_base_id", "shared_with_user_id", name="uq_kb_share"),
    )

    knowledge_base_id: Mapped[str] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id", ondelete="CASCADE"),
        nullable=False,
    )
    shared_with_user_id: Mapped[str] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # relationships
    knowledge_base: Mapped["KnowledgeBase"] = relationship(
        "KnowledgeBase",
        back_populates="shares",
    )
    shared_with_user: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<KnowledgeBaseShare kb={self.knowledge_base_id} user={self.shared_with_user_id}>"
