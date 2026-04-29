# Backend Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI backend foundation with database models, JWT auth, Normal chat mode with SSE streaming, and Docker infrastructure.

**Architecture:** Monolithic FastAPI app with layered structure (api → services → models). PostgreSQL for persistence, Redis for Celery broker, OpenAI-compatible LLM client for chat. Normal mode sends messages to LLM and streams responses via SSE.

**Tech Stack:** Python 3.11+, FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic, Pydantic v2, python-jose (JWT), passlib, httpx (LLM client), Celery, Redis, PostgreSQL, Docker Compose.

**Spec reference:** `docs/superpowers/specs/2026-04-29-agentic-chatbox-design.md`

**Sub-projects:** This is Plan 1 of 3. Plan 2 covers Intelligence Layer (RAG, Tools, Agent, Skills). Plan 3 covers Frontend.

---

## File Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py           # Settings (env vars)
│   │   ├── database.py         # SQLAlchemy engine + session
│   │   ├── security.py         # JWT + password hashing
│   │   └── deps.py             # Dependency injection (get_db, get_current_user)
│   ├── models/
│   │   ├── __init__.py         # Re-exports all models
│   │   ├── base.py             # Base mixin (id, timestamps)
│   │   ├── department.py       # Department model
│   │   ├── user.py             # User model
│   │   ├── conversation.py     # Conversation model
│   │   ├── message.py          # Message model
│   │   ├── skill.py            # Skill model
│   │   ├── tool.py             # Tool model
│   │   ├── knowledge_base.py   # KnowledgeBase model
│   │   └── knowledge_document.py # KnowledgeDocument model
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py             # Login request/response
│   │   ├── conversation.py     # Conversation CRUD schemas
│   │   ├── message.py          # Message schemas
│   │   ├── skill.py            # Skill schemas
│   │   ├── tool.py             # Tool schemas
│   │   └── knowledge.py        # Knowledge base/document schemas
│   ├── api/
│   │   ├── __init__.py
│   │   └── router.py           # Main router aggregating sub-routers
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm.py              # OpenAI-compatible LLM client
│   │   └── chat.py             # NormalHandler + SSE streaming
│   └── tasks/
│       └── __init__.py
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── tests/
│   ├── conftest.py             # Fixtures (db session, client, test user)
│   ├── test_auth.py
│   ├── test_conversations.py
│   ├── test_chat.py
│   └── test_models.py
├── pyproject.toml
├── Dockerfile
└── .env.example
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/__init__.py`
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/tasks/__init__.py`
- Create: `backend/.env.example`
- Create: `backend/Dockerfile`
- Create: `docker-compose.yml`
- Create: `.gitignore`

- [ ] **Step 1: Create backend/pyproject.toml**

```toml
[project]
name = "agentic-chatbox-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.0",
    "httpx>=0.27.0",
    "celery[redis]>=5.4.0",
    "redis>=5.0.0",
    "python-multipart>=0.0.9",
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create backend/.env.example**

```env
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/chatbox
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5432/chatbox

# Redis
REDIS_URL=redis://localhost:6379/0

# JWT
JWT_SECRET_KEY=change-me-to-a-random-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# LLM
LLM_BASE_URL=http://localhost:8000/v1
LLM_API_KEY=sk-placeholder
LLM_DEFAULT_MODEL=gpt-4

# Milvus
MILVUS_URI=http://localhost:19530
```

- [ ] **Step 3: Create backend/app/core/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/chatbox"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/chatbox"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    llm_base_url: str = "http://localhost:8000/v1"
    llm_api_key: str = "sk-placeholder"
    llm_default_model: str = "gpt-4"
    milvus_uri: str = "http://localhost:19530"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
```

- [ ] **Step 4: Create backend/app/core/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

- [ ] **Step 5: Create backend/app/main.py**

