"""Knowledge base chat service for ProveITGPT conversations with OpenAI streaming."""

import json
import logging
from typing import AsyncIterator, Optional

from openai import OpenAI

from ..config import config
from ..prompts.knowledge_base_chat import KB_CHAT_SYSTEM_PROMPT, build_kb_user_prompt

logger = logging.getLogger(__name__)


class KBChatService:
    """Service for handling knowledge base chat conversations with OpenAI."""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        if config.openai_api_key:
            self.client = OpenAI(api_key=config.openai_api_key)
        else:
            logger.warning("No OpenAI API key configured - KB chat service disabled")

    def _format_rag_results(self, results: list[dict], max_results: int = 15) -> str:
        """Format RAG similarity results for the prompt context."""
        if not results:
            return "No similar topics found for this query."

        lines = []
        for i, result in enumerate(results[:max_results], 1):
            topic_path = result.get('topic_path', 'unknown')
            similarity = result.get('similarity', 0)
            lines.append(f"{i}. Topic: `{topic_path}` (similarity: {similarity:.2f})")

            payloads = result.get('historical_payloads', [])
            if payloads:
                payload = payloads[0].get('payload', {})
                payload_str = json.dumps(payload, separators=(',', ':'))[:300]
                lines.append(f"   Sample payload: {payload_str}")

        return "\n".join(lines)

    def _format_graph_summary(self, summary: Optional[dict]) -> str:
        """Format high-level graph stats for the prompt context."""
        if not summary:
            return "Graph summary not available."

        lines = []

        topics = summary.get('topics', {})
        total_topics = topics.get('total', 0)
        by_broker = topics.get('byBroker', {})
        lines.append(f"- **Total topics**: {total_topics}")
        if by_broker:
            broker_parts = [f"{broker}: {count}" for broker, count in by_broker.items()]
            lines.append(f"- **By broker**: {', '.join(broker_parts)}")

        messages = summary.get('messages', {})
        total_messages = messages.get('total', 0)
        lines.append(f"- **Total messages**: {total_messages}")

        top_segments = summary.get('topSegments', [])
        if top_segments:
            lines.append(f"- **Top-level segments**: {', '.join(top_segments)}")

        return "\n".join(lines)

    def _format_conversation_history(self, history: list[dict]) -> str:
        """Format conversation history for the prompt."""
        if not history:
            return "No previous conversation"

        lines = []
        for msg in history[-10:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                lines.append(f"User: {content}")
            elif role == 'assistant':
                # Truncate long assistant responses in history
                if len(content) > 500:
                    content = content[:500] + "..."
                lines.append(f"Assistant: {content}")

        return "\n".join(lines)

    def _build_messages(
        self,
        graph_summary: Optional[dict],
        rag_context: Optional[dict],
        conversation_history: list[dict],
        user_message: str,
    ) -> list[dict]:
        """Build the messages array for OpenAI API."""
        # Format graph summary
        summary_str = self._format_graph_summary(graph_summary)

        # Extract RAG context
        rag_query = None
        rag_results = []
        if rag_context:
            rag_query = rag_context.get('query')
            rag_results = rag_context.get('similar_topics', [])

        # Build the user prompt
        user_prompt = build_kb_user_prompt(
            graph_summary=summary_str,
            rag_results=self._format_rag_results(rag_results),
            rag_query=rag_query,
            rag_count=len(rag_results),
            conversation_history=self._format_conversation_history(conversation_history),
            user_message=user_message,
        )

        return [
            {"role": "system", "content": KB_CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    async def chat_stream(
        self,
        graph_summary: Optional[dict],
        rag_context: Optional[dict],
        conversation_history: list[dict],
        user_message: str,
    ) -> AsyncIterator[str]:
        """Stream chat response from OpenAI."""
        if not self.client:
            raise RuntimeError("Chat client not configured - missing API key")

        messages = self._build_messages(
            graph_summary=graph_summary,
            rag_context=rag_context,
            conversation_history=conversation_history,
            user_message=user_message,
        )

        logger.info(f"[ProveITGPT] Sending KB chat request with {len(messages)} messages")
        logger.debug(f"[ProveITGPT] User prompt length: {len(messages[-1]['content'])} chars")

        try:
            response = self.client.chat.completions.create(
                model=config.llm_model,
                max_tokens=config.llm_max_tokens,
                messages=messages,
                stream=True,
            )

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"[ProveITGPT] Error in chat stream: {e}")
            raise

    async def chat(
        self,
        graph_summary: Optional[dict],
        rag_context: Optional[dict],
        conversation_history: list[dict],
        user_message: str,
    ) -> str:
        """Non-streaming chat response from OpenAI."""
        if not self.client:
            raise RuntimeError("Chat client not configured - missing API key")

        messages = self._build_messages(
            graph_summary=graph_summary,
            rag_context=rag_context,
            conversation_history=conversation_history,
            user_message=user_message,
        )

        logger.info(f"[ProveITGPT] Sending KB chat request with {len(messages)} messages")

        response = self.client.chat.completions.create(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            messages=messages,
        )

        return response.choices[0].message.content


# Singleton instance
kb_chat_service = KBChatService()
