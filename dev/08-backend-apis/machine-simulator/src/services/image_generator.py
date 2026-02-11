"""OpenAI-based image generation service for machine visuals."""

import base64
import logging
from typing import Optional

from openai import OpenAI

from ..config import config

logger = logging.getLogger(__name__)


class ImageGenerator:
    """Service for generating machine images using OpenAI's image API."""

    def __init__(self):
        self.client: Optional[OpenAI] = None
        if config.openai_api_key:
            self.client = OpenAI(api_key=config.openai_api_key)
        else:
            logger.warning("No OpenAI API key configured - image generation disabled")

    def _build_prompt(
        self,
        machine_type: str,
        description: Optional[str] = None,
        fields: Optional[list] = None
    ) -> str:
        """Build an image generation prompt from machine definition."""
        # Base prompt for industrial equipment visualization
        prompt_parts = [
            "Professional 3D render of an industrial",
            machine_type.lower(),
            "machine in a modern factory setting.",
            "Clean, photorealistic style with soft studio lighting.",
            "The machine should look operational and high-tech.",
        ]

        # Add context from description
        if description:
            # Extract key visual elements from description
            prompt_parts.append(f"The machine {description.lower()}.")

        # Add visual hints based on field types
        if fields:
            visual_hints = []
            for field in fields:
                name = field.get("name", "").lower()
                # Add visual elements based on common telemetry field names
                if "temperature" in name or "temp" in name:
                    visual_hints.append("temperature gauges")
                elif "pressure" in name:
                    visual_hints.append("pressure indicators")
                elif "speed" in name or "rpm" in name:
                    visual_hints.append("speed display")
                elif "counter" in name or "count" in name:
                    visual_hints.append("digital counter display")
                elif "status" in name or "running" in name:
                    visual_hints.append("status indicator lights")

            if visual_hints:
                unique_hints = list(set(visual_hints))[:3]  # Limit to 3 hints
                prompt_parts.append(f"Visible features include: {', '.join(unique_hints)}.")

        # Style guidance
        prompt_parts.extend([
            "No text or labels on the machine.",
            "Dark industrial background with subtle blue accent lighting.",
            "Highly detailed metallic surfaces."
        ])

        return " ".join(prompt_parts)

    async def generate_machine_image(
        self,
        machine_type: str,
        description: Optional[str] = None,
        fields: Optional[list] = None
    ) -> Optional[str]:
        """
        Generate an image for a machine and return as base64.

        Args:
            machine_type: Type of machine (e.g., "CNC Mill", "Conveyor Belt")
            description: Optional description of the machine
            fields: Optional list of field definitions for visual hints

        Returns:
            Base64-encoded PNG image, or None if generation fails
        """
        if not self.client:
            logger.warning("Image generation requested but OpenAI client not configured")
            return None

        prompt = self._build_prompt(machine_type, description, fields)
        logger.info(f"Generating image for {machine_type}")
        logger.debug(f"Image prompt: {prompt}")

        try:
            # DALL-E 3 only supports URL response format
            result = self.client.images.generate(
                model=config.image_model,
                prompt=prompt,
                size=config.image_size,
                n=1,
            )

            # Get image data
            image_data = result.data[0]

            # DALL-E 3 returns URL - fetch and convert to base64
            if hasattr(image_data, 'url') and image_data.url:
                import httpx
                async with httpx.AsyncClient(timeout=30.0) as http_client:
                    response = await http_client.get(image_data.url)
                    if response.status_code == 200:
                        return base64.b64encode(response.content).decode('utf-8')
                    else:
                        logger.error(f"Failed to fetch image from URL: {response.status_code}")

            logger.warning("No image URL in response")
            return None

        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return None

    async def generate_thumbnail(
        self,
        machine_type: str,
        description: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate a smaller thumbnail image for list views.

        Args:
            machine_type: Type of machine
            description: Optional description

        Returns:
            Base64-encoded PNG thumbnail, or None if generation fails
        """
        if not self.client:
            return None

        # Simpler prompt for thumbnails
        prompt = (
            f"Simple icon of a {machine_type.lower()} industrial machine. "
            "Minimalist style, dark background, blue accent lighting. "
            "Clean professional look suitable for a dashboard icon."
        )

        try:
            result = self.client.images.generate(
                model=config.image_model,
                prompt=prompt,
                size="256x256",  # Smaller for thumbnails
                n=1,
            )

            image_data = result.data[0]
            if hasattr(image_data, 'b64_json') and image_data.b64_json:
                return image_data.b64_json

            return None

        except Exception as e:
            logger.error(f"Thumbnail generation failed: {e}")
            return None


# Singleton instance
image_generator = ImageGenerator()
