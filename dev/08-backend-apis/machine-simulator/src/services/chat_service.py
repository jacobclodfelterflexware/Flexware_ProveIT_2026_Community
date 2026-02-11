"""Chat service for machine-specific conversations with OpenAI streaming."""

import json
import logging
from typing import AsyncIterator, Optional

from openai import OpenAI

from ..config import config
from ..prompts import MACHINE_CHAT_SYSTEM_PROMPT, build_machine_chat_user_prompt

logger = logging.getLogger(__name__)


class ChatService:
    """Service for handling machine chat conversations with OpenAI."""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        if config.openai_api_key:
            self.client = OpenAI(api_key=config.openai_api_key)
        else:
            logger.warning("No OpenAI API key configured - chat service disabled")

    def _format_field_definitions(self, fields: list[dict]) -> str:
        """Format field definitions for the prompt."""
        if not fields:
            return "No fields defined"

        lines = []
        for f in fields:
            field_info = f"- **{f.get('name', 'unnamed')}** ({f.get('type', 'unknown')})"
            min_val = f.get('min_value')
            max_val = f.get('max_value')
            if min_val is not None or max_val is not None:
                field_info += f" [range: {min_val or '?'} - {max_val or '?'}]"
            desc = f.get('description')
            if desc:
                field_info += f" - {desc}"
            lines.append(field_info)
        return "\n".join(lines)

    def _format_historical_messages(self, messages: list[dict], max_messages: int = 20) -> str:
        """Format historical messages for the prompt context."""
        if not messages:
            return "No historical messages available"

        lines = []
        for msg in messages[:max_messages]:
            timestamp = msg.get('timestamp', 'unknown time')
            topic = msg.get('topic', 'unknown topic')
            lines.append(f"[{timestamp}] {topic}")

            # Truncate large payloads
            payload = msg.get('payload', {})
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    pass

            payload_str = json.dumps(payload, separators=(',', ':')) if isinstance(payload, dict) else str(payload)
            if len(payload_str) > 500:
                payload_str = payload_str[:500] + "..."
            lines.append(f"  Payload: {payload_str}")

        return "\n".join(lines)

    def _format_similarity_results(self, results: list[dict], max_results: int = 10) -> str:
        """Format similarity results for the prompt context."""
        if not results:
            return "No similarity context available"

        lines = []
        for i, result in enumerate(results[:max_results], 1):
            topic_path = result.get('topic_path', 'unknown')
            similarity = result.get('similarity', 0)
            lines.append(f"{i}. Topic: {topic_path} (similarity: {similarity:.2f})")

            payloads = result.get('historical_payloads', [])
            if payloads:
                payload = payloads[0].get('payload', {})
                payload_str = json.dumps(payload, separators=(',', ':'))[:200]
                lines.append(f"   Sample: {payload_str}")

        return "\n".join(lines)

    def _format_rag_results(self, results: list[dict], max_results: int = 10) -> str:
        """Format RAG similarity results for the prompt context."""
        if not results:
            return ""

        lines = []
        for i, result in enumerate(results[:max_results], 1):
            topic_path = result.get('topic_path', 'unknown')
            similarity = result.get('similarity', 0)
            lines.append(f"{i}. Topic: {topic_path} (similarity: {similarity:.2f})")

            payloads = result.get('historical_payloads', [])
            if payloads:
                payload = payloads[0].get('payload', {})
                payload_str = json.dumps(payload, separators=(',', ':'))[:200]
                lines.append(f"   Sample: {payload_str}")

        return "\n".join(lines)

    def _format_conversation_history(self, history: list[dict]) -> str:
        """Format conversation history for the prompt."""
        if not history:
            return "No previous conversation"

        lines = []
        # Take last 5 exchanges (10 messages)
        for msg in history[-10:]:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            if role == 'user':
                lines.append(f"User: {content}")
            elif role == 'assistant':
                lines.append(f"Assistant: {content}")

        return "\n".join(lines)

    def _format_predictions(self, prediction: dict) -> str:
        """Format time series prediction data for the prompt."""
        if not prediction:
            return ""

        lines = []
        field = prediction.get('field', 'unknown')
        topic = prediction.get('topic', 'unknown')
        horizon = prediction.get('horizon', 'unknown')
        data_points = prediction.get('dataPointsUsed', 0)

        lines.append(f"Field: **{field}** on topic `{topic}`")
        lines.append(f"Forecast horizon: {horizon}")
        lines.append(f"Model trained on {data_points} data points")

        # Metrics
        metrics = prediction.get('metrics', {})
        rmse = metrics.get('rmse')
        mae = metrics.get('mae')
        mape = metrics.get('mape')
        metrics_parts = []
        if rmse is not None:
            metrics_parts.append(f"RMSE: {rmse:.4f}")
        if mae is not None:
            metrics_parts.append(f"MAE: {mae:.4f}")
        if mape is not None:
            metrics_parts.append(f"MAPE: {mape:.2f}%")
        if metrics_parts:
            lines.append(f"Model accuracy: {', '.join(metrics_parts)}")

        # Predictions (show next 5)
        predictions = prediction.get('predictions', [])
        if predictions:
            lines.append("\nForecast values:")
            for pred in predictions[:5]:
                date = pred.get('date', 'unknown')
                value = pred.get('value', 0)
                lower = pred.get('lower', 0)
                upper = pred.get('upper', 0)
                lines.append(f"  - {date}: {value:.2f} (95% CI: {lower:.2f} - {upper:.2f})")
            if len(predictions) > 5:
                lines.append(f"  ... and {len(predictions) - 5} more predictions")

        return "\n".join(lines)

    def _format_regression(self, regression: dict) -> str:
        """Format linear regression analysis data for the prompt."""
        if not regression:
            return ""

        lines = []
        target_field = regression.get('targetField', 'unknown')
        target_topic = regression.get('targetTopic', 'unknown')
        r_squared = regression.get('rSquared', 0)
        intercept = regression.get('intercept', 0)
        data_points = regression.get('dataPointsUsed', 0)

        lines.append(f"Target: **{target_field}** on topic `{target_topic}`")
        lines.append(f"Model R² (goodness of fit): {r_squared:.4f} ({r_squared*100:.1f}% variance explained)")
        lines.append(f"Intercept: {intercept:.4f}")
        lines.append(f"Trained on {data_points} data points")

        # Feature coefficients
        features = regression.get('features', [])
        if features:
            lines.append("\nFeature coefficients (influence on target):")
            for f in features[:10]:
                feat_field = f.get('field', 'unknown')
                feat_topic = f.get('topic', '')
                coef = f.get('coefficient', 0)
                p_value = f.get('pValue')
                significance = ""
                if p_value is not None:
                    if p_value < 0.001:
                        significance = " ***"
                    elif p_value < 0.01:
                        significance = " **"
                    elif p_value < 0.05:
                        significance = " *"
                lines.append(f"  - {feat_field}: {coef:+.4f}{significance}")
            if len(features) > 10:
                lines.append(f"  ... and {len(features) - 10} more features")

        return "\n".join(lines)

    def _build_messages(
        self,
        machine_context: dict,
        historical_context: dict,
        rag_context: Optional[dict],
        ml_context: Optional[dict],
        conversation_history: list[dict],
        user_message: str,
    ) -> list[dict]:
        """Build the messages array for OpenAI API."""
        # Extract machine info
        machine = machine_context
        topics = machine.get('topics', [])
        if not topics and machine.get('topic_path'):
            topics = [{'topic_path': machine.get('topic_path'), 'fields': machine.get('fields', [])}]

        topic_list = ', '.join(t.get('topic_path', '') for t in topics) if topics else 'No topics'

        # Flatten fields from all topics
        all_fields = []
        for t in topics:
            all_fields.extend(t.get('fields', []))
        if not all_fields:
            all_fields = machine.get('fields', [])

        # Extract historical context
        hist = historical_context or {}
        recent_messages = hist.get('recent_messages', [])
        graph_rels = hist.get('graph_relationships', {})

        # Extract RAG context
        rag_query = None
        rag_results = []
        if rag_context:
            rag_query = rag_context.get('query')
            rag_results = rag_context.get('similar_topics', [])

        # Extract ML context
        ml_predictions = None
        ml_regression = None
        if ml_context:
            prediction = ml_context.get('prediction')
            regression = ml_context.get('regression')
            if prediction:
                ml_predictions = self._format_predictions(prediction)
            if regression:
                ml_regression = self._format_regression(regression)

        # Build the user prompt
        user_prompt = build_machine_chat_user_prompt(
            machine_name=machine.get('name', 'Unknown'),
            machine_type=machine.get('machine_type', 'Unknown'),
            description=machine.get('description'),
            status=machine.get('status', 'unknown'),
            publish_interval_ms=machine.get('publish_interval_ms', 5000),
            topic_list=topic_list,
            field_definitions=self._format_field_definitions(all_fields),
            historical_messages=self._format_historical_messages(recent_messages),
            message_count=len(recent_messages),
            parent_topics=', '.join(graph_rels.get('parent_topics', [])) or 'None',
            child_topics=', '.join(graph_rels.get('child_topics', [])) or 'None',
            similarity_results=self._format_similarity_results(machine.get('similarity_results', [])),
            rag_query=rag_query,
            rag_count=len(rag_results),
            rag_results=self._format_rag_results(rag_results),
            ml_predictions=ml_predictions,
            ml_regression=ml_regression,
            conversation_history=self._format_conversation_history(conversation_history),
            user_message=user_message,
        )

        return [
            {"role": "system", "content": MACHINE_CHAT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

    async def chat_stream(
        self,
        machine_context: dict,
        historical_context: dict,
        rag_context: Optional[dict],
        ml_context: Optional[dict],
        conversation_history: list[dict],
        user_message: str,
    ) -> AsyncIterator[str]:
        """Stream chat response from OpenAI."""
        if not self.client:
            raise RuntimeError("Chat client not configured - missing API key")

        messages = self._build_messages(
            machine_context=machine_context,
            historical_context=historical_context,
            rag_context=rag_context,
            ml_context=ml_context,
            conversation_history=conversation_history,
            user_message=user_message,
        )

        logger.info(f"Sending chat request with {len(messages)} messages")
        logger.debug(f"User prompt length: {len(messages[-1]['content'])} chars")

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
            logger.error(f"Error in chat stream: {e}")
            raise

    async def chat(
        self,
        machine_context: dict,
        historical_context: dict,
        rag_context: Optional[dict],
        ml_context: Optional[dict],
        conversation_history: list[dict],
        user_message: str,
    ) -> str:
        """Non-streaming chat response from OpenAI."""
        if not self.client:
            raise RuntimeError("Chat client not configured - missing API key")

        messages = self._build_messages(
            machine_context=machine_context,
            historical_context=historical_context,
            rag_context=rag_context,
            ml_context=ml_context,
            conversation_history=conversation_history,
            user_message=user_message,
        )

        logger.info(f"Sending chat request with {len(messages)} messages")

        response = self.client.chat.completions.create(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            messages=messages,
        )

        return response.choices[0].message.content


# Singleton instance
chat_service = ChatService()
