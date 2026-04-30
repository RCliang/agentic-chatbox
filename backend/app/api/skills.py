"""Skill CRUD endpoints."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import Skill, User
from app.schemas.skill import SkillCreate, SkillResponse, SkillUpdate

router = APIRouter(prefix="/api/skills", tags=["skills"])

# ---------------------------------------------------------------------------
# Official builtin skills definitions
# ---------------------------------------------------------------------------

BUILTIN_SKILLS = [
    {
        "name": "通用助手",
        "description": "通用AI对话助手，适用于日常问答和闲聊",
        "instructions": "你是一个友好且知识渊博的AI助手。请用简洁、准确的方式回答用户的问题。如果不确定答案，请诚实告知。",
        "tools": [],
        "references": [],
        "examples": [
            {"user": "今天天气怎么样？", "assistant": "我无法获取实时天气数据，建议您查看天气预报应用获取最新信息。"},
        ],
        "is_builtin": True,
    },
    {
        "name": "代码专家",
        "description": "专注于编程和代码相关问题的技术助手",
        "instructions": (
            "你是一个资深的编程专家。请帮助用户解决编程问题，给出清晰的代码示例和技术解释。\n"
            "优先考虑代码质量、可读性和最佳实践。\n"
            "回答时应包含：问题分析、解决方案、代码示例、注意事项。"
        ),
        "tools": [
            {"name": "web_search", "when": "用户提到需要查找技术文档、最新 API 或框架信息时", "required": False},
            {"name": "web_reader", "when": "需要阅读具体的技术文档网页获取详细信息时", "required": False},
        ],
        "references": [
            {
                "type": "text",
                "source": (
                    "代码风格要求：\n"
                    "- 优先使用类型注解\n"
                    "- 函数和类需要 docstring\n"
                    "- 变量命名清晰有意义\n"
                    "- 遵循 DRY 原则，避免代码重复"
                ),
                "title": "编码规范",
                "inject": "always",
            },
        ],
        "examples": [
            {
                "user": "帮我写一个 Python 快速排序",
                "assistant": "```python\ndef quicksort(arr: list[int]) -> list[int]:\n    \"\"\"Quick sort implementation.\"\"\"\n    if len(arr) <= 1:\n        return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)\n```",
            },
        ],
        "is_builtin": True,
    },
    {
        "name": "文档写作",
        "description": "帮助撰写和优化各类文档、报告和文案",
        "instructions": (
            "你是一个专业的文档写作助手。帮助用户撰写、优化和润色各类文档。\n"
            "包括技术文档、商业报告、邮件和文案。注意结构清晰、语言流畅、逻辑严密。\n"
            "写作时应考虑：目标读者、文档目的、格式要求。"
        ),
        "tools": [
            {"name": "web_search", "when": "需要查找背景资料或行业信息来支撑文档内容时", "required": False},
            {"name": "knowledge_search", "when": "需要从知识库中检索相关参考文档时", "required": False},
        ],
        "references": [
            {
                "type": "text",
                "source": (
                    "文档写作原则：\n"
                    "- 开头点明主旨，结尾总结要点\n"
                    "- 使用标题和列表提高可读性\n"
                    "- 数据和案例佐证观点\n"
                    "- 保持语言一致性和专业性"
                ),
                "title": "写作规范",
                "inject": "always",
            },
        ],
        "examples": [],
        "is_builtin": True,
    },
    {
        "name": "数据分析",
        "description": "协助进行数据分析、解读和可视化建议",
        "instructions": (
            "你是一个数据分析专家。帮助用户理解数据、发现规律、提出分析思路和可视化建议。\n"
            "擅长使用 Python/SQL 进行数据处理，熟悉常见的统计方法和分析框架。\n"
            "分析时应包含：数据理解、分析方法、代码实现、结果解读。"
        ),
        "tools": [
            {"name": "web_search", "when": "需要查找统计方法、数据处理库的文档或最佳实践时", "required": False},
        ],
        "references": [
            {
                "type": "text",
                "source": (
                    "常用数据分析工具：\n"
                    "- pandas: 数据处理和清洗\n"
                    "- numpy: 数值计算\n"
                    "- matplotlib/seaborn: 数据可视化\n"
                    "- scikit-learn: 机器学习建模\n"
                    "- SQL: 数据库查询和聚合"
                ),
                "title": "分析工具箱",
                "inject": "always",
            },
        ],
        "examples": [
            {
                "user": "我有一份销售数据 CSV，想分析季度趋势",
                "assistant": "我来帮你分析。首先用 pandas 读取数据，然后按季度聚合，最后可视化趋势：\n```python\nimport pandas as pd\nimport matplotlib.pyplot as plt\n\ndf = pd.read_csv('sales.csv', parse_dates=['date'])\ndf['quarter'] = df['date'].dt.to_period('Q')\nquarterly = df.groupby('quarter')['amount'].sum()\nquarterly.plot(kind='bar', title='季度销售趋势')\nplt.show()\n```",
            },
        ],
        "is_builtin": True,
    },
    {
        "name": "翻译助手",
        "description": "提供高质量的多语言翻译服务",
        "instructions": (
            "你是一个专业的翻译助手，精通中文、英文、日文等多种语言。\n"
            "请提供准确、自然、符合目标语言习惯的翻译。\n"
            "必要时解释文化差异和翻译选择。翻译技术文档时保留专业术语。"
        ),
        "tools": [
            {"name": "web_search", "when": "遇到生僻词、专业术语或需要确认最新译法时", "required": False},
        ],
        "references": [
            {
                "type": "text",
                "source": (
                    "翻译原则：\n"
                    "- 信（忠实原文）、达（通顺流畅）、雅（文辞优美）\n"
                    "- 技术术语保留英文原文并附中文解释\n"
                    "- 注意上下文语境和文化差异\n"
                    "- 区分正式与非正式语境"
                ),
                "title": "翻译准则",
                "inject": "always",
            },
        ],
        "examples": [
            {
                "user": "翻译：The quick brown fox jumps over the lazy dog",
                "assistant": "敏捷的棕色狐狸跳过了那只懒狗。\n\n注：这是一句英文全字母句（pangram），包含了英文字母表中的所有26个字母，常用于测试字体和键盘。",
            },
        ],
        "is_builtin": True,
    },
]


@router.post("/seed", response_model=list[SkillResponse], status_code=status.HTTP_200_OK)
async def seed_builtin_skills(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seed official builtin skills. Idempotent — skips existing ones."""
    created = []
    for defn in BUILTIN_SKILLS:
        existing = await db.execute(
            select(Skill).where(Skill.name == defn["name"], Skill.is_builtin == True)  # noqa: E712
        )
        if existing.scalar_one_or_none() is not None:
            continue
        skill = Skill(**defn)
        db.add(skill)
        await db.flush()
        await db.refresh(skill)
        created.append(skill)
    await db.commit()
    return created


