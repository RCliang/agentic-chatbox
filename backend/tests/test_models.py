"""Tests for SQLAlchemy ORM models using aiosqlite in-memory SQLite."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.models.base import Base
from app.models.conversation import Conversation, ConversationMode
from app.models.department import Department
from app.models.message import Message, MessageRole
from app.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def engine():
    """Create an in-memory aiosqlite engine with SQLite compatibility."""
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    @event.listens_for(eng.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    return eng


@pytest.fixture
async def session(engine):
    """Create tables, yield a session, then drop tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with async_session() as sess:
        yield sess

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_create_department(session: AsyncSession):
    """Test creating a department."""
    dept = Department(name="Engineering")
    session.add(dept)
    await session.commit()
    await session.refresh(dept)

    assert dept.id is not None
    assert isinstance(dept.id, uuid.UUID)
    assert dept.name == "Engineering"
    assert dept.created_at is not None
    assert isinstance(dept.created_at, datetime)


async def test_create_user_with_department(session: AsyncSession):
    """Test creating a user associated with a department."""
    dept = Department(name="Engineering")
    session.add(dept)
    await session.flush()

    user = User(
        username="alice",
        password_hash="hashed_password_here",
        display_name="Alice Smith",
        department_id=dept.id,
        position="Software Engineer",
        is_dept_admin=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    assert user.id is not None
    assert isinstance(user.id, uuid.UUID)
    assert user.username == "alice"
    assert user.display_name == "Alice Smith"
    assert user.department_id == dept.id
    assert user.position == "Software Engineer"
    assert user.is_dept_admin is False

    # Verify relationship using explicit query with selectinload
    result = await session.execute(
        select(Department)
        .options(selectinload(Department.users))
        .where(Department.id == dept.id)
    )
    dept_loaded = result.scalar_one()
    assert len(dept_loaded.users) == 1
    assert dept_loaded.users[0].username == "alice"


async def test_create_conversation_with_user(session: AsyncSession):
    """Test creating a conversation linked to a user."""
    dept = Department(name="Engineering")
    session.add(dept)
    await session.flush()

    user = User(
        username="bob",
        password_hash="hashed_pw",
        display_name="Bob Jones",
        department_id=dept.id,
    )
    session.add(user)
    await session.flush()

    conv = Conversation(
        user_id=user.id,
        title="Test Conversation",
        mode=ConversationMode.normal,
    )
    session.add(conv)
    await session.commit()
    await session.refresh(conv)

    assert conv.id is not None
    assert isinstance(conv.id, uuid.UUID)
    assert conv.user_id == user.id
    assert conv.title == "Test Conversation"
    assert conv.mode == ConversationMode.normal
    assert conv.created_at is not None

    # Verify relationship using explicit query with selectinload
    result = await session.execute(
        select(User)
        .options(selectinload(User.conversations))
        .where(User.id == user.id)
    )
    user_loaded = result.scalar_one()
    assert len(user_loaded.conversations) == 1
    assert user_loaded.conversations[0].title == "Test Conversation"


async def test_create_message_in_conversation(session: AsyncSession):
    """Test creating a message inside a conversation."""
    dept = Department(name="Engineering")
    session.add(dept)
    await session.flush()

    user = User(
        username="charlie",
        password_hash="hashed_pw",
        display_name="Charlie Brown",
        department_id=dept.id,
    )
    session.add(user)
    await session.flush()

    conv = Conversation(
        user_id=user.id,
        title="Agentic Chat",
        mode=ConversationMode.agentic,
    )
    session.add(conv)
    await session.flush()

    # User message
    user_msg = Message(
        conversation_id=conv.id,
        role=MessageRole.user,
        content="Hello, how are you?",
    )
    session.add(user_msg)

    # Assistant message with tool calls
    assistant_msg = Message(
        conversation_id=conv.id,
        role=MessageRole.assistant,
        content=None,
        tool_calls=[{"name": "search", "arguments": {"query": "weather"}}],
        agent_steps=[
            {"step": "thinking", "content": "I need to search for the weather."},
            {"step": "tool_use", "content": "Calling search tool."},
        ],
    )
    session.add(assistant_msg)

    # Tool message
    tool_msg = Message(
        conversation_id=conv.id,
        role=MessageRole.tool,
        content='{"temperature": 22, "unit": "celsius"}',
        tool_call_id="call_abc123",
    )
    session.add(tool_msg)

    await session.commit()

    # Verify all three messages exist using explicit query with selectinload
    result = await session.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conv.id)
    )
    conv_loaded = result.scalar_one()
    assert len(conv_loaded.messages) == 3

    user_msg_db = conv_loaded.messages[0]
    assert user_msg_db.role == MessageRole.user
    assert user_msg_db.content == "Hello, how are you?"
    assert user_msg_db.tool_calls is None
    assert user_msg_db.tool_call_id is None

    assistant_msg_db = conv_loaded.messages[1]
    assert assistant_msg_db.role == MessageRole.assistant
    assert assistant_msg_db.content is None
    assert assistant_msg_db.tool_calls == [{"name": "search", "arguments": {"query": "weather"}}]
    assert assistant_msg_db.agent_steps is not None
    assert len(assistant_msg_db.agent_steps) == 2

    tool_msg_db = conv_loaded.messages[2]
    assert tool_msg_db.role == MessageRole.tool
    assert tool_msg_db.tool_call_id == "call_abc123"
    assert "temperature" in tool_msg_db.content
