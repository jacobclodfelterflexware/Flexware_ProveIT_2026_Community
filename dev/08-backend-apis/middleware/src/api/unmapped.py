"""Unmapped topics endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db, UnmappedTopic, TopicMapping
from .schemas import (
    UnmappedTopicResponse,
    UnmappedTopicListResponse,
    QuickMapRequest,
    TopicMappingResponse,
)

router = APIRouter(prefix="/unmapped", tags=["Unmapped Topics"])


@router.get("/", response_model=UnmappedTopicListResponse)
async def list_unmapped(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search in topic names"),
    order_by: str = Query("last_seen", description="Order by field", enum=["last_seen", "first_seen", "message_count", "topic"]),
    order_desc: bool = Query(True, description="Order descending"),
    db: AsyncSession = Depends(get_db),
):
    """List all unmapped topics with pagination and filtering."""
    query = select(UnmappedTopic)

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.where(UnmappedTopic.topic.ilike(search_pattern))

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply ordering
    order_column = getattr(UnmappedTopic, order_by)
    if order_desc:
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # Apply pagination
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    topics = result.scalars().all()

    return UnmappedTopicListResponse(topics=topics, total=total)


@router.get("/{unmapped_id}", response_model=UnmappedTopicResponse)
async def get_unmapped(
    unmapped_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific unmapped topic by ID."""
    query = select(UnmappedTopic).where(UnmappedTopic.id == unmapped_id)
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(status_code=404, detail="Unmapped topic not found")

    return topic


@router.post("/{unmapped_id}/quick-map", response_model=TopicMappingResponse, status_code=201)
async def quick_map(
    unmapped_id: int,
    request: QuickMapRequest,
    db: AsyncSession = Depends(get_db),
):
    """Quick-map an unmapped topic to a target topic."""
    # Get the unmapped topic
    query = select(UnmappedTopic).where(UnmappedTopic.id == unmapped_id)
    result = await db.execute(query)
    unmapped = result.scalar_one_or_none()

    if not unmapped:
        raise HTTPException(status_code=404, detail="Unmapped topic not found")

    # Check if mapping already exists for this source
    existing = await db.execute(
        select(TopicMapping).where(TopicMapping.source_topic == unmapped.topic)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail=f"Mapping for source topic '{unmapped.topic}' already exists",
        )

    # Create the mapping
    mapping = TopicMapping(
        source_topic=unmapped.topic,
        target_topic=request.target_topic,
        description=request.description,
        is_active=True,
    )
    db.add(mapping)

    # Remove from unmapped topics
    await db.delete(unmapped)

    await db.commit()
    await db.refresh(mapping)

    # Load relationships
    result = await db.execute(
        select(TopicMapping)
        .where(TopicMapping.id == mapping.id)
        .options(selectinload(TopicMapping.key_transformations))
    )
    return result.scalar_one()


@router.delete("/{unmapped_id}", status_code=204)
async def delete_unmapped(
    unmapped_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Delete an unmapped topic (dismiss/ignore it)."""
    query = select(UnmappedTopic).where(UnmappedTopic.id == unmapped_id)
    result = await db.execute(query)
    topic = result.scalar_one_or_none()

    if not topic:
        raise HTTPException(status_code=404, detail="Unmapped topic not found")

    await db.delete(topic)
    await db.commit()


@router.delete("/", status_code=204)
async def clear_unmapped(
    older_than_hours: Optional[int] = Query(None, description="Clear topics older than N hours"),
    db: AsyncSession = Depends(get_db),
):
    """Clear all unmapped topics, optionally filtering by age."""
    query = delete(UnmappedTopic)

    if older_than_hours is not None:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
        query = query.where(UnmappedTopic.last_seen < cutoff)

    await db.execute(query)
    await db.commit()