```python
from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title="Agentic Chatbox", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: Create docker-compose.yml**

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: chatbox
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    env_file:
      - ./backend/.env
    depends_on:
      - postgres
      - redis
    volumes:
      - ./backend:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  pgdata:
```

- [ ] **Step 7: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir -e .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 8: Create .gitignore**

```
__pycache__/
*.pyc
.env
.venv/
node_modules/
dist/
build/
.superpowers/
*.egg-info/
```

- [ ] **Step 9: Create all __init__.py files (empty)**

Create empty `__init__.py` in:
- `backend/app/`
- `backend/app/core/`
- `backend/app/models/`
- `backend/app/schemas/`
- `backend/app/api/`
- `backend/app/services/`
- `backend/app/tasks/`

- [ ] **Step 10: Verify FastAPI starts**

Run: `cd backend && pip install -e ".[dev]" 2>/dev/null || pip install -e . && uvicorn app.main:app --host 0.0.0.0 --port 8000`
Then: `curl http://localhost:8000/health`
Expected: `{"status":"ok"}`

- [ ] **Step 11: Commit**

```bash
git add backend/ docker-compose.yml .gitignore
git commit -m "feat: project scaffolding with FastAPI, Docker Compose, and config"
```

---

### Task 2: Database Models

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/department.py`
- Create: `backend/app/models/user.py`
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/models/message.py`
- Create: `backend/app/models/skill.py`
- Create: `backend/app/models/tool.py`
- Create: `backend/app/models/knowledge_base.py`
- Create: `backend/app/models/knowledge_document.py`
- Create: `backend/app/models/__init__.py` (update with re-exports)
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: Create backend/app/models/base.py**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
```

- [ ] **Step 2: Create backend/app/models/department.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Department(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "departments"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )

    users = relationship("User", back_populates="department")
    children = relationship("Department", back_populates="parent", remote_side="Department.id")
    parent = relationship("Department", back_populates="children", remote_side="Department.id")
```

- [ ] **Step 3: Create backend/app/models/user.py**

```python
import uuid

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    position: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_dept_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    department = relationship("Department", back_populates="users")
    conversations = relationship("Conversation", back_populates="user")
```

- [ ] **Step 4: Create backend/app/models/conversation.py**

```python
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ConversationMode(str, Enum):
    NORMAL = "normal"
    AGENTIC = "agentic"


class Conversation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    mode: Mapped[ConversationMode] = mapped_column(
        Enum(ConversationMode), default=ConversationMode.NORMAL, nullable=False
    )
    skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("skills.id"), nullable=True
    )
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=True
    )
    enabled_tools: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[func.now] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    skill = relationship("Skill", foreign_keys=[skill_id])
    knowledge_base = relationship("KnowledgeBase", foreign_keys=[knowledge_base_id])
```

