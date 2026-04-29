# Intelligence Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add knowledge base RAG, tool system with MCP support, Agentic mode with ReAct loop, and Skill management.

**Architecture:** RAG pipeline uses Celery for async document processing (parse → chunk → embed → Milvus). ToolRegistry supports builtin (local handler) and MCP (remote server) tools. AgentLoop runs ReAct cycle with SSE event streaming. Skills configure agent behavior (prompt + tools + KB).

**Tech Stack:** celery, redis, pymilvus, httpx (MCP client), openai-compatible embedding API.

**Spec reference:** `docs/superpowers/specs/2026-04-29-agentic-chatbox-design.md`

**Prerequisite:** Plan 1 (Backend Foundation) completed on `feat/backend-foundation`.

---

### Task 1: Knowledge Base CRUD API

**Files:**
- Create: `backend/app/schemas/knowledge.py`
- Create: `backend/app/api/knowledge.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_knowledge.py`

- [ ] **Step 1: Create backend/app/schemas/knowledge.py**

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict
import uuid


class KnowledgeBaseCreate(BaseModel):
    name: str
    description: str | None = None
    scope: str = "personal"
    department_id: str | None = None
    embedding_model: str = "text-embedding-ada-002"
    chunk_size: int = 512
    chunk_overlap: int = 50


class KnowledgeBaseResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    scope: str
    owner_id: uuid.UUID
    department_id: uuid.UUID | None
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    milvus_collection: str | None
    document_count: int = 0
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: uuid.UUID
    knowledge_base_id: uuid.UUID
    source_type: str
    title: str
    file_path: str | None
    feishu_doc_id: str | None
    uploaded_by: uuid.UUID
    status: str
    chunk_count: int
    indexed_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: str
```

- [ ] **Step 2: Create backend/app/api/knowledge.py**

Router prefix `/api/knowledge`, all endpoints require auth.

Permission logic:
- `GET /bases` — return user's personal KBs + department KBs (user.department_id match)
- `POST /bases` — personal: anyone can create; department: only is_dept_admin
- `DELETE /bases/{id}` — personal: only owner; department: only is_dept_admin
- `POST /bases/{id}/documents` — personal: only owner; department: only is_dept_admin; accept multipart file upload, save to `uploads/` dir, create KnowledgeDocument record with status=pending
- `GET /bases/{id}/documents` — list documents for a KB (with permission check)
- `DELETE /bases/{id}/documents/{doc_id}` — personal: only owner; department: only is_dept_admin

Implementation:
```python
@router.post("/bases/{kb_id}/documents")
async def upload_document(kb_id: str, file: UploadFile, user=Depends(get_current_user), db=Depends(get_db)):
    # 1. Check KB exists and user has permission
    # 2. Save file to backend/uploads/{kb_id}/{filename}
    # 3. Create KnowledgeDocument record (status=pending)
    # 4. Dispatch Celery task: process_document.delay(doc_id=str(doc.id))
    # 5. Return DocumentUploadResponse
```

- [ ] **Step 3: Update backend/app/api/router.py**

Add `knowledge_router`.

- [ ] **Step 4: Create backend/tests/test_knowledge.py**

Tests (use aiosqlite, mock file uploads):
- test_create_personal_knowledge_base
- test_list_knowledge_bases (returns personal + department)
- test_delete_personal_knowledge_base (owner only)
- test_upload_document (mock UploadFile, check record created)
- test_list_documents

- [ ] **Step 5: Run tests**

Run: `eval "$(conda shell.bash hook)" && conda activate dev && cd backend && pytest tests/test_knowledge.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/knowledge.py backend/app/api/knowledge.py backend/app/api/router.py backend/tests/test_knowledge.py
git commit -m "feat: add knowledge base CRUD API with permission checks"
```

---

### Task 2: Document Processing Pipeline (Celery + Embedding + Milvus)

**Files:**
- Create: `backend/app/services/knowledge.py`
- Create: `backend/app/tasks/document_tasks.py`
- Create: `backend/app/core/celery_app.py`
- Modify: `backend/pyproject.toml` (add pymilvus)
- Create: `backend/tests/test_knowledge_service.py`

- [ ] **Step 1: Install pymilvus**

Run: `eval "$(conda shell.bash hook)" && conda activate dev && pip install pymilvus`

- [ ] **Step 2: Create backend/app/core/celery_app.py**

```python
from celery import Celery
from app.core.config import settings

