"""Topic mapping CRUD endpoints."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, TopicMapping
from .schemas import (
    TopicMappingCreate,
    TopicMappingUpdate,
    TopicMappingResponse,
    TopicMappingListResponse,
)

router = APIRouter(prefix="/mappings", tags=["Topic Mappings"])


@router.get("/", response_model=TopicMappingListResponse)
async def list_mappings(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search in source/target topics"),
    db: AsyncSession = Depends(get_db),
):
    """List all topic mappings with pagination and filtering."""
    # Build query
    query = select(TopicMapping).options(
        selectinload(TopicMapping.key_transformations)
    )

    # Apply filters
    if is_active is not None:
        query = query.where(TopicMapping.is_active == is_active)

    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            (TopicMapping.source_topic.ilike(search_pattern))
            | (TopicMapping.target_topic.ilike(search_pattern))
        )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    query = query.order_by(TopicMapping.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    mappings = result.scalars().all()

    return TopicMappingListResponse(mappings=mappings, total=total)


@router.post("/", response_model=TopicMappingResponse, status_code=201)
async def create_mapping(
    mapping: TopicMappingCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new topic mapping."""
    # Check if source topic already exists
    existing = await db.execute(
        select(TopicMapping).where(TopicMapping.source_topic == mapping.source_topic)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Mapping for source topic '{mapping.source_topic}' already exists",
        )

    db_mapping = TopicMapping(**mapping.model_dump())
    db.add(db_mapping)
    await db.commit()
    await db.refresh(db_mapping)

    # Load relationships
    result = await db.execute(
        select(TopicMapping)
        .where(TopicMapping.id == db_mapping.id)
        .options(selectinload(TopicMapping.key_transformations))
    )
    return result.scalar_one()


@router.get("/{mapping_id}", response_model=TopicMappingResponse)
async def get_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific topic mapping by ID."""
    query = (
        select(TopicMapping)
        .where(TopicMapping.id == mapping_id)
        .options(selectinload(TopicMapping.key_transformations))
    )
    result = await db.execute(query)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return mapping


@router.patch("/{mapping_id}", response_model=TopicMappingResponse)
async def update_mapping(
    mapping_id: int,
    update: TopicMappingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a topic mapping."""
    query = select(TopicMapping).where(TopicMapping.id == mapping_id)
    result = await db.execute(query)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    # Update fields
    update_data = update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(mapping, key, value)

    await db.commit()
    await db.refresh(mapping)

    # Reload with relationships
    result = await db.execute(
        select(TopicMapping)
        .where(TopicMapping.id == mapping_id)
        .options(selectinload(TopicMapping.key_transformations))
    )
    return result.scalar_one()


@router.delete("/{mapping_id}", status_code=204)
async def delete_mapping(
    mapping_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete a topic mapping."""
    query = select(TopicMapping).where(TopicMapping.id == mapping_id)
    result = await db.execute(query)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    await db.delete(mapping)
    await db.commit()


@router.get("/by-source/{source_topic:path}", response_model=TopicMappingResponse)
async def get_mapping_by_source(
    source_topic: str,
    db: AsyncSession = Depends(get_db),
):
    """Get mapping by source topic."""
    query = (
        select(TopicMapping)
        .where(TopicMapping.source_topic == source_topic)
        .options(selectinload(TopicMapping.key_transformations))
    )
    result = await db.execute(query)
    mapping = result.scalar_one_or_none()

    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")

    return mapping
