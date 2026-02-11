"""Topic tree builder for organizing MQTT topics hierarchically."""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TopicNode:
    """A node in the topic tree."""

    name: str
    full_path: str
    children: Dict[str, "TopicNode"] = field(default_factory=dict)
    message_count: int = 0
    last_message: Optional[Dict[str, Any]] = None
    is_leaf: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "full_path": self.full_path,
            "children": [child.to_dict() for child in self.children.values()],
            "message_count": self.message_count,
            "last_message": self.last_message,
            "is_leaf": self.is_leaf,
        }


class TopicTreeBuilder:
    """Builds and maintains a hierarchical topic tree from MQTT messages."""

    def __init__(self):
        self.root = TopicNode(name="", full_path="")
        self.total_topics = 0
        self.total_messages = 0
        self.last_update = datetime.now()
        self._topic_nodes: Dict[str, TopicNode] = {}

    def add_message(self, topic: str, payload: str) -> None:
        """Add a message to the topic tree."""
        self.total_messages += 1
        self.last_update = datetime.now()

        # Split topic into parts
        parts = topic.split("/")
        current_node = self.root
        current_path = ""

        for i, part in enumerate(parts):
            if current_path:
                current_path = f"{current_path}/{part}"
            else:
                current_path = part

            if part not in current_node.children:
                # Create new node
                new_node = TopicNode(name=part, full_path=current_path)
                current_node.children[part] = new_node
                self._topic_nodes[current_path] = new_node

            current_node = current_node.children[part]

        # Update the leaf node
        is_new_topic = current_node.message_count == 0
        current_node.message_count += 1
        current_node.is_leaf = True

        if is_new_topic:
            self.total_topics += 1

        # Store last message
        try:
            parsed_payload = json.loads(payload) if payload else None
        except json.JSONDecodeError:
            parsed_payload = {"raw": payload[:500] if len(payload) > 500 else payload}

        current_node.last_message = {
            "payload": parsed_payload,
            "timestamp": int(self.last_update.timestamp() * 1000),
        }

    def get_tree(self) -> Optional[dict]:
        """Get the topic tree as a dictionary."""
        if not self.root.children:
            return None
        return self.root.to_dict()

    def get_stats(self) -> dict:
        """Get statistics about the topic tree."""
        return {
            "totalTopics": self.total_topics,
            "totalMessages": self.total_messages,
            "lastUpdate": int(self.last_update.timestamp() * 1000),
        }

    def clear(self) -> None:
        """Clear the topic tree."""
        self.root = TopicNode(name="", full_path="")
        self.total_topics = 0
        self.total_messages = 0
        self._topic_nodes.clear()

    def get_all_topics(self) -> List[str]:
        """Get all leaf topic paths."""
        return [
            path for path, node in self._topic_nodes.items()
            if node.is_leaf
        ]
