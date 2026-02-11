"""Image generation API endpoints."""

import logging
from typing import Optional
from pydantic import BaseModel, Field

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..services import image_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/images", tags=["images"])


class GenerateImageRequest(BaseModel):
    """Request to generate a machine image."""
    machine_type: str = Field(..., description="Type of machine (e.g., 'CNC Mill')")
    description: Optional[str] = Field(None, description="Machine description")
    fields: Optional[list[dict]] = Field(None, description="Field definitions for visual hints")


class GenerateImageResponse(BaseModel):
    """Response with generated image."""
    image_base64: str = Field(..., description="Base64-encoded PNG image")
    prompt_used: Optional[str] = Field(None, description="The prompt used for generation")


@router.post("/generate", response_model=GenerateImageResponse)
async def generate_machine_image(request: GenerateImageRequest):
    """
    Generate a photorealistic image of an industrial machine.

    The image is generated based on the machine type, description, and field
    definitions. Visual elements like gauges and displays are added based
    on the field names (e.g., temperature fields add temperature gauges).
    """
    if not request.machine_type:
        raise HTTPException(status_code=400, detail="machine_type is required")

    image_base64 = await image_generator.generate_machine_image(
        machine_type=request.machine_type,
        description=request.description,
        fields=request.fields
    )

    if not image_base64:
        raise HTTPException(
            status_code=503,
            detail="Image generation unavailable. Check OpenAI API key configuration."
        )

    return GenerateImageResponse(image_base64=image_base64)


@router.post("/generate/thumbnail")
async def generate_thumbnail(request: GenerateImageRequest):
    """
    Generate a smaller thumbnail image suitable for list views.
    """
    if not request.machine_type:
        raise HTTPException(status_code=400, detail="machine_type is required")

    image_base64 = await image_generator.generate_thumbnail(
        machine_type=request.machine_type,
        description=request.description
    )

    if not image_base64:
        raise HTTPException(
            status_code=503,
            detail="Image generation unavailable. Check OpenAI API key configuration."
        )

    return GenerateImageResponse(image_base64=image_base64)


@router.post("/generate/raw")
async def generate_image_raw(request: GenerateImageRequest):
    """
    Generate an image and return as raw PNG bytes.

    This endpoint returns the image directly as a PNG file,
    useful for direct embedding in img tags.
    """
    import base64

    if not request.machine_type:
        raise HTTPException(status_code=400, detail="machine_type is required")

    image_base64 = await image_generator.generate_machine_image(
        machine_type=request.machine_type,
        description=request.description,
        fields=request.fields
    )

    if not image_base64:
        raise HTTPException(
            status_code=503,
            detail="Image generation unavailable"
        )

    image_bytes = base64.b64decode(image_base64)
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=machine.png"}
    )
