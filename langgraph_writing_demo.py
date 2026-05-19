"""
LangGraph 多 Agent 协作示例：专业领域长文档写作系统

架构:
  Supervisor (主编)
    -> Outline Agent (大纲师)
    -> Research Agent (研究员)
    -> Writing Agent (写手)
    -> Review Agent (审校)
    -> Polish Agent (润色)

流程:
  1. User 提出需求 -> Supervisor 分派给 Outline Agent
  2. Outline Agent 产出大纲 -> 返回 Supervisor
  3. Supervisor 把每个章节派给 Research + Writing 循环
  4. 写完的章节 -> Review Agent 审校 -> 返回修改意见
  5. Supervisor 决定是退回修改还是进入润色
  6. Polish Agent 做最终润色
  7. 输出完整文档

pip install langgraph langgraph-supervisor langchain-openai
"""

import os
from typing import Literal, Annotated, Optional

# ============================================================
# 1. 配置 & 模型
# ============================================================

os.environ["OPENAI_API_KEY"] = "sk-your-key-here"

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.tools import tool
from langchain_core.tools import BaseTool
from langchain_core.runnables import RunnableConfig

# 使用 GPT-4o 保证质量
model = ChatOpenAI(model="gpt-4o", temperature=0.3)

# ============================================================
# 2. 定义状态类型
# ============================================================

from typing import TypedDict, List, Annotated
import operator

class WritingState(TypedDict):
    """多 Agent 写作系统的共享状态"""
    # 用户原始需求
    user_request: str
    
    # 目标受众
    target_audience: str  # 技术人员 / 管理者 / 普通读者
    
    # 大纲
    outline: str
    
    # 已完成的章节 {章节标题: 内容}
    sections: Annotated[dict, "章节字典"]
    
    # 当前正在处理的章节
    current_section: Optional[str]
    
    # 审校反馈 {章节标题: 反馈}
    review_feedback: Annotated[dict, "审校反馈字典"]
    
    # 写作轮次计数器
    writing_rounds: int
    
    # 最终文档
    final_document: str
    
    # 消息历史
    messages: list

# ============================================================
# 3. 定义 Tool（供 Agent 使用）
# ============================================================

@tool
def save_section(title: str, content: str) -> str:
    """保存一个已完成的章节内容"""
    return f"章节 '{title}' 已保存 ({len(content)} 字)"

@tool
def get_section(section_title: str) -> str:
    """获取指定章节的当前内容"""
    # 实际运行时从 state 读取，这里 Tool 仅做占位
    return f"获取章节: {section_title}"

@tool
def search_knowledge_base(query: str) -> str:
    """搜索内部知识库获取技术资料和参考信息"""
    # 模拟知识库查询
    knowledge = {
        "大模型": (
            "大语言模型(LLM)如 GPT-4、Claude 3.5、Gemini 1.5 等，"
            "参数量从 70B 到 1.8T 不等。2024-2025 年趋势包括：\n"
            "1. 多模态融合：文本+图像+音频统一处理\n"
            "2. 长上下文：从 128K 扩展到 1M-10M tokens\n"
            "3. Agentic AI：从对话到自主执行任务\n"
            "4. 小模型崛起：7B-14B 参数模型达到 GPT-3.5 水平"
        ),
        "RAG": (
            "检索增强生成(Retrieval-Augmented Generation)技术栈：\n"
            "1. 文档解析：Unstructured、LlamaParse\n"
            "2. 分块策略：语义分块、递归字符分块\n"
            "3. 向量化：OpenAI Embeddings、BGE、E5\n"
            "4. 向量库：Chroma、Pinecone、Weaviate、Qdrant\n"
            "5. 检索增强：HyDE、Multi-Query、RAG Fusion"
        ),
        "Agent": (
            "AI Agent 关键技术：\n"
            "1. 工具调用：Function Calling、MCP 协议\n"
            "2. 规划：ReAct、Plan-and-Execute、Tree-of-Thought\n"
            "3. 记忆：短期记忆(Context)、长期记忆(向量库)\n"
            "4. 多 Agent：Supervisor、Debate、Tool-Using 协作\n"
            "5. 评估：LangSmith、Arize、MLflow"
        ),
    }
    for key, val in knowledge.items():
        if key.lower() in query.lower():
            return val
    return f"在知识库中未找到 '{query}' 的精确匹配，建议使用通用搜索。"

