"""SQLAlchemy ORM models for middleware database."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, BigInteger, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .connection import Base


class TopicMapping(Base):
    """Topic mapping model."""

    __tablename__ = "topic_mappings"
    __table_args__ = {"schema": "middleware"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_topic: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    target_topic: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship to key transformations
    key_transformations: Mapped[List["KeyTransformation"]] = relationship(
        "KeyTransformation",
        back_populates="topic_mapping",
        cascade="all, delete-orphan",
        order_by="KeyTransformation.transform_order",
    )

    def __repr__(self) -> str:
        return f"<TopicMapping(id={self.id}, source={self.source_topic}, target={self.target_topic})>"


class KeyTransformation(Base):
    """Key transformation model for renaming JSON keys."""

    __tablename__ = "key_transformations"
    __table_args__ = {"schema": "middleware"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic_mapping_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("middleware.topic_mappings.id", ondelete="CASCADE"), nullable=False
    )
    source_key: Mapped[str] = mapped_column(String(512), nullable=False)
    target_key: Mapped[str] = mapped_column(String(512), nullable=False)
    json_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    transform_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship back to topic mapping
    topic_mapping: Mapped["TopicMapping"] = relationship(
        "TopicMapping", back_populates="key_transformations"
    )

    def __repr__(self) -> str:
        return f"<KeyTransformation(id={self.id}, {self.source_key} -> {self.target_key})>"


class UnmappedTopic(Base):
    """Unmapped topic tracking model."""

    __tablename__ = "unmapped_topics"
    __table_args__ = {"schema": "middleware"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    topic: Mapped[str] = mapped_column(String(1024), unique=True, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    message_count: Mapped[int] = mapped_column(BigInteger, default=1)
    sample_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<UnmappedTopic(id={self.id}, topic={self.topic}, count={self.message_count})>"
