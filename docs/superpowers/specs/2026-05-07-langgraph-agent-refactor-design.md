# LangGraph Agent 重构设计

## 概述

将现有手写 ReAct agent 循环（`agent.py`）替换为 LangGraph StateGraph 实现，引入混合模式（简单问题走单 agent、复杂问题走 planner→executor），支持 Skill 级 planning 配置、完整执行链路可视化、以及基于 checkpointer 的 human-in-the-loop。

## 核心决策

| 决策点 | 选择 |
|--------|------|
| 图结构 | 混合模式：简单走 agent，复杂走 planner→executor |
| 复杂判定 | Skill 级配置 `planning_mode: "auto"\|"always"\|"never"` |
| 前端事件 | plan 事件 + 节点流转，完整执行链路可视化 |
| 状态持久化 | LangGraph PostgreSQL checkpointer |
| Human-in-the-loop | plan 确认 + 敏感工具确认 |
| 迁移策略 | 方案 A — 整体替换 |

---

## 1. LangGraph 图结构

```
                    ┌─────────┐
                    │  START  │
                    └────┬────┘
                         │
                    ┌────▼────┐
                    │  router │  (根据 skill.planning_mode + LLM 判断)
                    └────┬────┘
                    ┌────┴────┐
                    │         │
              ┌─────▼───┐ ┌──▼──────────┐
              │  agent  │ │   planner   │
              └────┬────┘ └──────┬──────┘
                   │             │
                   │      ┌──────▼──────┐
                   │      │  interrupt  │ (等用户确认 plan)
                   │      │ (human_review_plan)
                   │      └──────┬──────┘
                   │             │
                   │      ┌──────▼──────┐
                   │      │  executor   │ (逐步执行 plan steps)
                   │      └──────┬──────┘
                   │             │
              ┌────▼────────────▼────┐
              │      tool_node       │ (执行工具，带 interrupt 判断)
              └────┬─────────────────┘
                   │
          ┌────────▼────────┐
          │ interrupt?      │ (tool.require_confirmation)
          │(human_review_tool)│
          └────────┬────────┘
                   │
              ┌────▼────┐
              │ respond │ (生成最终回复)
              └────┬────┘
                   │
              ┌────▼────┐
              │   END   │
              └─────────┘
```

### State 定义

```python
class PlanStep(TypedDict):
    id: str
    title: str
    description: str
    status: Literal["pending", "running", "done", "failed"]

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # 对话历史
    plan: list[PlanStep] | None              # 当前计划
    current_step: int                        # 执行到第几步
    skill: SkillConfig | None                # 当前 skill 配置
    tools_available: list[str]               # 可用工具列表
    sse_events: Annotated[list, operator.add] # 累积的 SSE 事件
```

### 节点职责

| 节点 | 职责 | 输入 | 输出 |
|-----|------|------|------|
| `router` | 根据 skill.planning_mode 决定路径 | AgentState | 条件边 → agent 或 planner |
| `planner` | 调用 LLM 生成 plan | messages + skill context | plan steps |
| `agent` | 简单对话，直接 LLM + tool calling | messages + tools | response 或 tool_calls |
| `executor` | 逐步执行 plan，每步调用 LLM | plan + current_step | tool_calls 或 step result |
| `tool_node` | 执行工具 + interrupt 判断 | tool_calls | tool results |
| `respond` | 生成最终回复，保存到 DB | 全部上下文 | final text |

### Router 逻辑

- `planning_mode = "never"` → 直接走 agent
- `planning_mode = "always"` → 直接走 planner
- `planning_mode = "auto"` → 调用 LLM 判断（structured output `{need_plan: bool}`）

---

## 2. SSE 事件体系

### 事件类型