- [ ] **Step 5: Create backend/app/models/message.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class Message(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(Enum(MessageRole), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_steps: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation = relationship("Conversation", back_populates="messages")
```

- [ ] **Step 6: Create backend/app/models/skill.py**

```python
import uuid

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Skill(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "skills"

    name: Mapped[str] = mapped_column(nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    tool_ids: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    knowledge_base_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=True
    )
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)

    conversations = relationship("Conversation", back_populates="skill", foreign_keys="Conversation.skill_id")
    knowledge_base = relationship("KnowledgeBase", foreign_keys=[knowledge_base_id])
```

- [ ] **Step 7: Create backend/app/models/tool.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ToolType(str, Enum):
    BUILTIN = "builtin"
    MCP = "mcp"


class Tool(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tools"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    parameters_schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    type: Mapped[ToolType] = mapped_column(
        Enum(ToolType), default=ToolType.BUILTIN, nullable=False
    )
    handler: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mcp_server_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mcp_tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
```

- [ ] **Step 8: Create backend/app/models/knowledge_base.py**

```python
import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class KnowledgeBaseScope(str, Enum):
    PERSONAL = "personal"
    DEPARTMENT = "department"


class KnowledgeBase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "knowledge_bases"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[KnowledgeBaseScope] = mapped_column(
        Enum(KnowledgeBaseScope), default=KnowledgeBaseScope.PERSONAL, nullable=False
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    department_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True
    )
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False, default="text-embedding-ada-002")
    chunk_size: Mapped[int] = mapped_column(Integer, default=512)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    milvus_collection: Mapped[str | None] = mapped_column(String(255), nullable=True)

    documents = relationship("KnowledgeDocument", back_populates="knowledge_base")
    conversations = relationship("Conversation", back_populates="knowledge_base", foreign_keys="Conversation.knowledge_base_id")
```

- [ ] **Step 9: Create backend/app/models/knowledge_document.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin


class DocumentSource(str, Enum):
    UPLOAD = "upload"
    FEISHU = "feishu"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class KnowledgeDocument(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "knowledge_documents"

    knowledge_base_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_bases.id"), nullable=False
    )
    source_type: Mapped[DocumentSource] = mapped_column(Enum(DocumentSource), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    file_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    feishu_doc_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus), default=DocumentStatus.PENDING, nullable=False
    )
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
```

- [ ] **Step 10: Update backend/app/models/__init__.py with re-exports**

```python
from app.models.base import Base
from app.models.department import Department
from app.models.user import User
from app.models.conversation import Conversation, ConversationMode
from app.models.message import Message, MessageRole
from app.models.skill import Skill
from app.models.tool import Tool, ToolType
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseScope
from app.models.knowledge_document import KnowledgeDocument, DocumentSource, DocumentStatus

__all__ = [
    "Base",
    "Department",
    "User",
    "Conversation",
    "ConversationMode",
    "Message",
    "MessageRole",
    "Skill",
    "Tool",
    "ToolType",
    "KnowledgeBase",
    "KnowledgeBaseScope",
    "KnowledgeDocument",
    "DocumentSource",
    "DocumentStatus",
]
```

- [ ] **Step 11: Write test for models**

Create `backend/tests/test_models.py`:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.models import Base, User, Department, Conversation, ConversationMode, Message, MessageRole


@pytest.fixture
def engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    return engine


@pytest.fixture
async def session(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def test_create_department(session):
    dept = Department(name="Engineering")
    session.add(dept)
    await session.commit()
    result = await session.get(Department, dept.id)
    assert result is not None
    assert result.name == "Engineering"


async def test_create_user(session):
    dept = Department(name="Engineering")
    session.add(dept)
    await session.flush()
    user = User(username="testuser", password_hash="hashed", display_name="Test", department_id=dept.id)
    session.add(user)
    await session.commit()
    result = await session.get(User, user.id)
    assert result.username == "testuser"
    assert result.department_id == dept.id


async def test_create_conversation(session):
    dept = Department(name="Engineering")
    session.add(dept)
    await session.flush()
    user = User(username="testuser", password_hash="hashed", display_name="Test", department_id=dept.id)
    session.add(user)
    await session.flush()
    conv = Conversation(user_id=user.id, title="Test Chat", mode=ConversationMode.NORMAL)
    session.add(conv)
    await session.commit()
    result = await session.get(Conversation, conv.id)
    assert result.title == "Test Chat"
    assert result.mode == ConversationMode.NORMAL


async def test_create_message(session):
    dept = Department(name="Engineering")
    session.add(dept)
    await session.flush()
    user = User(username="testuser", password_hash="hashed", display_name="Test", department_id=dept.id)
    session.add(user)
    await session.flush()
    conv = Conversation(user_id=user.id, title="Test Chat", mode=ConversationMode.NORMAL)
    session.add(conv)
    await session.flush()
    msg = Message(conversation_id=conv.id, role=MessageRole.USER, content="Hello")
    session.add(msg)
    await session.commit()
    result = await session.get(Message, msg.id)
    assert result.content == "Hello"
    assert result.role == MessageRole.USER
```

- [ ] **Step 12: Run tests**

Run: `cd backend && pip install aiosqlite && pytest tests/test_models.py -v`
Expected: All 4 tests PASS

- [ ] **Step 13: Commit**

```bash
git add backend/app/models/ backend/tests/test_models.py
git commit -m "feat: add all database models with SQLAlchemy ORM"
```

---

### Task 3: Alembic Setup + Initial Migration

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`

- [ ] **Step 1: Initialize Alembic**

Run: `cd backend && alembic init alembic`

- [ ] **Step 2: Update backend/alembic/env.py to use async and import models**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url_sync
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations():
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Update backend/alembic.ini sqlalchemy.url**

Set to a placeholder since env.py reads from settings:
```
sqlalchemy.url = postgresql://postgres:postgres@localhost:5432/chatbox
```

- [ ] **Step 4: Generate initial migration**

Run: `cd backend && docker compose up -d postgres redis && sleep 5 && alembic revision --autogenerate -m "initial"`
Expected: New file in `alembic/versions/`

- [ ] **Step 5: Apply migration**

Run: `cd backend && alembic upgrade head`
Expected: Tables created in PostgreSQL

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/ backend/alembic.ini
git commit -m "feat: setup Alembic migrations with async support"
```

---

### Task 4: Auth System (JWT)

**Files:**
- Create: `backend/app/core/security.py`
- Create: `backend/app/core/deps.py`
- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_auth.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Create backend/app/core/security.py**

```python
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None
```

- [ ] **Step 2: Create backend/app/core/deps.py**

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models import User

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 3: Create backend/app/schemas/auth.py**

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None
    department_id: str | None
    position: str | None
    is_dept_admin: bool

    class Config:
        from_attributes = True
```

- [ ] **Step 4: Create backend/app/api/auth.py**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(str(user.id))
    return LoginResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 5: Create backend/app/api/router.py**

```python
from fastapi import APIRouter

from app.api.auth import router as auth_router

router = APIRouter()
router.include_router(auth_router)
```

- [ ] **Step 6: Update backend/app/main.py to include router**

```python
from fastapi import FastAPI

from app.api.router import router
from app.core.config import settings
from app.models import Base

app = FastAPI(title="Agentic Chatbox", version="0.1.0")
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 7: Create backend/tests/conftest.py**

```python
import asyncio
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.database import async_session, engine, Base, get_db
from app.core.security import hash_password
from app.main import app
from app.models import Department, User


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with async_session() as session:
        yield session


@pytest.fixture
async def client():
    async def override_get_db():
        async with async_session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(db_session):
    dept = Department(name="Engineering")
    db_session.add(dept)
    await db_session.flush()
    user = User(
        username="testuser",
        password_hash=hash_password("password123"),
        display_name="Test User",
        department_id=dept.id,
        position="Engineer",
        is_dept_admin=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_header(test_user):
    from app.core.security import create_access_token
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}
```

- [ ] **Step 8: Create backend/tests/test_auth.py**

```python
import pytest
from httpx import AsyncClient


async def test_login_success(client: AsyncClient, test_user):
    response = await client.post("/api/auth/login", json={"username": "testuser", "password": "password123"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, test_user):
    response = await client.post("/api/auth/login", json={"username": "testuser", "password": "wrong"})
    assert response.status_code == 401


async def test_login_nonexistent_user(client: AsyncClient):
    response = await client.post("/api/auth/login", json={"username": "nobody", "password": "password"})
    assert response.status_code == 401


async def test_get_me(client: AsyncClient, auth_header):
    response = await client.get("/api/auth/me", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "testuser"
    assert data["display_name"] == "Test User"


async def test_get_me_unauthorized(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 403
```

- [ ] **Step 9: Run tests**

Run: `cd backend && pytest tests/test_auth.py -v`
Expected: All 5 tests PASS

- [ ] **Step 10: Commit**

```bash
git add backend/app/core/security.py backend/app/core/deps.py backend/app/schemas/auth.py backend/app/api/auth.py backend/app/api/router.py backend/app/main.py backend/tests/conftest.py backend/tests/test_auth.py
git commit -m "feat: add JWT auth system with login and current user endpoint"
```

---

### Task 5: Conversation CRUD API

**Files:**
- Create: `backend/app/schemas/conversation.py`
- Create: `backend/app/api/conversations.py`
- Create: `backend/tests/test_conversations.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Create backend/app/schemas/conversation.py**

```python
from datetime import datetime

from pydantic import BaseModel


class ConversationCreate(BaseModel):
    title: str = "New Chat"
    mode: str = "normal"
    skill_id: str | None = None
    knowledge_base_id: str | None = None
    tool_ids: list[str] | None = None


class ConversationResponse(BaseModel):
    id: str
    title: str
    mode: str
    skill_id: str | None
    knowledge_base_id: str | None
    enabled_tools: list | None
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class ConversationListResponse(BaseModel):
    id: str
    title: str
    mode: str
    created_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Create backend/app/api/conversations.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Conversation, Message, User
from app.schemas.conversation import ConversationCreate, ConversationResponse, ConversationListResponse

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("/", response_model=list[ConversationListResponse])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = Conversation(
        user_id=user.id,
        title=body.title,
        mode=body.mode,
        skill_id=body.skill_id,
        knowledge_base_id=body.knowledge_base_id,
        enabled_tools=body.tool_ids,
    )
    db.add(conv)
    await db.commit()
    await db.refresh(conv)
    return conv


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_user_conversation(conversation_id, user, db)
    return conv


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = await _get_user_conversation(conversation_id, user, db)
    # Delete messages first (FK constraint)
    stmt = select(Message).where(Message.conversation_id == conv.id)
    result = await db.execute(stmt)
    for msg in result.scalars().all():
        await db.delete(msg)
    await db.delete(conv)
    await db.commit()


async def _get_user_conversation(conversation_id: str, user: User, db: AsyncSession) -> Conversation:
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == user.id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv
```

- [ ] **Step 3: Update backend/app/api/router.py**

```python
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(conversations_router)
```

- [ ] **Step 4: Create backend/tests/test_conversations.py**

```python
import pytest
from httpx import AsyncClient


async def test_create_conversation(client: AsyncClient, auth_header):
    response = await client.post(
        "/api/conversations/",
        json={"title": "Test Chat", "mode": "normal"},
        headers=auth_header,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Chat"
    assert data["mode"] == "normal"


async def test_list_conversations(client: AsyncClient, auth_header):
    # Create two conversations
    await client.post("/api/conversations/", json={"title": "Chat 1", "mode": "normal"}, headers=auth_header)
    await client.post("/api/conversations/", json={"title": "Chat 2", "mode": "agentic"}, headers=auth_header)
    response = await client.get("/api/conversations/", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


async def test_get_conversation(client: AsyncClient, auth_header):
    create_resp = await client.post("/api/conversations/", json={"title": "My Chat", "mode": "normal"}, headers=auth_header)
    conv_id = create_resp.json()["id"]
    response = await client.get(f"/api/conversations/{conv_id}", headers=auth_header)
    assert response.status_code == 200
    assert response.json()["title"] == "My Chat"


async def test_get_conversation_not_found(client: AsyncClient, auth_header):
    response = await client.get("/api/conversations/00000000-0000-0000-0000-000000000000", headers=auth_header)
    assert response.status_code == 404


async def test_delete_conversation(client: AsyncClient, auth_header):
    create_resp = await client.post("/api/conversations/", json={"title": "To Delete", "mode": "normal"}, headers=auth_header)
    conv_id = create_resp.json()["id"]
    response = await client.delete(f"/api/conversations/{conv_id}", headers=auth_header)
    assert response.status_code == 204
    # Verify deleted
    get_resp = await client.get(f"/api/conversations/{conv_id}", headers=auth_header)
    assert get_resp.status_code == 404
```

- [ ] **Step 5: Run tests**

Run: `cd backend && pytest tests/test_conversations.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/conversation.py backend/app/api/conversations.py backend/app/api/router.py backend/tests/test_conversations.py
git commit -m "feat: add conversation CRUD API with auth and ownership checks"
```

---

### Task 6: LLM Client

**Files:**
- Create: `backend/app/services/llm.py`
- Create: `backend/tests/test_llm.py`

- [ ] **Step 1: Create backend/app/services/llm.py**

```python
from typing import AsyncIterator

import httpx

from app.core.config import settings


class LLMClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        default_model: str | None = None,
    ):
        self.base_url = (base_url or settings.llm_base_url).rstrip("/")
        self.api_key = api_key or settings.llm_api_key
        self.default_model = default_model or settings.llm_default_model

    async def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> dict:
        """Non-streaming chat completion."""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            resp.raise_for_status()
            return resp.json()

    async def chat_stream(
        self,
        messages: list[dict],
        model: str | None = None,
        tools: list[dict] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[dict]:
        """Streaming chat completion. Yields parsed SSE chunks."""
        payload = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    import json
                    yield json.loads(data)


llm_client = LLMClient()
```

- [ ] **Step 2: Create backend/tests/test_llm.py**

```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.services.llm import LLMClient


@pytest.fixture
def llm_client():
    return LLMClient(base_url="http://fake:8000/v1", api_key="test-key", default_model="test-model")


async def test_chat_non_streaming(llm_client):
    mock_response = {
        "choices": [{"message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}]
    }
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_resp = httpx.Response(200, json=mock_response, request=httpx.Request("POST", "http://fake"))
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await llm_client.chat([{"role": "user", "content": "Hi"}])
        assert result["choices"][0]["message"]["content"] == "Hello!"


async def test_chat_streaming(llm_client):
    chunks = [
        'data: {"choices":[{"delta":{"content":"He"},"finish_reason":null}]}\n',
        'data: {"choices":[{"delta":{"content":"llo"},"finish_reason":null}]}\n',
        "data: [DONE]\n",
    ]
    with patch("httpx.AsyncClient") as mock_client_cls:
        # Simulate streaming response
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = AsyncMock()
        mock_resp.aiter_lines = AsyncMock(return_value=iter(chunks))
        mock_client = AsyncMock()
        mock_client.stream.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_client.stream.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        texts = []
        async for chunk in llm_client.chat_stream([{"role": "user", "content": "Hi"}]):
            content = chunk["choices"][0].get("delta", {}).get("content", "")
            if content:
                texts.append(content)
        assert texts == ["He", "llo"]
```

- [ ] **Step 3: Run tests**

Run: `cd backend && pytest tests/test_llm.py -v`
Expected: All 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/llm.py backend/tests/test_llm.py
git commit -m "feat: add OpenAI-compatible LLM client with streaming support"
```

---

### Task 7: Normal Chat + SSE Streaming

**Files:**
- Create: `backend/app/schemas/message.py`
- Create: `backend/app/services/chat.py`
- Create: `backend/app/api/chat.py`
- Create: `backend/tests/test_chat.py`
- Modify: `backend/app/api/router.py`

- [ ] **Step 1: Create backend/app/schemas/message.py**

```python
from datetime import datetime
from pydantic import BaseModel


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str | None
    tool_calls: dict | None
    tool_call_id: str | None
    agent_steps: dict | None
    created_at: datetime

    class Config:
        from_attributes = True


class ChatSendRequest(BaseModel):
    conversation_id: str
    content: str
    attachments: list[str] | None = None
```

- [ ] **Step 2: Create backend/app/services/chat.py**

```python
import json
import uuid
from typing import AsyncIterator

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Conversation, Message, MessageRole
from app.services.llm import LLMClient, llm_client


DEFAULT_SYSTEM_PROMPT = "You are a helpful AI assistant."


async def get_conversation_messages(
    db: AsyncSession, conversation_id: str, limit: int = 50
) -> list[Message]:
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def build_messages_for_llm(
    history: list[Message], system_prompt: str, user_content: str
) -> list[dict]:
    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        if msg.role == MessageRole.USER:
            messages.append({"role": "user", "content": msg.content or ""})
        elif msg.role == MessageRole.ASSISTANT:
            messages.append({"role": "assistant", "content": msg.content or ""})
    messages.append({"role": "user", "content": user_content})
    return messages


async def normal_chat_stream(
    conversation: Conversation,
    user_content: str,
    db: AsyncSession,
    llm: LLMClient | None = None,
) -> AsyncIterator[dict]:
    """Stream Normal mode chat response. Yields SSE events."""
    client = llm or llm_client

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=user_content,
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # Build message history
    history = await get_conversation_messages(db, conversation.id, limit=50)
    system_prompt = DEFAULT_SYSTEM_PROMPT
    llm_messages = build_messages_for_llm(history[:-1], system_prompt, user_content)

    # Stream from LLM
    full_content = ""
    async for chunk in client.chat_stream(llm_messages):
        choices = chunk.get("choices", [])
        if not choices:
            continue
        delta = choices[0].get("delta", {})
        content = delta.get("content", "")
        if content:
            full_content += content
            yield {"event": "text", "data": json.dumps({"content": content})}

    # Save assistant message
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=full_content,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    yield {
        "event": "done",
        "data": json.dumps({"message_id": str(assistant_msg.id)}),
    }
```

- [ ] **Step 3: Create backend/app/api/chat.py**

```python
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Conversation, User
from app.schemas.message import ChatSendRequest
from app.services.chat import normal_chat_stream

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/send")
async def send_message(
    body: ChatSendRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Get conversation
    stmt = select(Conversation).where(
        Conversation.id == body.conversation_id,
        Conversation.user_id == user.id,
    )
    result = await db.execute(stmt)
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    if conversation.mode == "agentic":
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Agentic mode not yet implemented")

    async def event_generator():
        async for event in normal_chat_stream(conversation, body.content, db):
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import Message
    from app.schemas.message import MessageResponse

    stmt = select(Conversation).where(
        Conversation.id == conversation_id,
        Conversation.user_id == user.id,
    )
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]
```

- [ ] **Step 4: Update backend/app/api/router.py**

```python
from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.conversations import router as conversations_router
from app.api.chat import router as chat_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(conversations_router)
router.include_router(chat_router)
```

- [ ] **Step 5: Create backend/tests/test_chat.py**

```python
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.models import Conversation, ConversationMode, Message, MessageRole


async def test_send_message_returns_sse(client: AsyncClient, auth_header, test_user, db_session):
    # Create conversation
    conv = Conversation(user_id=test_user.id, title="SSE Test", mode=ConversationMode.NORMAL)
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Mock LLM streaming
    mock_chunks = [
        {"choices": [{"delta": {"content": "Hi"}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": " there"}, "finish_reason": None}]},
        {"choices": [{"delta": {}, "finish_reason": "stop"}]},
    ]

    async def mock_stream(*args, **kwargs):
        for chunk in mock_chunks:
            yield chunk

    with patch("app.services.chat.llm_client") as mock_llm:
        mock_llm.chat_stream = mock_stream

        response = await client.post(
            "/api/chat/send",
            json={"conversation_id": str(conv.id), "content": "Hello"},
            headers=auth_header,
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

        body = response.text
        assert "event: text" in body
        assert "event: done" in body
        assert '"content":"Hi"' in body
        assert '"content":" there"' in body


async def test_send_message_not_found(client: AsyncClient, auth_header):
    response = await client.post(
        "/api/chat/send",
        json={"conversation_id": "00000000-0000-0000-0000-000000000000", "content": "Hello"},
        headers=auth_header,
    )
    assert response.status_code == 404


async def test_get_messages(client: AsyncClient, auth_header, test_user, db_session):
    conv = Conversation(user_id=test_user.id, title="Msg Test", mode=ConversationMode.NORMAL)
    db_session.add(conv)
    await db_session.flush()
    msg1 = Message(conversation_id=conv.id, role=MessageRole.USER, content="Hello")
    msg2 = Message(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="Hi there!")
    db_session.add(msg1)
    db_session.add(msg2)
    await db_session.commit()

    response = await client.get(f"/api/chat/conversations/{conv.id}/messages", headers=auth_header)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["role"] == "user"
    assert data[1]["role"] == "assistant"
```

- [ ] **Step 6: Run all tests**

Run: `cd backend && pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/message.py backend/app/services/chat.py backend/app/api/chat.py backend/app/api/router.py backend/tests/test_chat.py
git commit -m "feat: add Normal mode chat with SSE streaming"
```

---

### Task 8: Integration Smoke Test

**Files:**
- Create: `backend/tests/test_integration.py`

- [ ] **Step 1: Create backend/tests/test_integration.py**

```python
"""Full flow: login → create conversation → send message → get messages."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

from app.models import Conversation, ConversationMode


async def test_full_normal_chat_flow(client: AsyncClient, test_user, db_session):
    # 1. Login
    login_resp = await client.post("/api/auth/login", json={"username": "testuser", "password": "password123"})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get current user
    me_resp = await client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "testuser"

    # 3. Create conversation
    conv_resp = await client.post("/api/conversations/", json={"title": "Integration Test", "mode": "normal"}, headers=headers)
    assert conv_resp.status_code == 201
    conv_id = conv_resp.json()["id"]

    # 4. List conversations
    list_resp = await client.get("/api/conversations/", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # 5. Send message (mock LLM)
    async def mock_stream(*args, **kwargs):
        yield {"choices": [{"delta": {"content": "Integration OK"}, "finish_reason": None}]}
        yield {"choices": [{"delta": {}, "finish_reason": "stop"}]}

    with patch("app.services.chat.llm_client") as mock_llm:
        mock_llm.chat_stream = mock_stream
        send_resp = await client.post(
            "/api/chat/send",
            json={"conversation_id": conv_id, "content": "Test message"},
            headers=headers,
        )
        assert send_resp.status_code == 200
        assert "Integration OK" in send_resp.text

    # 6. Get messages
    msg_resp = await client.get(f"/api/chat/conversations/{conv_id}/messages", headers=headers)
    assert msg_resp.status_code == 200
    messages = msg_resp.json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # 7. Delete conversation
    del_resp = await client.delete(f"/api/conversations/{conv_id}", headers=headers)
    assert del_resp.status_code == 204

    # 8. Verify deleted
    get_resp = await client.get(f"/api/conversations/{conv_id}", headers=headers)
    assert get_resp.status_code == 404
```

- [ ] **Step 2: Run integration test**

Run: `cd backend && pytest tests/test_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_integration.py
git commit -m "test: add integration smoke test for full Normal chat flow"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] DB models (all 9 tables) → Task 2
- [x] Auth (JWT login/me) → Task 4
- [x] Conversations CRUD → Task 5
- [x] Messages persistence → Task 7
- [x] Normal chat with SSE → Task 7
- [x] LLM client (OpenAI compatible) → Task 6
- [x] Docker Compose infrastructure → Task 1
- [ ] Agentic mode → Plan 2
- [ ] Knowledge base / RAG → Plan 2
- [ ] Tool system / MCP → Plan 2
- [ ] Skill system → Plan 2
- [ ] Frontend → Plan 3

**2. Placeholder scan:** No TBD, no "implement later", no "add error handling" without specifics. All code steps have actual code.

**3. Type consistency:** Model field names match across models → schemas → API → tests. `ConversationMode.NORMAL` / `MessageRole.USER` used consistently.
