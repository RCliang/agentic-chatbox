"""Message model."""

import enum

from sqlalchemy import Enum, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class MessageRole(str, enum.Enum):
    user = "user"
    assistant = "assistant"
    tool = "tool"
    system = "system"


class Message(BaseMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[str] = mapped_column(
        Uuid,
        ForeignKey("conversations.id"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        Enum(MessageRole, name="message_role", native_enum=False),
        nullable=False,
    )
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_steps: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)

    # relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role.value} conversation_id={self.conversation_id}>"
