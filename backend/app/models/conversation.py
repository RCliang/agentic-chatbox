"""Conversation model."""

import enum

from sqlalchemy import Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class ConversationMode(str, enum.Enum):
    normal = "normal"
    agentic = "agentic"


class Conversation(BaseMixin):
    __tablename__ = "conversations"

    user_id: Mapped[str] = mapped_column(
        Uuid,
        ForeignKey("users.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    mode: Mapped[ConversationMode] = mapped_column(
        Enum(ConversationMode, name="conversation_mode", native_enum=False),
        default=ConversationMode.normal,
        nullable=False,
    )
    skill_id: Mapped[str | None] = mapped_column(
        Uuid,
        ForeignKey("skills.id"),
        nullable=True,
    )
    knowledge_base_id: Mapped[str | None] = mapped_column(
        Uuid,
        ForeignKey("knowledge_bases.id"),
        nullable=True,
    )
    enabled_tools: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)

    # relationships
    user: Mapped["User"] = relationship("User", back_populates="conversations")
    skill: Mapped["Skill | None"] = relationship("Skill", back_populates="conversations")
    knowledge_base: Mapped["KnowledgeBase | None"] = relationship(
        "KnowledgeBase",
        back_populates="conversations",
    )
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} title={self.title!r} mode={self.mode.value}>"