@router.get("", response_model=list[SkillResponse])
async def list_skills(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return all skills (both builtin and custom)."""
    result = await db.execute(select(Skill).order_by(Skill.created_at.desc()))
    return result.scalars().all()


@router.post("", response_model=SkillResponse, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new custom skill."""
    skill = Skill(
        name=body.name,
        description=body.description,
        instructions=body.instructions,
        tools=[t.model_dump() for t in body.tools] if body.tools else None,
        references=[r.model_dump() for r in body.references] if body.references else None,
        examples=[e.model_dump() for e in body.examples] if body.examples else None,
        knowledge_base_id=(
            uuid.UUID(body.knowledge_base_id) if body.knowledge_base_id else None
        ),
        is_builtin=False,
    )
    db.add(skill)
    await db.commit()
    await db.refresh(skill)
    return skill


@router.put("/{skill_id}", response_model=SkillResponse)
async def update_skill(
    skill_id: uuid.UUID,
    body: SkillUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a skill (partial update)."""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    if "knowledge_base_id" in update_data and update_data["knowledge_base_id"] is not None:
        update_data["knowledge_base_id"] = uuid.UUID(update_data["knowledge_base_id"])
    # Serialize Pydantic sub-models to dicts for JSON columns
    for key in ("tools", "references", "examples"):
        if key in update_data and update_data[key] is not None:
            update_data[key] = [item.model_dump() if hasattr(item, "model_dump") else item for item in update_data[key]]

    for field, value in update_data.items():
        setattr(skill, field, value)

    await db.commit()
    await db.refresh(skill)
    return skill


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(
    skill_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a custom skill. Builtin skills cannot be deleted (403)."""
    result = await db.execute(select(Skill).where(Skill.id == skill_id))
    skill = result.scalar_one_or_none()
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Skill not found",
        )

    if skill.is_builtin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete a builtin skill",
        )

    await db.delete(skill)
    await db.commit()
