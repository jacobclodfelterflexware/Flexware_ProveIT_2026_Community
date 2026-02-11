"""Conversation models for multi-turn schema suggestion."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
import uuid


class MessageRole(str, Enum):
    """Role of message sender."""
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"


class ConversationStatus(str, Enum):
    """Status of a conversation."""
    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


@dataclass
class ConversationMessage:
    """A single message in the conversation."""
    id: str
    role: MessageRole
    content: str
    timestamp: datetime
    draft_proposal: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        role: MessageRole,
        content: str,
        draft_proposal: Optional[Dict[str, Any]] = None
    ) -> "ConversationMessage":
        """Create a new message with generated ID and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.utcnow(),
            draft_proposal=draft_proposal
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "draft_proposal": self.draft_proposal
        }


@dataclass
class SchemaConversation:
    """A conversation session for schema mapping."""
    id: str
    raw_topic: str
    raw_payload: str
    status: ConversationStatus
    messages: List[ConversationMessage]
    current_proposal: Optional[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    created_by: str
    context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        raw_topic: str,
        raw_payload: str,
        created_by: str,
        context: Optional[Dict[str, Any]] = None
    ) -> "SchemaConversation":
        """Create a new conversation session."""
        now = datetime.utcnow()
        return cls(
            id=str(uuid.uuid4()),
            raw_topic=raw_topic,
            raw_payload=raw_payload,
            status=ConversationStatus.ACTIVE,
            messages=[],
            current_proposal=None,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            context=context or {}
        )

    def add_message(self, message: ConversationMessage) -> None:
        """Add a message and update timestamp."""
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "raw_topic": self.raw_topic,
            "raw_payload": self.raw_payload,
            "status": self.status.value,
            "current_proposal": self.current_proposal,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by
        }
