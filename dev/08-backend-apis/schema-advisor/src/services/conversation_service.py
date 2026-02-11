"""Conversation management service for multi-turn schema suggestions."""
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from neo4j import AsyncDriver

from models.conversation import (
    SchemaConversation,
    ConversationMessage,
    ConversationStatus,
    MessageRole
)
from services.mcp_client import MCPClient
from services.llm_client import LLMClient
from prompts.conversation_prompts import format_conversation_for_llm

logger = logging.getLogger(__name__)


class ConversationService:
    """Manages schema mapping conversations."""

    def __init__(self, driver: AsyncDriver, mcp: MCPClient, llm: LLMClient):
        self.driver = driver
        self.mcp = mcp
        self.llm = llm

    async def start_conversation(
        self,
        raw_topic: str,
        raw_payload: str,
        created_by: str = "api-user",
        initial_suggestion: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Start a new conversation for a topic.

        1. Check if active conversation already exists
        2. Gather context from MCP
        3. Create conversation in Neo4j
        4. Get initial LLM response
        5. Return conversation with initial AI message
        """
        logger.info(f"Starting conversation for topic: {raw_topic}")

        # Check if active conversation already exists for this topic
        existing = await self._get_active_conversation(raw_topic)
        if existing:
            logger.info(f"Active conversation already exists: {existing['id']}")
            return {
                "success": False,
                "error": "Active conversation already exists for this topic",
                "conversation_id": existing["id"]
            }

        # Gather context from MCP
        context = await self._gather_context(raw_topic, raw_payload)

        # Include initial_suggestion in context if provided (from preview)
        if initial_suggestion:
            context["initial_suggestion"] = initial_suggestion

        # Create conversation
        conversation = SchemaConversation.create(
            raw_topic=raw_topic,
            raw_payload=raw_payload,
            created_by=created_by,
            context=context
        )

        # Format messages for LLM (initial context only, no messages yet)
        llm_messages = format_conversation_for_llm(
            raw_topic=conversation.raw_topic,
            raw_payload=conversation.raw_payload,
            context=conversation.context,
            messages=[]
        )

        # Get initial LLM response
        llm_response = await self.llm.chat_completion(llm_messages, require_json=True)

        if not llm_response:
            logger.error("LLM failed to respond for initial conversation")
            return {"success": False, "error": "LLM failed to respond"}

        # Create assistant message from response
        assistant_msg = ConversationMessage.create(
            role=MessageRole.ASSISTANT,
            content=llm_response.get("message", ""),
            draft_proposal=llm_response.get("currentProposal")
        )
        conversation.add_message(assistant_msg)
        conversation.current_proposal = llm_response.get("currentProposal")

        # Save to Neo4j
        await self._save_conversation(conversation)

        logger.info(f"Conversation started: {conversation.id}")

        return {
            "success": True,
            "conversation_id": conversation.id,
            "message": llm_response.get("message"),
            "needs_clarification": llm_response.get("needsClarification", False),
            "clarification_questions": llm_response.get("clarificationQuestions", []),
            "current_proposal": conversation.current_proposal
        }

    async def continue_conversation(
        self,
        conversation_id: str,
        user_message: str
    ) -> Dict[str, Any]:
        """
        Continue an existing conversation with user input.

        1. Load conversation from Neo4j
        2. Add user message
        3. Get LLM response with full history
        4. Update conversation
        """
        logger.info(f"Continuing conversation: {conversation_id}")

        # Load conversation
        conversation = await self._load_conversation(conversation_id)
        if not conversation:
            return {"success": False, "error": "Conversation not found"}

        if conversation.status != ConversationStatus.ACTIVE:
            return {"success": False, "error": "Conversation is not active"}

        # Add user message
        user_msg = ConversationMessage.create(
            role=MessageRole.USER,
            content=user_message
        )
        conversation.add_message(user_msg)

        # Format messages for LLM
        llm_messages = format_conversation_for_llm(
            raw_topic=conversation.raw_topic,
            raw_payload=conversation.raw_payload,
            context=conversation.context,
            messages=[m.to_dict() for m in conversation.messages]
        )

        # Get LLM response
        llm_response = await self.llm.chat_completion(llm_messages, require_json=True)

        if not llm_response:
            logger.error("LLM failed to respond")
            return {"success": False, "error": "LLM failed to respond"}

        # Add assistant message
        assistant_msg = ConversationMessage.create(
            role=MessageRole.ASSISTANT,
            content=llm_response.get("message", ""),
            draft_proposal=llm_response.get("currentProposal")
        )
        conversation.add_message(assistant_msg)
        conversation.current_proposal = llm_response.get("currentProposal")

        # Update in Neo4j
        await self._update_conversation(conversation)

        logger.info(f"Conversation continued: {conversation_id}")

        return {
            "success": True,
            "conversation_id": conversation.id,
            "message": llm_response.get("message"),
            "needs_clarification": llm_response.get("needsClarification", False),
            "clarification_questions": llm_response.get("clarificationQuestions", []),
            "current_proposal": conversation.current_proposal
        }

    async def accept_proposal(
        self,
        conversation_id: str,
        edits: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Accept the current proposal and create a SchemaMapping.

        1. Load conversation
        2. Apply any user edits to the proposal
        3. Create SchemaMapping in Neo4j
        4. Mark conversation as completed
        """
        logger.info(f"Accepting proposal for conversation: {conversation_id}")

        conversation = await self._load_conversation(conversation_id)
        if not conversation:
            return {"success": False, "error": "Conversation not found"}

        if not conversation.current_proposal:
            return {"success": False, "error": "No proposal to accept"}

        # Apply edits if provided
        proposal = conversation.current_proposal.copy()
        if edits:
            if "curatedTopic" in edits:
                proposal["suggestedFullTopicPath"] = edits["curatedTopic"]
            if "payloadMapping" in edits:
                proposal["payloadMapping"] = edits["payloadMapping"]

        # Create SchemaMapping
        mapping_id = await self._create_mapping_from_proposal(conversation, proposal)

        if not mapping_id:
            return {"success": False, "error": "Failed to create mapping"}

        # Mark conversation as completed
        conversation.status = ConversationStatus.COMPLETED
        await self._update_conversation(conversation)

        logger.info(f"Proposal accepted, mapping created: {mapping_id}")

        return {
            "success": True,
            "mapping_id": mapping_id,
            "conversation_id": conversation_id
        }

    async def get_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Get full conversation details."""
        conversation = await self._load_conversation(conversation_id)
        if not conversation:
            return {"success": False, "error": "Conversation not found"}

        return {
            "success": True,
            "conversation": conversation.to_dict()
        }

    # ========== Private Methods ==========

    async def _gather_context(
        self,
        raw_topic: str,
        raw_payload: str
    ) -> Dict[str, Any]:
        """Gather context from MCP for the conversation."""
        logger.info(f"Gathering context for: {raw_topic}")

        similar_topics = await self.mcp.similar_topics(topic=raw_topic, k=20)
        similar_messages = await self.mcp.similar_messages(
            topic=raw_topic,
            payload=raw_payload,
            k=50
        )

        root = raw_topic.split("/")[0] if raw_topic else ""
        curated_tree = await self.mcp.get_topic_tree(broker="curated", root_path=root)

        return {
            "similar_topics": similar_topics or [],
            "similar_messages": similar_messages or [],
            "curated_tree": curated_tree or {}
        }

    async def _save_conversation(self, conv: SchemaConversation) -> None:
        """Save new conversation to Neo4j."""
        query = """
        CREATE (c:SchemaConversation {
            id: $id,
            rawTopic: $rawTopic,
            rawPayload: $rawPayload,
            status: $status,
            currentProposalJson: $currentProposalJson,
            contextJson: $contextJson,
            createdAt: datetime($createdAt),
            updatedAt: datetime($updatedAt),
            createdBy: $createdBy
        })

        WITH c
        UNWIND $messages AS msg
        CREATE (m:ConversationMessage {
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: datetime(msg.timestamp),
            draftProposalJson: msg.draftProposalJson
        })
        CREATE (c)-[:HAS_MESSAGE]->(m)

        RETURN c.id AS id
        """

        async with self.driver.session() as session:
            await session.run(
                query,
                id=conv.id,
                rawTopic=conv.raw_topic,
                rawPayload=conv.raw_payload,
                status=conv.status.value,
                currentProposalJson=json.dumps(conv.current_proposal) if conv.current_proposal else None,
                contextJson=json.dumps(conv.context),
                createdAt=conv.created_at.isoformat(),
                updatedAt=conv.updated_at.isoformat(),
                createdBy=conv.created_by,
                messages=[
                    {
                        "id": m.id,
                        "role": m.role.value,
                        "content": m.content,
                        "timestamp": m.timestamp.isoformat(),
                        "draftProposalJson": json.dumps(m.draft_proposal) if m.draft_proposal else None
                    }
                    for m in conv.messages
                ]
            )

    async def _load_conversation(
        self,
        conversation_id: str
    ) -> Optional[SchemaConversation]:
        """Load conversation from Neo4j."""
        query = """
        MATCH (c:SchemaConversation {id: $id})
        OPTIONAL MATCH (c)-[:HAS_MESSAGE]->(m:ConversationMessage)
        WITH c, m ORDER BY m.timestamp
        WITH c, collect(m) AS messages
        RETURN c {
            .id, .rawTopic, .rawPayload, .status,
            .currentProposalJson, .contextJson,
            createdAt: toString(c.createdAt),
            updatedAt: toString(c.updatedAt),
            .createdBy
        } AS conv,
        [msg IN messages | {
            id: msg.id,
            role: msg.role,
            content: msg.content,
            timestamp: toString(msg.timestamp),
            draftProposalJson: msg.draftProposalJson
        }] AS messages
        """

        async with self.driver.session() as session:
            result = await session.run(query, id=conversation_id)
            record = await result.single()

            if not record:
                return None

            conv_data = dict(record["conv"])
            messages_data = record["messages"]

            messages = []
            for m in messages_data:
                if m and m.get("id"):
                    messages.append(ConversationMessage(
                        id=m["id"],
                        role=MessageRole(m["role"]),
                        content=m["content"],
                        timestamp=datetime.fromisoformat(m["timestamp"].replace("Z", "+00:00")),
                        draft_proposal=json.loads(m["draftProposalJson"]) if m.get("draftProposalJson") else None
                    ))

            return SchemaConversation(
                id=conv_data["id"],
                raw_topic=conv_data["rawTopic"],
                raw_payload=conv_data["rawPayload"],
                status=ConversationStatus(conv_data["status"]),
                messages=messages,
                current_proposal=json.loads(conv_data["currentProposalJson"]) if conv_data.get("currentProposalJson") else None,
                created_at=datetime.fromisoformat(conv_data["createdAt"].replace("Z", "+00:00")),
                updated_at=datetime.fromisoformat(conv_data["updatedAt"].replace("Z", "+00:00")),
                created_by=conv_data["createdBy"],
                context=json.loads(conv_data["contextJson"]) if conv_data.get("contextJson") else {}
            )

    async def _update_conversation(self, conv: SchemaConversation) -> None:
        """Update existing conversation in Neo4j."""
        # Update conversation node
        update_query = """
        MATCH (c:SchemaConversation {id: $id})
        SET c.status = $status,
            c.currentProposalJson = $currentProposalJson,
            c.updatedAt = datetime($updatedAt)
        """

        # Add new messages
        add_messages_query = """
        MATCH (c:SchemaConversation {id: $convId})
        UNWIND $newMessages AS msg
        MERGE (m:ConversationMessage {id: msg.id})
        ON CREATE SET
            m.role = msg.role,
            m.content = msg.content,
            m.timestamp = datetime(msg.timestamp),
            m.draftProposalJson = msg.draftProposalJson
        MERGE (c)-[:HAS_MESSAGE]->(m)
        """

        async with self.driver.session() as session:
            # Update conversation
            await session.run(
                update_query,
                id=conv.id,
                status=conv.status.value,
                currentProposalJson=json.dumps(conv.current_proposal) if conv.current_proposal else None,
                updatedAt=conv.updated_at.isoformat()
            )

            # Get existing message IDs
            existing_query = """
            MATCH (c:SchemaConversation {id: $id})-[:HAS_MESSAGE]->(m)
            RETURN collect(m.id) AS ids
            """
            result = await session.run(existing_query, id=conv.id)
            record = await result.single()
            existing_ids = set(record["ids"]) if record else set()

            # Add only new messages
            new_messages = [
                {
                    "id": m.id,
                    "role": m.role.value,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat(),
                    "draftProposalJson": json.dumps(m.draft_proposal) if m.draft_proposal else None
                }
                for m in conv.messages if m.id not in existing_ids
            ]

            if new_messages:
                await session.run(add_messages_query, convId=conv.id, newMessages=new_messages)

    async def _get_active_conversation(
        self,
        raw_topic: str
    ) -> Optional[Dict[str, str]]:
        """Check if an active conversation exists for this topic."""
        query = """
        MATCH (c:SchemaConversation {rawTopic: $topic, status: "active"})
        RETURN c.id AS id
        LIMIT 1
        """

        async with self.driver.session() as session:
            result = await session.run(query, topic=raw_topic)
            record = await result.single()
            return {"id": record["id"]} if record else None

    async def _create_mapping_from_proposal(
        self,
        conv: SchemaConversation,
        proposal: Dict[str, Any]
    ) -> Optional[str]:
        """Create a SchemaMapping from the accepted proposal."""
        mapping_id = str(uuid.uuid4())

        query = """
        // Create the mapping
        CREATE (s:SchemaMapping {
            id: $mappingId,
            rawTopic: $rawTopic,
            curatedTopic: $curatedTopic,
            payloadMappingJson: $payloadMappingJson,
            status: "proposed",
            createdAt: datetime(),
            createdBy: $createdBy,
            notes: $notes,
            confidence: $confidence,
            conversationId: $conversationId
        })

        // Link to conversation
        WITH s
        MATCH (c:SchemaConversation {id: $conversationId})
        CREATE (c)-[:PRODUCED_MAPPING]->(s)

        // Ensure topics exist
        WITH s
        MERGE (raw:Topic {path: $rawTopic, broker: "uncurated"})
        ON CREATE SET raw.createdAt = datetime()

        MERGE (cur:Topic {path: $curatedTopic, broker: "curated"})
        ON CREATE SET cur.createdAt = datetime()

        // Create relationships
        MERGE (s)-[:RAW_TOPIC]->(raw)
        MERGE (s)-[:CURATED_TOPIC]->(cur)
        MERGE (raw)-[r:ROUTES_TO]->(cur)
        SET r.mappingId = s.id, r.status = "proposed"

        RETURN s.id AS id
        """

        try:
            async with self.driver.session() as session:
                result = await session.run(
                    query,
                    mappingId=mapping_id,
                    rawTopic=conv.raw_topic,
                    curatedTopic=proposal.get("suggestedFullTopicPath"),
                    payloadMappingJson=json.dumps(proposal.get("payloadMapping", {})),
                    createdBy=conv.created_by,
                    notes=proposal.get("rationale", ""),
                    confidence=proposal.get("confidence", "medium"),
                    conversationId=conv.id
                )
                record = await result.single()
                return record["id"] if record else None
        except Exception as e:
            logger.error(f"Failed to create mapping: {e}")
            return None
