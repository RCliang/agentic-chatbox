"""Skill model — modular skill definition with progressive loading support."""

from sqlalchemy import Boolean, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class Skill(BaseMixin):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ---- Modular content ----
    instructions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    tools: Mapped[list | None] = mapped_column(JSON, nullable=True)
    references: Mapped[list | None] = mapped_column(JSON, nullable=True)
    examples: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Legacy / convenience
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id"),
        nullable=True,
    )

    # relationships
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="skill",
    )

    def __repr__(self) -> str:
        return f"<Skill id={self.id} name={self.name!r}>"