celery_app = Celery("chatbox", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="UTC")
```

- [ ] **Step 3: Create backend/app/services/knowledge.py**

Core RAG service:

```python
import os
import uuid
from typing import AsyncIterator
import httpx
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models import KnowledgeBase, KnowledgeDocument


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
        if start >= len(text):
            break
    return chunks


async def get_embedding(text: str) -> list[float]:
    """Get embedding vector from OpenAI-compatible API."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.llm_base_url}/embeddings",
            json={"model": settings.llm_default_model, "input": text},
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
        )
        resp.raise_for_status()
        return resp.json()["data"][0]["embedding"]


async def retrieve(kb_ids: list[str], query: str, top_k: int = 5) -> list[dict]:
    """Retrieve relevant chunks from knowledge bases using Milvus."""
    from pymilvus import connections, Collection

    connections.connect(uri=settings.milvus_uri, timeout=5)
    all_results = []
    query_vector = await get_embedding(query)

    for kb_id in kb_ids:
        collection_name = f"kb_{kb_id}"
        try:
            collection = Collection(collection_name)
            collection.load()
            results = collection.search(
                data=[query_vector],
                anns_field="embedding",
                param={"metric_type": "COSINE", "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["text", "doc_id", "metadata"],
            )
            for hits in results:
                for hit in hits:
                    all_results.append({
                        "text": hit.entity.get("text", ""),
                        "score": hit.score,
                        "doc_id": hit.entity.get("doc_id", ""),
                        "metadata": hit.entity.get("metadata", {}),
                    })
        except Exception:
            continue

    all_results.sort(key=lambda x: x["score"], reverse=True)
    return all_results[:top_k]


async def get_kb_context(knowledge_base_id: str | None, query: str) -> str:
    """Build RAG context string from a knowledge base."""
    if not knowledge_base_id:
        return ""
    results = await retrieve([str(knowledge_base_id)], query)
    if not results:
        return ""
    context_parts = [f"[{i+1}] {r['text']}" for i, r in enumerate(results)]
    return "Relevant context:\n" + "\n".join(context_parts)
```

- [ ] **Step 4: Create backend/app/tasks/document_tasks.py**

```python
import os
from app.core.celery_app import celery_app
from app.services.knowledge import chunk_text, get_embedding


@celery_app.task(bind=True, max_retries=1)
def process_document(self, doc_id: str):
    """Process uploaded document: parse → chunk → embed → store in Milvus."""
    from app.core.database import SessionLocal
    from app.models import KnowledgeDocument, KnowledgeBase
    from sqlalchemy import select
    import asyncio
    from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType

    db = SessionLocal()
    try:
        doc = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.id == doc_id)).scalar_one_or_none()
        if not doc:
            return

        doc.status = "indexing"
        db.commit()

        # Read file content
        file_path = doc.file_path
        if not file_path or not os.path.exists(file_path):
            doc.status = "failed"
            db.commit()
            return

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        # Get KB config
        kb = db.execute(select(KnowledgeBase).where(KnowledgeBase.id == doc.knowledge_base_id)).scalar_one_or_none()
        chunk_size = kb.chunk_size if kb else 512
        overlap = kb.chunk_overlap if kb else 50

        # Chunk text
        chunks = chunk_text(text, chunk_size, overlap)
        doc.chunk_count = len(chunks)

        # Create Milvus collection if needed
        kb_id = str(doc.knowledge_base_id)
        collection_name = f"kb_{kb_id}"
        connections.connect(uri="http://localhost:19530", timeout=5)

        if not connections.has_connection() or not Collection(collection_name).num_entities:
            # Get embedding dimension from a sample
            embedding = asyncio.run(get_embedding("sample"))
            dim = len(embedding)
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=64),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
                FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=8192),
                FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=64),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=2048),
            ]
            schema = CollectionSchema(fields=fields, description=f"KB {kb_id}")
            collection = Collection(collection_name, schema=schema)
            index_params = {"metric_type": "COSINE", "index_type": "IVF_FLAT", "params": {"nlist": 128}}
            collection.create_index(field_name="embedding", index_params=index_params)

        collection = Collection(collection_name)

        # Embed and insert chunks
        for i, chunk in enumerate(chunks):
            embedding = asyncio.run(get_embedding(chunk))
            chunk_id = f"{doc_id}_{i}"
            import json
            collection.insert([[chunk_id], [embedding], [chunk[:8192]], [str(doc_id)], [json.dumps({"chunk_index": i})]])

        collection.flush()
        doc.status = "ready"
        db.commit()
    except Exception as exc:
        doc.status = "failed"
        db.commit()
        raise self.retry(exc=exc, countdown=60)
    finally:
        db.close()
```

- [ ] **Step 5: Create backend/tests/test_knowledge_service.py**

Test chunk_text function (pure logic, no DB/Milvus needed):
```python
from app.services.knowledge import chunk_text

def test_chunk_text_basic():
    text = "A" * 1000
    chunks = chunk_text(text, chunk_size=512, overlap=50)
    assert len(chunks) > 1
    assert all(len(c) <= 512 for c in chunks)

def test_chunk_text_short():
    chunks = chunk_text("Hello world", chunk_size=512, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"

def test_chunk_text_no_overlap():
    chunks = chunk_text("A" * 1024, chunk_size=512, overlap=0)
    assert len(chunks) == 2
```

- [ ] **Step 6: Run tests**

Run: `eval "$(conda shell.bash hook)" && conda activate dev && cd backend && pytest tests/test_knowledge_service.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/knowledge.py backend/app/tasks/document_tasks.py backend/app/core/celery_app.py backend/pyproject.toml backend/tests/test_knowledge_service.py
git commit -m "feat: add RAG pipeline with document processing, embedding, and Milvus"
```

---

### Task 3: Tool System + MCP Client

**Files:**
- Create: `backend/app/services/tools.py`
- Create: `backend/app/tools/__init__.py`
- Create: `backend/app/tools/web_search.py`
- Create: `backend/app/tools/web_reader.py`
- Create: `backend/app/tools/knowledge_search.py`
- Modify: `backend/app/models/tool.py` (ensure handler field works)
- Create: `backend/tests/test_tools.py`

- [ ] **Step 1: Create backend/app/services/tools.py**

```python
import importlib
import httpx
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Tool, ToolType


class ToolRegistry:
    """Registry for managing builtin and MCP tools."""

    def __init__(self):
        self._builtin_handlers: dict[str, callable] = {}

    def register(self, name: str, handler: callable):
        self._builtin_handlers[name] = handler

    async def execute(self, tool_name: str, arguments: dict, db: AsyncSession | None = None) -> str:
        """Execute a tool by name. For builtin: call local handler. For MCP: call remote server."""
        if tool_name in self._builtin_handlers:
            result = self._builtin_handlers[tool_name](**arguments)
            if isinstance(result, str):
                return result
            return str(result)

        # Look up tool from DB for MCP tools
        if db:
            stmt = select(Tool).where(Tool.name == tool_name, Tool.is_enabled == True)
            result = await db.execute(stmt)
            tool = result.scalar_one_or_none()
            if tool and tool.type == ToolType.mcp and tool.mcp_server_url:
                return await self._call_mcp(tool, arguments)

        return f"Error: Tool '{tool_name}' not found"

    async def _call_mcp(self, tool: Tool, arguments: dict) -> str:
        """Call an MCP server tool via HTTP."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{tool.mcp_server_url}/tools/call",
                json={"name": tool.mcp_tool_name or tool.name, "arguments": arguments},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                return data.get("content", str(data))
            return str(data)

    def get_tool_schemas(self, tool_ids: list[str], db: AsyncSession | None = None) -> list[dict]:
        """Get OpenAI-compatible tool schemas for given tool IDs."""
        schemas = []
        for tid in tool_ids:
            # Check builtin first
            if tid in self._builtin_handlers:
                schemas.append({"type": "function", "function": {"name": tid, "description": f"Builtin tool: {tid}", "parameters": {"type": "object", "properties": {}}}})
                continue
        return schemas


