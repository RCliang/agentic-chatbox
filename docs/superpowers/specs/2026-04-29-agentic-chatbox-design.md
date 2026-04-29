# Agentic Chatbox — Design Spec

## Overview

类 Claude 的 Web 端 AI Agent 产品，面向内部团队使用。支持 Normal（普通聊天）和 Agentic（自主执行）两种对话模式，集成知识库 RAG、Skill 配置、MCP 工具调用能力。

## Tech Stack

- **Frontend**: React 18 + TypeScript, Zustand, React Router v6, Tailwind CSS, React Markdown, Vite
- **Backend**: Python FastAPI, Uvicorn
- **Database**: PostgreSQL (Alembic migrations)
- **Vector DB**: Milvus
- **Async Tasks**: Celery + Redis
- **LLM**: OpenAI 兼容格式 API（内部模型服务）
- **External**: MCP Server（飞书文档等）

## Architecture

### Monolithic Layered Architecture

单体分层架构，FastAPI 按 4 个核心模块划分：

- **Chat Module**: 对话管理、SSE 流式输出、ChatRouter 模式分发
- **Agent Module**: AgentLoop ReAct 循环、Tool Use 编排
- **Knowledge Module**: 文件上传、向量化、RAG 检索
- **Tool Module**: ToolRegistry 工具注册表、MCP Client、内置工具

### Dual-Mode Chat

**Normal Mode**: 用户消息 → RAG 检索（可选）→ LLM 直接回复 → SSE `text` 事件流式返回。单轮请求-响应。

**Agentic Mode**: 用户消息 → AgentLoop 循环（Think → Act → Observe）→ 自主调用工具、多轮迭代 → SSE 事件流实时推送执行过程 → 最终回复。

**Chat Router**: 后端根据 `conversation.mode` 将请求分发到 NormalHandler 或 AgentLoop，两者共享 Tool Engine、Knowledge、Skill 模块。

### AgentLoop (ReAct)

```
while iterations < max_iterations (default: 15):
    response = await llm.chat(messages, tools=tool_schemas)
    if no tool_calls:
        stream response.content → SSE event: text
        persist message → return
    else:
        for tool_call in response.tool_calls:
            result = await execute_tool(tool_call)
            push SSE events: tool_call, tool_result
            append result to messages
    iterations++
# max iterations exceeded → force final summary
```

安全机制: max_iterations 防无限循环、tool 超时 30s、结果截断防 token 爆炸、仅启用对话绑定的工具。

### Skill Integration

Skill = System Prompt + Tool Binding + Knowledge Base（可选）。用户在创建 Agentic 对话时选择 Skill，Skill 的配置驱动 AgentLoop 初始化：

- `system_prompt` → Agent 的角色 prompt
- `tool_ids` → 限制 Agent 可用的工具集
- `knowledge_base_id` → 自动参与 RAG 检索

不选 Skill 时使用默认 prompt + 用户手动勾选的工具。

## API Design

### Auth — /api/auth
- `POST /login` — 登录，返回 JWT
- `POST /logout` — 登出
- `GET /me` — 当前用户信息

### Conversations — /api/conversations
- `GET /` — 对话列表（分页）
- `POST /` — 创建对话 `{title, mode, skill_id?, kb_id?, tool_ids?}`
- `GET /{id}` — 对话详情
- `DELETE /{id}` — 删除对话
- `GET /{id}/messages` — 消息历史

### Chat (SSE) — /api/chat
- `POST /send` — 发送消息，返回 SSE stream

SSE 事件类型:
- Normal: `text` → `done`
- Agentic: `thinking` → `tool_call` → `tool_result` → `text` → `done`

### Skills — /api/skills
- `GET /` — Skill 列表
- `POST /` — 创建 Skill `{name, description, system_prompt, tool_ids[], knowledge_base_id?}`
- `PUT /{id}` — 更新 Skill
- `DELETE /{id}` — 删除 Skill（仅 builtin=false）

