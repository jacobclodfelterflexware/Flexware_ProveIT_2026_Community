"""Key transformation CRUD endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, KeyTransformation, TopicMapping
from .schemas import (
    KeyTransformationCreate,
    KeyTransformationUpdate,
    KeyTransformationResponse,
)

router = APIRouter(prefix="/transforms", tags=["Key Transformations"])


@router.get("/", response_model=List[KeyTransformationResponse])
async def list_transforms(
    topic_mapping_id: Optional[int] = Query(None, description="Filter by topic mapping ID"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all key transformations with optional filtering."""
    query = select(KeyTransformation)

    if topic_mapping_id is not None:
        query = query.where(KeyTransformation.topic_mapping_id == topic_mapping_id)

    if is_active is not None:
        query = query.where(KeyTransformation.is_active == is_active)

    query = query.order_by(
        KeyTransformation.topic_mapping_id,
        KeyTransformation.transform_order,
    ).offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=KeyTransformationResponse, status_code=201)
async def create_transform(
    transform: KeyTransformationCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new key transformation."""
    # Verify topic mapping exists
    mapping_result = await db.execute(
        select(TopicMapping).where(TopicMapping.id == transform.topic_mapping_id)
    )
    if not mapping_result.scalar_one_or_none():
        raise HTTPException(
            status_code=404,
            detail=f"Topic mapping with ID {transform.topic_mapping_id} not found",
        )

    # Check for duplicate
    existing = await db.execute(
        select(KeyTransformation).where(
            KeyTransformation.topic_mapping_id == transform.topic_mapping_id,
            KeyTransformation.source_key == transform.source_key,
            KeyTransformation.json_path == transform.json_path,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Transformation for key '{transform.source_key}' already exists",
        )

    db_transform = KeyTransformation(**transform.model_dump())
    db.add(db_transform)
    await db.commit()
    await db.refresh(db_transform)

    return db_transform


@router.get("/{transform_id}", response_model=KeyTransformationResponse)
async def get_transform(
    transform_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific key transformation by ID."""
    query = select(KeyTransformation).where(KeyTransformation.id == transform_id)
    result = await db.execute(query)
    transform = result.scalar_one_or_none()

    if not transform:
        raise HTTPException(status_code=404, detail="Transformation not found")

    return transform


@router.patch("/{transform_id}", response_model=KeyTransformationResponse)
async def update_transform(
    transform_id: int,
    update: KeyTransformationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a key transformation."""
    query = select(KeyTransformation).where(KeyTransformation.id == transform_id)
    result = await db.execute(query)
    transform = result.scalar_one_or_none()

    if not transform:
        raise HTTPException(status_code=404, detail="Transformation not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(transform, key, value)

    await db.commit()
    await db.refresh(transform)

    return transform


@router.delete("/{transform_id}", status_code=204)
async def delete_transform(
    transform_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a key transformation."""
    query = select(KeyTransformation).where(KeyTransformation.id == transform_id)
    result = await db.execute(query)
    transform = result.scalar_one_or_none()

    if not transform:
        raise HTTPException(status_code=404, detail="Transformation not found")

    await db.delete(transform)
    await db.commit()