# Global registry instance
tool_registry = ToolRegistry()


def register_builtin_tools():
    """Import and register all builtin tools."""
    import app.tools.web_search
    import app.tools.web_reader
    import app.tools.knowledge_search
```

- [ ] **Step 2: Create backend/app/tools/web_search.py**

```python
import httpx

def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for information."""
    # Placeholder — in production, connect to a search API
    return f"[web_search] Searched for: {query}. Found {max_results} results (placeholder)."
```

- [ ] **Step 3: Create backend/app/tools/web_reader.py**

```python
import httpx

def web_reader(url: str) -> str:
    """Read and extract text content from a URL."""
    # Placeholder — in production, fetch and parse HTML
    return f"[web_reader] Read content from: {url} (placeholder)."
```

- [ ] **Step 4: Create backend/app/tools/knowledge_search.py**

```python
import asyncio
from app.services.knowledge import retrieve

def knowledge_search(query: str, knowledge_base_id: str, top_k: int = 5) -> str:
    """Search knowledge base for relevant documents."""
    results = asyncio.run(retrieve([knowledge_base_id], query, top_k))
    if not results:
        return "No relevant documents found."
    output = []
    for i, r in enumerate(results):
        output.append(f"[{i+1}] (score: {r['score']:.3f}) {r['text'][:500]}")
    return "\n".join(output)
```

- [ ] **Step 5: Create backend/tests/test_tools.py**

```python
import pytest
from app.services.tools import ToolRegistry, tool_registry


def test_registry_builtin():
    def dummy_tool(x: str) -> str:
        return f"got {x}"
    registry = ToolRegistry()
    registry.register("dummy", dummy_tool)
    result = registry.get_tool_schemas(["dummy"])
    assert len(result) == 1


@pytest.mark.asyncio
async def test_execute_builtin():
    def add(a: int, b: int) -> int:
        return a + b
    registry = ToolRegistry()
    registry.register("add", add)
    result = await registry.execute("add", {"a": 1, "b": 2})
    assert result == "3"


@pytest.mark.asyncio
async def test_execute_not_found():
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {})
    assert "not found" in result.lower()
```

- [ ] **Step 6: Run tests**

Run: `eval "$(conda shell.bash hook)" && conda activate dev && cd backend && pytest tests/test_tools.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/tools.py backend/app/tools/ backend/tests/test_tools.py
git commit -m "feat: add ToolRegistry with builtin tools and MCP client support"
```

---

### Task 4: Agent Engine (Agentic Mode)

**Files:**
- Create: `backend/app/services/agent.py`
- Modify: `backend/app/services/chat.py` (add RAG context, integrate agent)
- Modify: `backend/app/api/chat.py` (route to agent for agentic mode)
- Create: `backend/tests/test_agent.py`

- [ ] **Step 1: Create backend/app/services/agent.py**

```python
import json
import uuid
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Conversation, Message, MessageRole
from app.services.llm import LLMClient, llm_client
from app.services.tools import tool_registry
from app.services.knowledge import get_kb_context


MAX_ITERATIONS = 15
TOOL_TIMEOUT = 30
MAX_RESULT_LENGTH = 4000


async def agent_loop(
    conversation: Conversation,
    user_content: str,
    db: AsyncSession,
    llm: LLMClient | None = None,
) -> AsyncIterator[dict]:
    """Run Agentic mode: ReAct loop with tool calls. Yields SSE events."""

    client = llm or llm_client

    # Save user message
    user_msg = Message(conversation_id=conversation.id, role=MessageRole.USER, content=user_content)
    db.add(user_msg)
    await db.commit()

    # Build system prompt
    system_prompt = "You are a helpful AI assistant. Use tools when needed to accomplish tasks."
    if conversation.skill_id:
        from app.models import Skill
        from sqlalchemy import select
        skill = await db.execute(select(Skill).where(Skill.id == conversation.skill_id))
        skill_obj = skill.scalar_one_or_none()
        if skill_obj:
            system_prompt = skill_obj.system_prompt

    # Build message history
    from app.services.chat import get_conversation_messages, build_messages_for_llm
    history = await get_conversation_messages(db, conversation.id, limit=50)
    messages = build_messages_for_llm(history[:-1], system_prompt, user_content)

    # Add RAG context if KB is bound
    if conversation.knowledge_base_id:
        rag_context = await get_kb_context(str(conversation.knowledge_base_id), user_content)
        if rag_context:
            messages[0]["content"] += f"\n\n{rag_context}"

    # Get tool schemas
    tool_ids = conversation.enabled_tools or []
    tool_schemas = tool_registry.get_tool_schemas(tool_ids, db)
    if tool_schemas:
        messages[0]["content"] += "\n\nYou have access to the following tools. Use them when needed."

    iterations = 0
    agent_steps = []

    while iterations < MAX_ITERATIONS:
        iterations += 1

        response = await client.chat(messages, tools=tool_schemas if tool_schemas else None)

        choices = response.get("choices", [])
        if not choices:
            break

        msg = choices[0].get("message", {})
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            # Final response — stream it
            if content:
                for char in content:
                    yield {"event": "text", "data": json.dumps({"content": char})}
            break

        # Has tool calls — record thinking, execute tools
        if content:
            yield {"event": "thinking", "data": json.dumps({"content": content})}
            agent_steps.append({"type": "thinking", "content": content})

        messages.append(msg)

        for tc in tool_calls:
            fn_name = tc.get("function", {}).get("name", "")
            fn_args_str = tc.get("function", {}).get("arguments", "{}")
            try:
                fn_args = json.loads(fn_args_str)
            except json.JSONDecodeError:
                fn_args = {}

            tc_id = tc.get("id", str(uuid.uuid4()))

            yield {"event": "tool_call", "data": json.dumps({"id": tc_id, "name": fn_name, "args": fn_args})}
            agent_steps.append({"type": "tool_call", "id": tc_id, "name": fn_name, "args": fn_args})

            try:
                result = await tool_registry.execute(fn_name, fn_args, db)
                if len(result) > MAX_RESULT_LENGTH:
                    result = result[:MAX_RESULT_LENGTH] + "... (truncated)"
            except Exception as e:
                result = f"Error executing tool: {str(e)}"

            yield {"event": "tool_result", "data": json.dumps({"id": tc_id, "content": result})}
            agent_steps.append({"type": "tool_result", "id": tc_id, "content": result})

            messages.append({"role": "tool", "tool_call_id": tc_id, "content": result})

    # Force final summary if max iterations exceeded
    if iterations >= MAX_ITERATIONS and tool_calls:
        messages.append({"role": "user", "content": "You've reached the maximum number of steps. Please provide a final summary based on what you've gathered so far."})
        response = await client.chat(messages)
        content = response.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content:
            for char in content:
                yield {"event": "text", "data": json.dumps({"content": char})}

    # Save assistant message with agent steps
    full_content = content if not tool_calls else ""
    assistant_msg = Message(
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=full_content,
        agent_steps=agent_steps if agent_steps else None,
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)

    yield {"event": "done", "data": json.dumps({"message_id": str(assistant_msg.id), "steps": agent_steps})}
```

- [ ] **Step 2: Update backend/app/services/chat.py**

Add RAG context to normal_chat_stream. After building llm_messages, if conversation has knowledge_base_id, call `get_kb_context` and append to system prompt.

- [ ] **Step 3: Update backend/app/api/chat.py**

Change the `/send` endpoint: when `conversation.mode == "agentic"`, use `agent_loop` instead of `normal_chat_stream`. Remove the 501 error.

```python
from app.services.agent import agent_loop

# In send_message:
if conversation.mode == "agentic":
    stream = agent_loop(conversation, body.content, db)
else:
    stream = normal_chat_stream(conversation, body.content, db)

async def event_generator():
    async for event in stream:
        yield f"event: {event['event']}\ndata: {event['data']}\n\n"
```

- [ ] **Step 4: Create backend/tests/test_agent.py**

```python
import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient
from app.models import Conversation, ConversationMode


async def test_agentic_mode_no_tools(client, auth_header, test_user, db_session):
    """Agentic mode with no tools should behave like normal chat."""
    conv = Conversation(user_id=test_user.id, title="Agent Test", mode=ConversationMode.AGENTIC)
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # Mock LLM: no tool_calls, just text response
    mock_response = {"choices": [{"message": {"role": "assistant", "content": "Task complete."}, "finish_reason": "stop"}]}

    with patch("app.services.agent.llm_client") as mock_llm:
        mock_llm.chat = AsyncMock(return_value=mock_response)
        resp = await client.post("/api/chat/send", json={"conversation_id": str(conv.id), "content": "Do something"}, headers=auth_header)
        assert resp.status_code == 200
        assert "Task complete." in resp.text
        assert "event: text" in resp.text
        assert "event: done" in resp.text


async def test_agentic_mode_with_tool_call(client, auth_header, test_user, db_session):
    """Agentic mode with a tool call cycle."""
    conv = Conversation(user_id=test_user.id, title="Agent Tool Test", mode=ConversationMode.AGENTIC, enabled_tools=["web_search"])
    db_session.add(conv)
    await db_session.commit()
    await db_session.refresh(conv)

    # First call: returns tool_call. Second call: returns final text.
    call_count = 0

    async def mock_chat(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"choices": [{"message": {"role": "assistant", "content": "Let me search.", "tool_calls": [{"id": "tc1", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "test"}'}}]}, "finish_reason": "tool_calls"}]}
        else:
            return {"choices": [{"message": {"role": "assistant", "content": "Based on the search: found results."}, "finish_reason": "stop"}]}

    with patch("app.services.agent.llm_client") as mock_llm:
        mock_llm.chat = mock_chat
        resp = await client.post("/api/chat/send", json={"conversation_id": str(conv.id), "content": "Search for test"}, headers=auth_header)
        assert resp.status_code == 200
        body = resp.text
        assert "event: thinking" in body
        assert "event: tool_call" in body
        assert "event: tool_result" in body
        assert "event: text" in body
        assert "event: done" in body
```

- [ ] **Step 5: Run ALL tests**

Run: `eval "$(conda shell.bash hook)" && conda activate dev && cd backend && pytest tests/ -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/agent.py backend/app/services/chat.py backend/app/api/chat.py backend/tests/test_agent.py
git commit -m "feat: add Agentic mode with ReAct loop and SSE streaming"
```

---

### Task 5: Skill System CRUD API

**Files:**
- Create: `backend/app/schemas/skill.py`
- Create: `backend/app/api/skills.py`
- Modify: `backend/app/api/router.py`
- Create: `backend/tests/test_skills.py`

- [ ] **Step 1: Create backend/app/schemas/skill.py**

```python
from datetime import datetime
from pydantic import BaseModel, ConfigDict
import uuid


class SkillCreate(BaseModel):
    name: str
    description: str | None = None
    system_prompt: str
    tool_ids: list[str] | None = None
    knowledge_base_id: str | None = None


class SkillUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    tool_ids: list[str] | None = None
    knowledge_base_id: str | None = None


class SkillResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    system_prompt: str
    tool_ids: list | None
    knowledge_base_id: uuid.UUID | None
    is_builtin: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
```

- [ ] **Step 2: Create backend/app/api/skills.py**

Router prefix `/api/skills`, requires auth.
- `GET /` — list all skills
- `POST /` — create skill (admin only or any user)
- `PUT /{id}` — update skill
- `DELETE /{id}` — delete skill (only if is_builtin=False)

- [ ] **Step 3: Update backend/app/api/router.py**

Add `skills_router`.

- [ ] **Step 4: Create backend/tests/test_skills.py**

Tests:
- test_create_skill
- test_list_skills
- test_update_skill
- test_delete_custom_skill
- test_delete_builtin_skill_returns_error

- [ ] **Step 5: Run tests**

Run: `eval "$(conda shell.bash hook)" && conda activate dev && cd backend && pytest tests/test_skills.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/skill.py backend/app/api/skills.py backend/app/api/router.py backend/tests/test_skills.py
git commit -m "feat: add Skill CRUD API"
```

---

### Task 6: Full Suite Verification

**Files:** None new

- [ ] **Step 1: Run full test suite**

Run: `eval "$(conda shell.bash hook)" && conda activate dev && cd backend && pytest tests/ -v`

Expected: All tests pass

- [ ] **Step 2: Verify git log**

Run: `git log --oneline feat/backend-foundation --not main`

Should show all commits from Plan 1 + Plan 2.
