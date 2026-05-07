"""LangGraph PostgreSQL checkpointer setup."""

from __future__ import annotations

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.config import settings

_checkpointer: AsyncPostgresSaver | None = None


async def get_checkpointer() -> AsyncPostgresSaver:
    """Get or create the async PostgreSQL checkpointer singleton.

    Uses the sync database URL (standard psycopg format) since
    langgraph-checkpoint-postgres uses psycopg3 directly, not SQLAlchemy.
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = AsyncPostgresSaver.from_conn_string(
            settings.database_url_sync
        )
        await _checkpointer.setup()
    return _checkpointer
