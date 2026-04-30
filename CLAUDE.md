# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Agentic Chatbox — a full-stack AI chatbot with a ReAct agent loop supporting tool use, RAG knowledge bases, and configurable skills.

## Tech Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async), PostgreSQL, Redis, Celery, Milvus (vector DB), JWT auth
- **Frontend:** React 19, TypeScript 5.8, Vite 6, Tailwind CSS 4, Zustand, react-router-dom 7

## Common Commands

### Backend (run from `backend/`)
```bash
docker-compose up                    # Start full stack (Postgres, Redis, backend)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload  # Run backend locally
pytest                               # Run all tests
pytest tests/test_foo.py::test_bar   # Run a single test
```

### Frontend (run from `frontend/`)
```bash
npm run dev       # Vite dev server
npm run build     # TypeScript check + Vite production build
npm run lint      # ESLint
npm run preview   # Preview production build
```

## Architecture

### Backend (`backend/app/`)

- **`services/agent.py`** — Core ReAct agent loop. Async generator that drives multi-turn LLM conversation with tool calling, yielding SSE events (`thinking`, `tool_call`, `tool_result`, `text`, `done`). Max 15 iterations.
- **`services/tools.py`** — Tool registry. Tools (web_search, web_reader, knowledge_search) are registered with function-calling schemas and executed server-side.
- **`services/knowledge.py`** — RAG pipeline. Documents are vectorized into Milvus; relevant chunks are retrieved and prepended to the system prompt.
- **`api/`** — FastAPI route handlers. Aggregated in `router.py`.
- **`models/`** — SQLAlchemy ORM models (user, conversation, message, skill, tool, knowledge_base, etc.).
- **`schemas/`** — Pydantic request/response schemas.
- **`core/`** — Config (`pydantic-settings` + `.env`), database setup, JWT security, Celery app.
- **`tasks/`** — Celery background tasks (document processing).
- **`tools/`** — Individual tool implementations.

### Frontend (`frontend/src/`)

- **Pages:** LoginPage, ChatPage, KnowledgePage, SkillsPage (routes: `/login`, `/`, `/admin/knowledge`, `/admin/skills`)
- **State:** Zustand stores (`authStore`, `chatStore`)
- **API:** Axios client in `api/client.ts`
- **Chat streaming:** SSE from backend, rendered with react-markdown

### Key Patterns

- Chat responses stream via SSE from the ReAct agent loop to the frontend
- Skills are configurable system prompts stored in DB, attached to conversations
- JWT auth protects both frontend routes (PrivateRoute) and backend endpoints (deps.py)
- Alembic manages database migrations
