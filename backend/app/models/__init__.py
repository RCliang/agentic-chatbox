"""Database models for the agentic chatbox application."""

from app.models.base import Base
from app.models.conversation import Conversation, ConversationMode
from app.models.department import Department
from app.models.knowledge_base import KnowledgeBase, KnowledgeBaseScope
from app.models.knowledge_document import DocumentSource, DocumentStatus, KnowledgeDocument
from app.models.knowledge_share import KnowledgeBaseShare
from app.models.message import Message, MessageRole
from app.models.skill import Skill
from app.models.tool import Tool, ToolType
from app.models.user import User

__all__ = [
    # Base
    "Base",
    # Models
    "Department",
    "User",
    "Conversation",
    "Message",
    "Skill",
    "Tool",
    "KnowledgeBase",
    "KnowledgeDocument",
    "KnowledgeBaseShare",
    # Enums
    "ConversationMode",
    "MessageRole",
    "ToolType",
    "KnowledgeBaseScope",
    "DocumentSource",
    "DocumentStatus",
]
