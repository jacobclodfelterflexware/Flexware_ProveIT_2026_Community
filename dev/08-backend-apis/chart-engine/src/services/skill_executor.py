import logging
from dataclasses import dataclass, field
from typing import Optional
import jsonschema
from neo4j import AsyncGraphDatabase

from api.models import RAGContext, ChartConfig
from skills.registry import SkillRegistry
from skills.base import ChartSkill, ChartResult

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of parameter validation."""
    valid: bool
    errors: list[str] = field(default_factory=list)
    sanitized_parameters: Optional[dict] = None


@dataclass
class ExecutionResult:
    """Result of skill execution."""
    chart_config: ChartConfig
    initial_data: dict
    subscriptions: list[str] = field(default_factory=list)


class SkillExecutor:
    """
    Executes chart skills by:
    1. Validating parameters against skill schema
    2. Running parameterized Cypher queries
    3. Building chart configurations
    """

    def __init__(
        self,
        registry: SkillRegistry,
        neo4j_uri: str,
        neo4j_user: str,
        neo4j_password: str
    ):
        self.registry = registry
        self.driver = AsyncGraphDatabase.driver(
            neo4j_uri,
            auth=(neo4j_user, neo4j_password)
        )

    async def close(self):
        """Close the Neo4j driver."""
        await self.driver.close()

    def validate_parameters(
        self,
        skill_id: str,
        parameters: dict,
        rag_context: Optional[RAGContext] = None
    ) -> ValidationResult:
        """
        Validate parameters against skill schema.

        Performs:
        1. Schema validation (JSON Schema)
        2. Semantic validation (topics/fields exist in RAG context)
        3. Safety sanitization
        """
        errors = []

        # Get skill
        skill = self.registry.get_skill(skill_id)
        if not skill:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown skill: {skill_id}"]
            )

        # Stage 1: JSON Schema validation
        try:
            jsonschema.validate(parameters, skill.parameters_schema)
        except jsonschema.ValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
            return ValidationResult(valid=False, errors=errors)

        # Stage 2: Semantic validation (if RAG context provided)
        if rag_context:
            available_topics = set()
            available_fields = set(rag_context.available_fields)

            for topic in rag_context.matching_topics:
                path = topic.get("path", topic.get("topic", ""))
                if path:
                    available_topics.add(path)

            # Check topics
            param_topics = []
            for key in ["topics", "topic", "x_topic", "y_topic", "left_topics", "right_topics"]:
                val = parameters.get(key)
                if isinstance(val, list):
                    param_topics.extend(val)
                elif isinstance(val, str):
                    param_topics.append(val)

            for topic in param_topics:
                if topic and topic not in available_topics:
                    # Warn but don't fail - topic might be a partial match
                    logger.warning(f"Topic '{topic}' not in RAG context")

            # Check fields
            param_fields = []
            for key in ["fields", "field", "x_field", "y_field", "left_field", "right_field"]:
                val = parameters.get(key)
                if isinstance(val, list):
                    param_fields.extend(val)
                elif isinstance(val, str):
                    param_fields.append(val)

            for field_name in param_fields:
                if field_name and available_fields and field_name not in available_fields:
                    # Warn but don't fail
                    logger.warning(f"Field '{field_name}' not in RAG context")

        # Stage 3: Sanitization
        sanitized = self._sanitize_parameters(parameters)

        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            sanitized_parameters=sanitized
        )

    def _sanitize_parameters(self, params: dict) -> dict:
        """
        Sanitize parameters to prevent injection attacks.
        """
        sanitized = {}

        for key, value in params.items():
            if isinstance(value, str):
                # Remove potential Cypher injection patterns
                sanitized[key] = self._sanitize_string(value)
            elif isinstance(value, list):
                sanitized[key] = [
                    self._sanitize_string(v) if isinstance(v, str) else v
                    for v in value
                ]
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_parameters(value)
            else:
                sanitized[key] = value

        return sanitized

    def _sanitize_string(self, value: str) -> str:
        """Sanitize a string value."""
        # Remove semicolons and dangerous patterns
        dangerous_patterns = [";", "//", "/*", "*/", "DETACH", "DELETE", "DROP", "CREATE", "MERGE"]
        result = value
        for pattern in dangerous_patterns:
            result = result.replace(pattern, "")
        return result.strip()

    async def execute(
        self,
        skill_id: str,
        parameters: dict,
        chart_id: str
    ) -> ExecutionResult:
        """
        Execute a skill and return chart configuration.
        """
        skill = self.registry.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Unknown skill: {skill_id}")

        # Build and execute query
        query, query_params = skill.build_cypher_query(parameters)

        async with self.driver.session() as session:
            result = await session.run(query, query_params)
            records = await result.data()

        # Build chart config
        chart_config_dict = skill.build_chart_config(records, parameters)

        # Build subscriptions for streaming
        subscriptions = []
        if skill.supports_streaming:
            subscriptions = skill.build_subscriptions(parameters)

        # Convert to ChartConfig model
        chart_config = ChartConfig(
            type=chart_config_dict.get("type", skill.chart_type),
            data=chart_config_dict.get("data", {}),
            options=chart_config_dict.get("options", {})
        )

        # Extract sample values from first few records
        sample_values = []
        if records:
            # Get fields from parameters
            fields = parameters.get("fields", [parameters.get("field", "value")])
            if isinstance(fields, str):
                fields = [fields]
            primary_field = fields[0] if fields else "value"

            for record in records[:5]:
                topic = record.get("topic", "unknown")
                # Try to get value from numericValue, then from payload
                value = record.get("numericValue")
                if value is None:
                    payload = record.get("payload", {})
                    if isinstance(payload, dict):
                        value = payload.get(primary_field)
                sample_values.append({"topic": topic, "value": value})

        return ExecutionResult(
            chart_config=chart_config,
            initial_data={
                "records": len(records),
                "chart_id": chart_id,
                "sample_values": sample_values
            },
            subscriptions=subscriptions
        )
