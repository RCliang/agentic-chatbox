"""Department model."""

from sqlalchemy import ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseMixin


class Department(BaseMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    parent_id: Mapped[str | None] = mapped_column(
        Uuid,
        ForeignKey("departments.id"),
        nullable=True,
    )

    # relationships
    parent: Mapped["Department | None"] = relationship(
        "Department",
        remote_side="Department.id",
        back_populates="children",
    )
    children: Mapped[list["Department"]] = relationship(
        "Department",
        back_populates="parent",
    )
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="department",
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name!r}>"