@tool
def check_consistency(new_content: str, existing_sections: dict) -> str:
    """检查新内容与已有章节的一致性"""
    issues = []
    if len(new_content) < 50:
        issues.append("章节内容过短，建议扩充到至少 200 字")
    if "..." in new_content:
        issues.append("包含省略号，可能存在未完成内容")
    if not issues:
        return "一致性检查通过"
    return "发现以下问题:\n" + "\n".join(issues)

# ============================================================
# 4. 创建各个 Agent
# ============================================================

from langgraph.prebuilt import create_react_agent

# --- 4a. 大纲 Agent ---
outline_agent = create_react_agent(
    model=model,
    tools=[],
    name="outline_expert",
    prompt=(
        "你是专业的大纲编写专家。你的职责：\n"
        "1. 根据用户需求，输出结构完整的文档大纲\n"
        "2. 大纲要有 Introduction -> Main Body -> Conclusion 结构\n"
        "3. 每个章节要有 2-4 个子节\n"
        "4. 标注每个章节的目标字数\n"
        "5. 输出格式要清晰，用 Markdown 标题层级\n\n"
        "注意：只输出大纲，不要写正文内容。"
    ),
)

# --- 4b. 研究 Agent ---
research_agent = create_react_agent(
    model=model,
    tools=[search_knowledge_base],
    name="research_expert",
    prompt=(
        "你是资深技术研究员。\n"
        "1. 你只负责查找和整理资料，不写正文\n"
        "2. 使用 search_knowledge_base 搜索相关知识\n"
        "3. 输出结构化的研究摘要，包括关键点、数据、引用来源\n"
        "4. 如果某个信息不完整，明确指出知识缺口\n"
        "5. 关注 2024-2025 年的最新信息"
    ),
)

# --- 4c. 写作 Agent ---
writing_agent = create_react_agent(
    model=model,
    tools=[save_section, check_consistency],
    name="writing_expert",
    prompt=(
        "你是专业的技术文档写手。\n"
        "1. 根据大纲和研究资料，撰写高质量章节\n"
        "2. 语言要保持专业性和可读性的平衡\n"
        "3. 适当使用代码示例、表格、流程图（mermaid）来增强表达\n"
        "4. 每个章节完成后调用 save_section 保存\n"
        "5. 严格遵守目标字数，不要超太多\n"
        "6. 使用中文写作，但技术术语保留英文\n"
        "7. 风格：清晰、准确、有深度"
    ),
)

# --- 4d. 审校 Agent ---
review_agent = create_react_agent(
    model=model,
    tools=[check_consistency],
    name="review_expert",
    prompt=(
        "你是严格的审校专家。检查以下方面：\n"
        "1. 事实准确性：是否有错误的技术陈述？\n"
        "2. 逻辑连贯性：段落之间是否流畅衔接？\n"
        "3. 完整性：是否覆盖了大纲要求的要点？\n"
        "4. 风格一致：是否保持了统一的语调和技术深度？\n"
        "5. 格式规范：代码、列表、标题格式是否正确？\n\n"
        "输出格式：\n"
        "- PASS: 通过，可直接发布\n"
        "- MINOR: 小问题，标注位置和建议\n"
        "- MAJOR: 需要重写，说明原因\n"
        "- CRITICAL: 存在事实错误，必须修正"
    ),
)

# --- 4e. 润色 Agent ---
polish_agent = create_react_agent(
    model=model,
    tools=[],
    name="polish_expert",
    prompt=(
        "你是终稿润色专家。\n"
        "1. 修正错别字和语法问题\n"
        "2. 统一术语使用（例如全文统一用"大语言模型"而非混用）\n"
        "3. 优化句式，使表达更简洁有力\n"
        "4. 统一标点、段落间距等格式\n"
        "5. 保持原文的技术准确性和风格\n"
        "6. 输出最终版本，附带简短的修改说明"
    ),
)

# ============================================================
# 5. 构建 Supervisor 多 Agent 系统
# ============================================================

