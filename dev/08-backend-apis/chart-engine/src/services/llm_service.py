import json
import logging
from typing import Optional
from openai import AsyncOpenAI

from api.models import RAGContext, ChartPreferences, SkillParameters

logger = logging.getLogger(__name__)


class LLMService:
    """
    LLM orchestration service for skill selection and parameter generation.
    """

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def select_skill_and_params(
        self,
        query: str,
        rag_context: RAGContext,
        available_skills: list[dict],
        preferences: Optional[ChartPreferences] = None
    ) -> SkillParameters:
        """
        Use LLM to select the best skill and generate parameters.

        Args:
            query: User's natural language request
            rag_context: Retrieved context from RAG
            available_skills: List of skill summaries with schemas
            preferences: Optional user preferences

        Returns:
            SkillParameters with skill_id, parameters, and reasoning
        """
        system_prompt = self._build_system_prompt(available_skills)
        user_prompt = self._build_user_prompt(query, rag_context, preferences)

        try:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,  # Low temperature for consistent structured output
                )
            except Exception as json_mode_err:
                # Retry without response_format for models that don't support JSON mode
                logger.warning(f"JSON mode failed ({json_mode_err}), retrying without response_format")
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.1,
                )

            content = response.choices[0].message.content
            result = json.loads(content)

            return SkillParameters(
                skill_id=result.get("skill_id"),
                parameters=result.get("parameters", {}),
                reasoning=result.get("reasoning")
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response: {e}")
            # Fallback to a default skill
            return self._fallback_selection(query, rag_context)

        except Exception as e:
            logger.error(f"LLM error: {e}")
            return self._fallback_selection(query, rag_context)

    def _build_system_prompt(self, available_skills: list[dict]) -> str:
        """Build the system prompt with skill definitions."""
        skills_json = json.dumps(available_skills, indent=2)

        return f"""You are a chart generation assistant. Given a user's request and available data context, select the most appropriate chart skill and generate valid parameters.

## Available Skills
{skills_json}

## Rules
1. ONLY reference topics and fields that exist in the "Available Data" section
2. Your output MUST be valid JSON matching the selected skill's parameter schema
3. If multiple skills could work, prefer the one that best matches the user's intent
4. For time series data, prefer line charts unless the user asks for something specific
5. For comparisons between two variables, prefer scatter plots
6. For current values or status, prefer gauges or KPI cards
7. If the request is ambiguous and you cannot determine a good chart, use skill_id "clarification_needed"

## Output Format
Always respond with a JSON object in this exact format:
{{
    "skill_id": "the_skill_id",
    "parameters": {{
        // parameters matching the skill's schema
    }},
    "reasoning": "Brief explanation of why this skill and these parameters were chosen"
}}"""

    def _build_user_prompt(
        self,
        query: str,
        rag_context: RAGContext,
        preferences: Optional[ChartPreferences] = None
    ) -> str:
        """Build the user prompt with RAG context."""
        # Format matching topics
        topics_info = []
        for topic in rag_context.matching_topics[:10]:  # Limit to top 10
            path = topic.get("path", topic.get("topic", "unknown"))
            similarity = topic.get("similarity", topic.get("score", 0))
            fields = topic.get("available_fields", [])
            topics_info.append({
                "path": path,
                "similarity": round(similarity, 3) if isinstance(similarity, float) else similarity,
                "available_fields": fields,
                "data_type": topic.get("data_type", "unknown")
            })

        context = {
            "matching_topics": topics_info,
            "topic_hierarchy": rag_context.topic_hierarchy,
            "available_fields": rag_context.available_fields,
            "time_range": rag_context.time_range_available
        }

        prompt = f"""## User Request
"{query}"

## Available Data (from knowledge graph)
{json.dumps(context, indent=2)}
"""

        if preferences:
            pref_dict = {}
            if preferences.chart_types:
                pref_dict["preferred_chart_types"] = preferences.chart_types
            if preferences.time_window:
                pref_dict["time_window"] = preferences.time_window
            if preferences.max_series:
                pref_dict["max_series"] = preferences.max_series

            if pref_dict:
                prompt += f"""
## User Preferences
{json.dumps(pref_dict, indent=2)}
"""

        prompt += """
Based on the user's request and available data, select the best skill and generate the parameters.
Remember: Only use topics and fields that exist in the Available Data section."""

        return prompt

    def _fallback_selection(self, query: str, rag_context: RAGContext) -> SkillParameters:
        """Fallback skill selection when LLM fails."""
        # Default to time_series_line with first available topic
        if rag_context.matching_topics:
            first_topic = rag_context.matching_topics[0]
            topic_path = first_topic.get("path", first_topic.get("topic"))
            fields = first_topic.get("available_fields", ["value"])

            return SkillParameters(
                skill_id="time_series_line",
                parameters={
                    "topics": [topic_path] if topic_path else [],
                    "fields": [fields[0]] if fields else ["value"],
                    "window": "1h"
                },
                reasoning="Fallback: Using time series line chart with first matching topic"
            )

        return SkillParameters(
            skill_id="clarification_needed",
            parameters={},
            reasoning="Could not find matching data for the request"
        )

    async def refine_parameters(
        self,
        original_query: str,
        refinement: str,
        current_params: SkillParameters,
        rag_context: RAGContext
    ) -> SkillParameters:
        """
        Refine existing parameters based on user feedback.
        Used for multi-turn conversations.
        """
        prompt = f"""The user previously asked: "{original_query}"
You selected skill "{current_params.skill_id}" with parameters:
{json.dumps(current_params.parameters, indent=2)}

The user now says: "{refinement}"

Update the parameters based on this feedback. You may change the skill if appropriate.
Available data context:
{json.dumps({"topics": [t.get("path", t.get("topic")) for t in rag_context.matching_topics[:10]]}, indent=2)}
"""

        try:
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._build_system_prompt([])},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                )
            except Exception as json_mode_err:
                logger.warning(f"JSON mode failed in refinement ({json_mode_err}), retrying without response_format")
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": self._build_system_prompt([])},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.1,
                )

            content = response.choices[0].message.content
            result = json.loads(content)

            return SkillParameters(
                skill_id=result.get("skill_id", current_params.skill_id),
                parameters=result.get("parameters", current_params.parameters),
                reasoning=result.get("reasoning")
            )
        except Exception as e:
            logger.error(f"Refinement error: {e}")
            return current_params
