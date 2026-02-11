"""Pydantic schemas for API requests and responses."""
from datetime import datetime
from typing import Optional, List, Any

from pydantic import BaseModel, Field, ConfigDict


# Topic Mapping Schemas
class TopicMappingBase(BaseModel):
    """Base schema for topic mapping."""

    source_topic: str = Field(..., max_length=1024, description="Source MQTT topic pattern")
    target_topic: str = Field(..., max_length=1024, description="Target MQTT topic")
    description: Optional[str] = Field(None, description="Description of this mapping")
    is_active: bool = Field(True, description="Whether this mapping is active")


class TopicMappingCreate(TopicMappingBase):
    """Schema for creating a topic mapping."""

    pass


class TopicMappingUpdate(BaseModel):
    """Schema for updating a topic mapping."""

    target_topic: Optional[str] = Field(None, max_length=1024)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class KeyTransformationBase(BaseModel):
    """Base schema for key transformation."""

    source_key: str = Field(..., max_length=512, description="Original JSON key name")
    target_key: str = Field(..., max_length=512, description="New JSON key name")
    json_path: Optional[str] = Field(
        None, max_length=1024, description="JSONPath for nested key transformation"
    )
    transform_order: int = Field(0, description="Order of transformation application")
    is_active: bool = Field(True, description="Whether this transformation is active")


class KeyTransformationCreate(KeyTransformationBase):
    """Schema for creating a key transformation."""

    topic_mapping_id: int = Field(..., description="ID of the parent topic mapping")


class KeyTransformationUpdate(BaseModel):
    """Schema for updating a key transformation."""

    target_key: Optional[str] = Field(None, max_length=512)
    json_path: Optional[str] = None
    transform_order: Optional[int] = None
    is_active: Optional[bool] = None


class KeyTransformationResponse(KeyTransformationBase):
    """Response schema for key transformation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_mapping_id: int
    created_at: datetime
    updated_at: datetime


class TopicMappingResponse(TopicMappingBase):
    """Response schema for topic mapping."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    key_transformations: List[KeyTransformationResponse] = []


class TopicMappingListResponse(BaseModel):
    """Response schema for listing topic mappings."""

    mappings: List[TopicMappingResponse]
    total: int


# Unmapped Topic Schemas
class UnmappedTopicResponse(BaseModel):
    """Response schema for unmapped topic."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    topic: str
    first_seen: datetime
    last_seen: datetime
    message_count: int
    sample_payload: Optional[dict] = None


class UnmappedTopicListResponse(BaseModel):
    """Response schema for listing unmapped topics."""

    topics: List[UnmappedTopicResponse]
    total: int


class QuickMapRequest(BaseModel):
    """Request schema for quick-mapping an unmapped topic."""

    target_topic: str = Field(..., max_length=1024, description="Target topic to map to")
    description: Optional[str] = Field(None, description="Description of this mapping")


# SSE Stream Schemas
class TopicTreeNode(BaseModel):
    """Schema for a node in the topic tree."""

    name: str
    full_path: str
    children: List["TopicTreeNode"] = []
    message_count: int = 0
    last_message: Optional[dict] = None
    is_leaf: bool = False


class TopicTreeResponse(BaseModel):
    """Response schema for topic tree SSE stream."""

    tree: Optional[TopicTreeNode] = None
    stats: dict = Field(default_factory=dict)
    broker: str


class MappingStatsResponse(BaseModel):
    """Response schema for mapping statistics."""

    total_mappings: int
    active_mappings: int
    total_transformations: int
    unmapped_topics: int
    messages_processed: int = 0
    messages_transformed: int = 0
    messages_dropped: int = 0


# Health check
class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str
    mqtt_uncurated_connected: bool = False
    mqtt_curated_connected: bool = False
    database_connected: bool = False
    cache_ready: bool = False


# Rebuild models for forward references
TopicTreeNode.model_rebuild()