from langgraph_supervisor import create_supervisor
from langgraph_supervisor.handoff import create_forward_message_tool

# 转发工具：Supervisor 可以直接透传子 Agent 的回复
forwarding_tool = create_forward_message_tool("supervisor")

# 创建主编 Supervisor
workflow = create_supervisor(
    agents=[
        outline_agent,
        research_agent,
        writing_agent,
        review_agent,
        polish_agent,
    ],
    model=model,
    prompt=(
        "你是文档主编（Editor-in-Chief），管理一个专业写作团队。\n\n"
        "团队人员：\n"
        "- outline_expert: 大纲师，负责生成整篇文档的结构\n"
        "- research_expert: 研究员，负责搜索和整理资料\n"
        "- writing_expert: 写手，负责撰写正文\n"
        "- review_expert: 审校，负责检查质量和一致性\n"
        "- polish_expert: 润色，负责终稿打磨\n\n"
        "工作流程：\n"
        "1. 第一步 -> 分派给 outline_expert 生成大纲\n"
        "2. 拿到大纲后 -> 分派给 research_expert 研究相关主题\n"
        "3. 研究完成 -> 分派给 writing_expert 撰写正文\n"
        "4. 写作完成 -> 分派给 review_expert 审校\n"
        "5a. 如果审校发现 MAJOR/CRITICAL 问题 -> 退回 writing_expert 修改\n"
        "5b. 如果审校通过或只有 MINOR 问题 -> 进入 polish_expert 润色\n"
        "6. 润色完成后 -> 输出最终结果\n\n"
        "约束：\n"
        "- 一次只分派一个任务给一个 Agent\n"
        "- 每个 Agent 完成后再决定下一步\n"
        "- 不要跳过步骤，也不要在一个 Agent 完成前做其他事\n"
        "- 审校退回修改时，最多做 2 轮迭代"
    ),
    supervisor_name="editor_in_chief",
    output_mode="last_message",
    tools=[forwarding_tool],
)

# 编译
app = workflow.compile()

# ============================================================
# 6. 可视化（可选）
# ============================================================

# 生成 Mermaid 图
from langgraph.graph import StateGraph
mermaid_code = app.get_graph().draw_mermaid()
print("=== 工作流图 (Mermaid) ===")
print(mermaid_code)

# ============================================================
# 7. 运行
# ============================================================

def run_writing_pipeline(user_request: str, audience: str = "技术人员"):
    """运行长文档写作流水线"""
    
    print(f"\n{'='*60}")
    print(f"📝 开始写作任务")
    print(f"需求: {user_request}")
    print(f"受众: {audience}")
    print(f"{'='*60}\n")
    
    result = app.invoke({
        "messages": [
            SystemMessage(
                content=(
                    f"你是专业文档主编，今天要完成的写作任务：\n\n"
                    f"主题: {user_request}\n"
                    f"目标受众: {audience}\n"
                    f"语言: 中文\n\n"
                    f"请按标准流程逐步分派给团队完成。"
                )
            ),
            HumanMessage(
                content=f"请开始撰写关于「{user_request}」的专业长文，目标受众是{audience}。"
            ),
        ],
        "user_request": user_request,
        "target_audience": audience,
        "outline": "",
        "sections": {},
        "current_section": None,
        "review_feedback": {},
        "writing_rounds": 0,
        "final_document": "",
    })
    
    final_output = result.get("final_document", "") or ""
    messages = result.get("messages", [])
    
    print(f"\n{'='*60}")
    print(f"✅ 写作完成!")
    print(f"{'='*60}\n")
    
    # 输出最终消息
    if messages:
        last_msg = messages[-1]
        if hasattr(last_msg, 'content'):
            print(last_msg.content[:3000])
            if len(last_msg.content) > 3000:
                print(f"\n... (内容过长，截断显示，共 {len(last_msg.content)} 字)")
    
    if final_output:
        print(f"\n最终文档长度: {len(final_output)} 字")
    
    return result

# ============================================================
# 8. 运行示例
# ============================================================

if __name__ == "__main__":
    result = run_writing_pipeline(
        user_request="2025年AI Agent开发技术全景分析：框架对比、架构模式与生产化实践",
        audience="有2-5年经验的AI开发工程师"
    )