| 事件 | 触发时机 | data 结构 | 前端渲染 |
|------|---------|-----------|---------|
| `node_enter` | 进入图节点 | `{node: string, label: string}` | 节点状态指示器 |
| `node_exit` | 离开图节点 | `{node: string, duration_ms: number}` | 更新节点为完成 |
| `plan` | planner 生成计划 | `{steps: PlanStep[]}` | 可折叠计划列表 |
| `plan_step_update` | executor 执行某步 | `{step_id: string, status: string}` | 更新步骤状态 |
| `interrupt` | 需要用户确认 | `{type: "plan"\|"tool", payload: any}` | 确认弹窗 |
| `thinking` | LLM 推理（保留） | `{content: string}` | 推理过程展示 |
| `tool_call` | 工具调用（保留） | `{id, name, arguments}` | 工具调用展示 |
| `tool_result` | 工具返回（保留） | `{id, name, result}` | 工具结果展示 |
| `text` | 最终文本（保留） | `{content: string}` | markdown 渲染 |
| `done` | 完成（保留） | `{message_id: string}` | 结束标记 |

### SSE 流产生方式

在每个 LangGraph 节点内部产出事件，通过 `astream_events` 或回调收集，在 FastAPI SSE endpoint 中转为 `text/event-stream` 格式推送。

---

## 3. Skill 模型扩展与渐进加载

### 新增字段

```python
class Skill(Base):
    # 现有字段保留

    planning_mode: str = "auto"      # "auto" | "always" | "never"
    confirm_plan: bool = True        # plan 生成后是否需要用户确认
    confirm_tools: list[str] = []    # 需要用户确认的工具名列表
```

### 渐进加载策略（三阶段）

1. **Phase 1 — 构建 system prompt 时**：instructions + always-inject references + tool guidance + examples（现有逻辑保留）
2. **Phase 2 — 每轮对话时**：on-demand references，基于用户消息做 RAG 检索（现有逻辑保留）
3. **Phase 3 — executor 步骤级加载（新增）**：当 executor 执行 plan 某一步时，根据该步骤涉及的工具动态检索相关 reference 注入上下文

### Phase 3 reference 配置

```json
{
    "title": "API 文档",
    "type": "knowledge_base",
    "source": "kb_xxx",
    "inject": "on_step",
    "match_tools": ["web_reader"]
}
```

当 executor 执行的步骤调用了 `web_reader` 工具时，才将此 reference 的内容检索注入上下文。

### Skill 配置完整示例

```json
{
    "name": "研究助手",
    "instructions": "你是一个研究助手...",
    "planning_mode": "auto",
    "confirm_plan": true,
    "confirm_tools": ["web_search"],
    "references": [
        {"title": "搜索指南", "type": "text", "source": "...", "inject": "always"},
        {"title": "领域知识", "type": "knowledge_base", "source": "kb_123", "inject": "on_demand"},
        {"title": "API文档", "type": "knowledge_base", "source": "kb_456", "inject": "on_step", "match_tools": ["web_reader"]}
    ],
    "tools": [
        {"name": "web_search", "when": "需要搜索时", "required": true},
        {"name": "web_reader", "when": "需要读取网页时", "required": false}
    ]
}
```

---

## 4. Checkpointer 与 Human-in-the-Loop

### Checkpointer

- 使用 `langgraph-checkpoint-postgres`，复用现有 PostgreSQL 连接
- `thread_id` 直接使用 `conversation.id`（UUID），不引入新 ID 体系
- checkpoint 表由 LangGraph 自动创建管理

### Interrupt 流程

```
1. 图执行到 interrupt 点 → 状态写入 checkpoint → 向前端发 interrupt 事件
2. 前端展示确认 UI → 用户操作（approve / reject / edit）
3. 前端发 POST /api/chat/resume → 带 thread_id + 用户决策
4. 后端用 Command(resume=user_decision) 恢复图执行
5. 继续产出 SSE 事件流
```

### Interrupt 触发条件

