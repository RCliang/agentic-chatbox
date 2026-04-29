"""Tool model."""

import enum

from sqlalchemy import Boolean, Enum, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseMixin


class ToolType(str, enum.Enum):
    builtin = "builtin"
    mcp = "mcp"


class Tool(BaseMixin):
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters_schema: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    type: Mapped[ToolType] = mapped_column(
        Enum(ToolType, name="tool_type", native_enum=False),
        nullable=False,
    )
    handler: Mapped[str | None] = mapped_column(String(512), nullable=True)
    mcp_server_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mcp_tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Tool id={self.id} name={self.name!r} type={self.type.value}>"
