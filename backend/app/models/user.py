"""User model."""

from sqlalchemy import Boolean, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class User(BaseMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    department_id: Mapped[str | None] = mapped_column(
        Uuid,
        ForeignKey("departments.id"),
        nullable=True,
    )
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_dept_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # relationships
    department: Mapped["Department | None"] = relationship(
        "Department",
        back_populates="users",
    )
    conversations: Mapped[list["Conversation"]] = relationship(
        "Conversation",
        back_populates="user",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
