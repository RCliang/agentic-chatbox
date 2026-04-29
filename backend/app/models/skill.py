"""Skill model."""

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class Skill(BaseMixin):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    tool_ids: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id"),
        nullable=True,
    )
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="skill",
    )

    def __repr__(self) -> str:
        return f"<Skill id={self.id} name={self.name!r}>"
