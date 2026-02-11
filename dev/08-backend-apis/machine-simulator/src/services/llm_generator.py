"""LLM-based machine generation service using OpenAI."""

import json
import logging
from typing import Optional

from openai import OpenAI

from ..config import config
from ..models import FieldDefinition, FieldType, GeneratedMachineResponse, ContextTopic
from ..prompts import (
    RANDOM_MACHINE_SYSTEM_PROMPT,
    RANDOM_MACHINE_USER_PROMPT,
    CONTEXT_AWARE_RANDOM_SYSTEM_PROMPT,
    CONTEXT_AWARE_RANDOM_USER_PROMPT,
    PROMPTED_MACHINE_SYSTEM_PROMPT,
    LADDER_GENERATION_SYSTEM_PROMPT,
    LADDER_GENERATION_USER_PROMPT,
    SMPROFILE_GENERATION_SYSTEM_PROMPT,
    SMPROFILE_GENERATION_USER_PROMPT,
)
from .machine_store import machine_store

logger = logging.getLogger(__name__)


class LLMGenerator:
    """Service for generating machine definitions using OpenAI LLM."""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        if config.openai_api_key:
            self.client = OpenAI(api_key=config.openai_api_key)
        else:
            logger.warning("No OpenAI API key configured - LLM generation disabled")

    def _parse_llm_response(
        self,
        content: str,
        context_topics: list[dict] | None = None
    ) -> GeneratedMachineResponse:
        """Parse LLM JSON response into GeneratedMachineResponse."""
        # Clean up response - remove markdown code blocks if present
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        data = json.loads(content)
        logger.info(f"Parsed LLM response: {json.dumps(data, indent=2)}")

        # Convert fields to FieldDefinition objects
        fields = []
        for f in data.get("fields", []):
            field_type = f.get("type", "string")
            # Map type string to FieldType enum
            type_map = {
                "number": FieldType.NUMBER,
                "integer": FieldType.INTEGER,
                "boolean": FieldType.BOOLEAN,
                "string": FieldType.STRING,
            }

            # Only set static_value if it's explicitly provided and not null
            # Fields with minValue/maxValue are dynamic (sensor values)
            static_val = f.get("staticValue")
            has_range = f.get("minValue") is not None or f.get("maxValue") is not None

            # If field has a range, it's dynamic - ignore any staticValue
            if has_range:
                static_val = None

            fields.append(
                FieldDefinition(
                    name=f.get("name"),
                    type=type_map.get(field_type, FieldType.STRING),
                    min_value=f.get("minValue"),
                    max_value=f.get("maxValue"),
                    static_value=static_val if static_val is not None else None,
                    description=f.get("description"),
                )
            )

        # Convert context topics to ContextTopic objects
        context_topic_objects = None
        if context_topics:
            context_topic_objects = [
                ContextTopic(
                    topic_path=t['topic_path'],
                    field_names=t['field_names'],
                    payload_preview=json.dumps(t['payload'], separators=(',', ':'))[:200]
                )
                for t in context_topics
            ]

        # Extract SparkMES structure if present
        sparkmes = data.get("SparkMES")
        if sparkmes:
            logger.info(f"SparkMES structure found with {len(sparkmes.get('tags', []))} top-level tags")

        return GeneratedMachineResponse(
            machine_type=data.get("machineType", "Unknown"),
            suggested_name=data.get("suggestedName", "machine-001"),
            description=data.get("description"),
            topic_path=data.get("topicPath"),  # None - will be set during Connect flow
            fields=fields,
            publish_interval_ms=data.get("publishIntervalMs", 5000),
            context_topics=context_topic_objects,
            sparkmes=sparkmes,
        )

    def _format_context_for_prompt(self, context_topics: list[dict]) -> str:
        """Format context topics into a string for the LLM prompt."""
        lines = []
        for i, topic in enumerate(context_topics, 1):
            lines.append(f"{i}. Topic: {topic['topic_path']}")
            lines.append(f"   Fields: {', '.join(topic['field_names'])}")

            # Include sample payload values (truncated for readability)
            payload_preview = json.dumps(topic['payload'], separators=(',', ':'))
            if len(payload_preview) > 500:
                payload_preview = payload_preview[:500] + "..."
            lines.append(f"   Sample payload: {payload_preview}")
            lines.append("")

        return "\n".join(lines)

    def _format_existing_machines(self, machines: list[dict]) -> str:
        """Format existing machines list for the LLM prompt."""
        if not machines:
            return "EXISTING MACHINES: None yet - you are creating the first machine!"

        lines = ["EXISTING MACHINES (you MUST NOT duplicate these names or types):"]
        for m in machines:
            lines.append(f"- {m['name']} ({m['machine_type']})")

        return "\n".join(lines)

    async def generate_random(self) -> GeneratedMachineResponse:
        """Generate a random machine definition using LLM with knowledge graph context."""
        if not self.client:
            raise RuntimeError("LLM client not configured - missing API key")

        logger.info("Generating random machine definition...")

        # Try to get context from knowledge graph
        context_topics = []
        try:
            context_topics = await machine_store.get_random_topic_context(limit=10)
            logger.info(f"Retrieved {len(context_topics)} topics for context")
        except Exception as e:
            logger.warning(f"Failed to get context from Neo4j: {e}")

        # Get existing machines to avoid duplicates
        existing_machines = []
        try:
            existing_machines = await machine_store.get_machine_summary()
            logger.info(f"Found {len(existing_machines)} existing machines to avoid duplicating")
        except Exception as e:
            logger.warning(f"Failed to get existing machines: {e}")

        # Choose prompts based on whether we have context
        if context_topics:
            # Build context section for prompt
            context_section = self._format_context_for_prompt(context_topics)
            existing_machines_section = self._format_existing_machines(existing_machines)

            system_prompt = CONTEXT_AWARE_RANDOM_SYSTEM_PROMPT
            user_prompt = CONTEXT_AWARE_RANDOM_USER_PROMPT.format(
                count=len(context_topics),
                context_section=context_section,
                existing_machines_section=existing_machines_section
            )
            logger.info("Using context-aware prompts for generation")
        else:
            # Fall back to original prompts if no context available
            # Still include existing machines to prevent duplicates
            system_prompt = RANDOM_MACHINE_SYSTEM_PROMPT
            existing_machines_section = self._format_existing_machines(existing_machines)
            user_prompt = f"{existing_machines_section}\n\n{RANDOM_MACHINE_USER_PROMPT}"
            logger.info(f"No context available, using standard prompts with {len(existing_machines)} existing machines")

        response = self.client.chat.completions.create(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        logger.debug(f"LLM response: {content}")

        # Pass context_topics to include them in the response
        return self._parse_llm_response(content, context_topics=context_topics if context_topics else None)

    async def generate_from_prompt(self, user_prompt: str) -> GeneratedMachineResponse:
        """Generate a machine definition based on user's description."""
        if not self.client:
            raise RuntimeError("LLM client not configured - missing API key")

        logger.info(f"Generating machine from prompt: {user_prompt[:100]}...")

        # Get existing machines to avoid duplicates
        existing_machines = []
        try:
            existing_machines = await machine_store.get_machine_summary()
            logger.info(f"Found {len(existing_machines)} existing machines to avoid duplicating")
        except Exception as e:
            logger.warning(f"Failed to get existing machines: {e}")

        existing_machines_section = self._format_existing_machines(existing_machines)

        response = self.client.chat.completions.create(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            messages=[
                {
                    "role": "system",
                    "content": PROMPTED_MACHINE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": f"{existing_machines_section}\n\nCreate a machine definition for: {user_prompt}\n\nIMPORTANT: The suggested name MUST be unique and MUST NOT match any existing machine name listed above.",
                }
            ],
        )

        content = response.choices[0].message.content
        logger.debug(f"LLM response: {content}")

        return self._parse_llm_response(content)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 1024,
    ) -> str:
        """Generic LLM generation with custom prompts. Returns raw string response."""
        if not self.client:
            raise RuntimeError("LLM client not configured - missing API key")

        logger.info(f"Generating with custom prompt...")
        logger.debug(f"System prompt: {system_prompt[:200]}...")
        logger.debug(f"User prompt: {user_prompt[:200]}...")

        response = self.client.chat.completions.create(
            model=config.llm_model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        logger.info(f"LLM raw response: {content}")
        return content

    def _format_fields_for_ladder_prompt(self, fields: list[FieldDefinition]) -> str:
        """Format machine fields for the ladder generation prompt."""
        # DEBUG: Log input fields
        logger.info(f"[Ladder] ========== FORMATTING FIELDS FOR PROMPT ==========")
        logger.info(f"[Ladder] Received {len(fields)} fields:")
        for f in fields:
            logger.info(f"[Ladder]   - name='{f.name}', type={f.type.value}, min={f.min_value}, max={f.max_value}")

        lines = []
        for f in fields:
            field_info = f"- {f.name} ({f.type.value})"
            if f.min_value is not None or f.max_value is not None:
                field_info += f" [range: {f.min_value or '?'} - {f.max_value or '?'}]"
            if f.description:
                field_info += f" - {f.description}"
            lines.append(field_info)

        result = "\n".join(lines) if lines else "No fields defined"
        logger.info(f"[Ladder] Formatted fields section:\n{result}")
        logger.info(f"[Ladder] =====================================================")
        return result

    def _format_formulas_for_ladder_prompt(self, fields: list[FieldDefinition]) -> str:
        """Format field formulas for the ladder generation prompt.

        This helps the LLM understand how each field should behave so it can
        generate ladder logic that mirrors the simulation formulas.
        """
        lines = []
        for f in fields:
            if f.formula:
                formula_info = f"- {f.name}: formula=\"{f.formula}\""
                if f.min_value is not None and f.max_value is not None:
                    formula_info += f" (expected range: {f.min_value} to {f.max_value})"
                lines.append(formula_info)
            elif f.static_value is not None:
                lines.append(f"- {f.name}: static value = {f.static_value}")
            else:
                # No formula or static value - describe expected behavior based on type
                if f.type.value == "boolean":
                    lines.append(f"- {f.name}: boolean field (should toggle TRUE/FALSE)")
                elif f.type.value == "integer":
                    if "count" in f.name.lower():
                        lines.append(f"- {f.name}: counter field (should increment)")
                    else:
                        range_str = ""
                        if f.min_value is not None and f.max_value is not None:
                            range_str = f" in range {f.min_value}-{f.max_value}"
                        lines.append(f"- {f.name}: integer field{range_str}")
                elif f.type.value == "number":
                    range_str = ""
                    if f.min_value is not None and f.max_value is not None:
                        range_str = f" in range {f.min_value}-{f.max_value}"
                    lines.append(f"- {f.name}: numeric field (should oscillate{range_str})")
                else:
                    lines.append(f"- {f.name}: {f.type.value} field")

        return "\n".join(lines) if lines else "No formulas defined - use default behavior for each field type"

    def _clean_json_response(self, content: str) -> str:
        """Clean markdown formatting from LLM JSON response."""
        content = content.strip()

        # Remove markdown code blocks
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        # Try to extract JSON object if there's extra text before/after
        content = content.strip()
        start = content.find('{')
        end = content.rfind('}')
        if start != -1 and end != -1 and end > start:
            content = content[start:end+1]

        return content.strip()

    async def generate_ladder(
        self,
        machine_type: str,
        fields: list[FieldDefinition],
        description: Optional[str] = None,
    ) -> dict:
        """Generate ladder logic for a machine based on its type and fields.

        Args:
            machine_type: Type of machine (e.g., "Conveyor Belt", "CNC Mill")
            fields: List of FieldDefinition objects representing machine I/O
            description: Optional description of the machine

        Returns:
            Dictionary with ladder_program, io_mapping, and rationale
        """
        if not self.client:
            raise RuntimeError("LLM client not configured - missing API key")

        logger.info(f"[Ladder] ========== GENERATE LADDER CALLED ==========")
        logger.info(f"[Ladder] machine_type: {machine_type}")
        logger.info(f"[Ladder] description: {description}")
        logger.info(f"[Ladder] fields count: {len(fields)}")
        logger.info(f"[Ladder] field names: {[f.name for f in fields]}")

        fields_section = self._format_fields_for_ladder_prompt(fields)
        formulas_section = self._format_formulas_for_ladder_prompt(fields)

        user_prompt = LADDER_GENERATION_USER_PROMPT.format(
            machine_type=machine_type,
            description=description or f"A {machine_type} machine",
            fields_section=fields_section,
            formulas_section=formulas_section,
        )

        # DEBUG: Log the full prompts being sent to LLM
        logger.info(f"[Ladder] ========== FULL USER PROMPT ==========")
        logger.info(f"[Ladder] {user_prompt}")
        logger.info(f"[Ladder] ========================================")

        response = self.client.chat.completions.create(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            messages=[
                {"role": "system", "content": LADDER_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content

        # DEBUG: Log the full LLM response
        logger.info(f"[Ladder] ========== FULL LLM RESPONSE ==========")
        logger.info(f"[Ladder] {content}")
        logger.info(f"[Ladder] ==========================================")

        # Parse and return the JSON response
        clean_content = self._clean_json_response(content)
        try:
            data = json.loads(clean_content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            logger.error(f"Raw LLM response (first 1000 chars): {content[:1000]}")
            logger.error(f"Cleaned response (first 1000 chars): {clean_content[:1000]}")
            raise

        # DEBUG: Log the parsed response
        logger.info(f"[Ladder] ========== PARSED RESPONSE ==========")
        logger.info(f"[Ladder] rungs count: {len(data.get('ladder_program', {}).get('rungs', []))}")
        logger.info(f"[Ladder] io_mapping.inputs: {data.get('io_mapping', {}).get('inputs', [])}")
        logger.info(f"[Ladder] io_mapping.outputs: {data.get('io_mapping', {}).get('outputs', [])}")
        logger.info(f"[Ladder] rationale: {data.get('rationale', 'N/A')[:200]}")
        logger.info(f"[Ladder] =========================================")

        return data

    async def generate_smprofile(
        self,
        machine_type: str,
        machine_name: str,
        description: Optional[str] = None,
    ) -> dict:
        """Generate a CESMII SM Profile (Machine Identification) for a machine.

        Args:
            machine_type: Type of machine (e.g., "CNC Mill", "Conveyor Belt")
            machine_name: Name of the machine
            description: Optional description of the machine

        Returns:
            Dictionary containing the SM Profile payload
        """
        if not self.client:
            raise RuntimeError("LLM client not configured - missing API key")

        logger.info(f"Generating SM Profile for {machine_type}: {machine_name}")

        user_prompt = SMPROFILE_GENERATION_USER_PROMPT.format(
            machine_type=machine_type,
            machine_name=machine_name,
            description=description or f"A {machine_type} machine",
        )

        response = self.client.chat.completions.create(
            model=config.llm_model,
            max_tokens=config.llm_max_tokens,
            messages=[
                {"role": "system", "content": SMPROFILE_GENERATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content
        logger.info(f"SM Profile LLM response: {content}")

        clean_content = self._clean_json_response(content)
        try:
            data = json.loads(clean_content)
        except json.JSONDecodeError as e:
            logger.error(f"SM Profile JSON parse error: {e}")
            raise

        logger.info(f"Generated SM Profile with manufacturer: {data.get('manufacturer')}")
        return data


# Singleton instance
llm_generator = LLMGenerator()
