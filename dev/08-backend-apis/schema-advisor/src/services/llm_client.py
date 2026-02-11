"""OpenAI LLM client for schema suggestions."""
import json
import logging
from typing import Any, List, Dict, Union

from openai import AsyncOpenAI

from config import config

logger = logging.getLogger(__name__)


class LLMClient:
    """OpenAI LLM client for schema suggestions."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self.model = config.openai_model
        self.temperature = config.openai_temperature
        self.max_tokens = config.openai_max_tokens

    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        require_json: bool = False
    ) -> Union[Dict[str, Any], str, None]:
        """
        Multi-turn chat completion with full message history.

        Args:
            messages: List of messages with 'role' and 'content' keys
            require_json: If True, enforce JSON response format

        Returns:
            Parsed JSON dict if require_json, else raw string content, or None on failure
        """
        try:
            kwargs = {
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "messages": messages
            }

            if require_json:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content

            if require_json:
                result = json.loads(content)
                logger.info(f"LLM chat response received (JSON mode)")
                return result

            logger.info(f"LLM chat response received (text mode)")
            return content

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM chat request failed: {e}")
            return None

    async def suggest_schema(
        self,
        system_prompt: str,
        user_prompt: str
    ) -> dict[str, Any] | None:
        """
        Call LLM to suggest schema mapping.

        Returns parsed JSON response or None on failure.
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            result = json.loads(content)

            logger.info(f"LLM suggestion received: {result.get('suggestedFullTopicPath')}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON response: {e}")
            return None
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            return None