### Tools — /api/tools
- `GET /` — 工具列表
- `PUT /{id}/toggle` — 启用/禁用工具
- `PUT /{id}/config` — 更新工具配置参数

### Knowledge — /api/knowledge
- `GET /bases` — 用户可访问的知识库列表
- `POST /bases` — 创建知识库 `{name, scope, department_id?}`
- `DELETE /bases/{id}` — 删除知识库
- `POST /bases/{id}/documents` — 上传文档 (multipart)
- `POST /bases/{id}/feishu-sync` — 同步飞书文档（通过 MCP Server）
- `DELETE /bases/{id}/documents/{doc_id}` — 删除文档
- `GET /bases/{id}/documents` — 文档列表 + 状态

## Data Model

### departments
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| name | VARCHAR UNIQUE | 部门名称 |
| parent_id | UUID FK NULL | 上级部门（支持层级） |
| created_at | TIMESTAMP | |

### users
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| username | VARCHAR UNIQUE | |
| password_hash | VARCHAR | |
| display_name | VARCHAR | |
| avatar_url | VARCHAR NULL | |
| department_id | UUID FK → departments | 所属部门 |
| position | VARCHAR | 职位 |
| is_dept_admin | BOOLEAN DEFAULT false | 是否部门管理员 |
| created_at | TIMESTAMP | |

### conversations
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| user_id | UUID FK → users | |
| title | VARCHAR | |
| mode | ENUM(normal, agentic) | 对话模式 |
| skill_id | UUID FK → skills NULL | 绑定的 Skill（创建时选定） |
| knowledge_base_id | UUID FK NULL | 绑定的知识库 |
| enabled_tools | JSONB (tool_id[]) | 该对话启用的工具 |
| created_at | TIMESTAMP | |
| updated_at | TIMESTAMP | |

### messages
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| conversation_id | UUID FK → conversations | |
| role | ENUM(user, assistant, tool, system) | |
| content | TEXT | |
| tool_calls | JSONB NULL | LLM 工具调用 |
| tool_call_id | VARCHAR NULL | 工具调用 ID |
| agent_steps | JSONB NULL | Agentic 模式执行轨迹 |
| created_at | TIMESTAMP | |

### skills
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| name | VARCHAR UNIQUE | |
| description | TEXT | |
| system_prompt | TEXT | Agent 角色 prompt |
| tool_ids | JSONB (tool_id[]) | 绑定的工具 |
| knowledge_base_id | UUID FK NULL | 关联知识库 |
| is_builtin | BOOLEAN | 是否内置 |
| created_at | TIMESTAMP | |

### tools
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| name | VARCHAR UNIQUE | |
| description | TEXT | |
| parameters_schema | JSONB | JSON Schema |
| type | ENUM(builtin, mcp) | 工具类型 |
| handler | VARCHAR NULL | 本地 handler 模块路径（builtin） |
| mcp_server_url | VARCHAR NULL | MCP Server 地址（mcp） |
| mcp_tool_name | VARCHAR NULL | MCP 上的工具名（mcp） |
| config | JSONB NULL | 连接参数等 |
| is_enabled | BOOLEAN | |
| created_at | TIMESTAMP | |

### knowledge_bases
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| name | VARCHAR | |
| description | TEXT NULL | |
| scope | ENUM(personal, department) | 知识库范围 |
| owner_id | UUID FK → users | 创建者 |
| department_id | UUID FK → departments NULL | 关联部门 |
| embedding_model | VARCHAR | |
| chunk_size | INT DEFAULT 512 | |
| chunk_overlap | INT DEFAULT 50 | |
| milvus_collection | VARCHAR | |
| created_at | TIMESTAMP | |

### knowledge_documents
| Column | Type | Description |
|--------|------|-------------|
| id | UUID PK | |
| knowledge_base_id | UUID FK → knowledge_bases | |
| source_type | ENUM(upload, feishu) | |
| title | VARCHAR | |
| file_path | VARCHAR NULL | 上传文件路径 |
| feishu_doc_id | VARCHAR NULL | 飞书文档 ID |
| uploaded_by | UUID FK → users | 上传者 |
| status | ENUM(pending, indexing, ready, failed) | |
| chunk_count | INT DEFAULT 0 | |
| indexed_at | TIMESTAMP NULL | |
| created_at | TIMESTAMP | |