- **Plan 确认**：`skill.confirm_plan == True` 时，planner 生成 plan 后触发 interrupt
- **Tool 确认**：工具名在 `skill.confirm_tools` 列表中时，tool_node 执行前触发 interrupt

### API 变更

```python
# 现有 — 保留
POST /api/chat/send              # 发送消息，触发图执行，返回 SSE 流

# 新增
POST /api/chat/resume            # 恢复被 interrupt 的图执行
  body: {
      conversation_id: str,
      action: "approve" | "reject" | "edit",
      payload: {...}              # edit 时携带修改内容
  }
  response: SSE stream            # 继续流式输出后续事件

GET /api/chat/{conversation_id}/status    # 检查是否有 pending interrupt
  response: {
      state: "idle" | "running" | "waiting_for_input",
      interrupt_data: {...} | null
  }
```

---

## 5. 后端文件结构

```
backend/app/
├── services/
│   ├── agent.py              # 重写：LangGraph 图定义 + 编译
│   ├── agent_nodes.py        # 新增：各节点实现
│   ├── agent_state.py        # 新增：AgentState + PlanStep 定义
│   ├── agent_events.py       # 新增：SSE 事件生成
│   ├── checkpointer.py       # 新增：PostgreSQL checkpointer 初始化
│   ├── chat.py               # 微调：build_messages_for_llm 保留复用
│   ├── tools.py              # 保留
│   ├── knowledge.py          # 保留
│   └── llm.py                # 保留
├── api/
│   ├── chat.py               # 修改：新增 /resume 和 /status 端点
│   └── ...
├── models/
│   └── skill.py              # 修改：新增 planning_mode, confirm_plan, confirm_tools
└── schemas/
    └── chat.py               # 修改：新增 ResumeRequest schema
```

### 依赖关系

`agent.py`（图定义）→ `agent_nodes.py`（节点）→ `agent_state.py`（状态）+ `agent_events.py`（事件）

现有 `tools.py`、`knowledge.py`、`llm.py` 作为底层服务被节点调用，不改动。

---

## 6. 前端变更

### 文件结构

```
frontend/src/
├── components/
│   ├── AgentStep.tsx          # 重构：支持新事件类型
│   ├── PlanView.tsx           # 新增：plan 步骤列表
│   ├── InterruptDialog.tsx    # 新增：interrupt 确认弹窗
│   ├── NodeTracker.tsx        # 新增：节点执行流程指示器
│   └── ChatArea.tsx           # 修改：集成新组件
├── stores/
│   └── chatStore.ts           # 修改：新增 interrupt 状态 + resume 方法
├── api/
│   └── client.ts              # 修改：新增 resume、getConversationStatus
└── types/
    └── index.ts               # 修改：新增事件类型定义
```

### chatStore 新增状态与方法

```typescript
interface ChatState {
  // 新增
  interruptData: InterruptData | null;
  planSteps: PlanStep[];
  activeNodes: NodeStatus[];

  // 新增方法
  resumeInterrupt: (action: string, payload?: any) => void;
  checkConversationStatus: () => void;
}
```

### 新组件

- **PlanView**：渲染 plan 步骤列表，每步显示标题、描述、状态图标（pending/running/done/failed），可折叠
- **InterruptDialog**：
  - Plan 模式：展示步骤列表，用户可编辑、删除、重排，approve/reject 按钮
  - Tool 模式：展示工具名 + 参数预览，approve/reject 按钮
- **NodeTracker**：顶部横向流程指示器，显示当前图执行到哪个节点

### AgentStep 扩展

```tsx
case 'node_enter':       → <NodeTracker>
case 'node_exit':        → 更新 NodeTracker 状态
case 'plan':             → <PlanView>
case 'plan_step_update': → 更新 PlanView 步骤状态
case 'interrupt':        → <InterruptDialog>
```

---

## 7. 新增依赖

### Backend

```
langgraph>=0.2
langgraph-checkpoint-postgres>=2.0
```

### Frontend

无新增依赖。