### Permission Rules

- **Personal KB (scope=personal)**: owner 可完全管理，其他人不可见
- **Department KB (scope=department)**: 部门所有人可查看/使用，仅 is_dept_admin 可创建/删除 KB 和管理文档
- **RAG 检索**: 查询范围 = 用户 personal KBs + 用户 department KB

## RAG Pipeline

### 文档处理流程（Celery 异步）

文件上传 / 飞书同步（通过 MCP）→ `process_document` Celery Task → 文件解析（PDF/Word/Markdown → 纯文本）→ 文本分块（chunk_size/overlap）→ 向量化（Embedding Model）→ 存入 Milvus → 更新文档状态为 ready。

### Milvus Collection

每个知识库对应一个 collection: `kb_{knowledge_base_id}`

| Field | Type | Description |
|-------|------|-------------|
| id | VARCHAR PK | |
| embedding | FLOAT_VECTOR(1024) | |
| text | VARCHAR | 原文 |
| doc_id | VARCHAR | 关联文档 |
| metadata | JSON | 页码/标题等 |

Index: IVF_FLAT | 检索: top_k=5, metric=cosine

### RAG Retrieval

对话时对 query 做向量化，从绑定的知识库 collection 中检索 top_k=5 相关片段，注入 system prompt 上下文提供给 LLM。

## MCP Integration

ToolRegistry 支持两种工具类型：
- **builtin**: 直接调用本地 handler 函数
- **mcp**: 通过 MCP Client 转发到外部 MCP Server

飞书文档读取通过已部署的 MCP Server 处理，注册为 type=mcp 工具。飞书能力同时可作为 Agent 可用工具。

### 预置内置工具

- `web_search` — 网页搜索
- `web_reader` — 网页内容读取
- `knowledge_search` — 知识库检索
- `code_execute` — 代码沙箱执行

## Frontend

### Pages

- `/` — 主聊天页面（Sidebar + ChatArea + Input）
- `/login` — 登录页
- `/new-chat` — 新建对话（选模式/Skill/KB）
- `/admin/knowledge` — 知识库管理（CRUD + 文档管理 + 飞书同步）
- `/admin/skills` — Skill 管理（CRUD + 工具绑定）

### Chat UI Features

- 顶部 Normal / Agentic 模式切换 Tab
- 左侧对话列表（显示模式、Skill 标签）
- 输入框上方知识库选择器（添加/移除 KB 标签）
- 输入框左侧图片上传按钮（多图预览）
- Agentic 模式实时展示 Agent 执行过程（思考 → 工具调用 → 结果 → 回复）
- 深色主题

## Deployment

Docker Compose 编排: Nginx → FastAPI (Uvicorn multi-worker) → Celery Worker + Beat → Redis → PostgreSQL + Milvus。LLM Service 和 MCP Server 作为外部依赖。

### Project Structure

```
agentic-chatbox/
├── backend/
│   ├── app/
│   │   ├── api/          # 路由层
│   │   ├── core/         # 配置、安全、依赖注入
│   │   ├── models/       # SQLAlchemy ORM
│   │   ├── schemas/      # Pydantic 模型
│   │   ├── services/
│   │   │   ├── chat.py       # NormalHandler + ChatRouter
│   │   │   ├── agent.py      # AgentLoop (ReAct)
│   │   │   ├── knowledge.py  # RAG 检索 + 文档管理
│   │   │   └── tools.py      # ToolRegistry + MCP Client
│   │   ├── tools/        # 内置工具实现
│   │   └── tasks/        # Celery 任务
│   ├── alembic/
│   └── tests/
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── stores/
│       ├── hooks/
│       └── api/
├── docker-compose.yml
└── .env.example
```
