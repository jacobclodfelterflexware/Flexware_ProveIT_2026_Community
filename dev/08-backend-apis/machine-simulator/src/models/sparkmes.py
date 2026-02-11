"""Pydantic models for SparkMES tag structures."""

from typing import Any, Optional, Union
from pydantic import BaseModel, Field


class SparkMESParameter(BaseModel):
    """A SparkMES parameter with dataType and value."""
    dataType: str = Field(..., description="Data type: String, Integer, etc.")
    value: Any = Field(..., description="Parameter value")


class SparkMESTag(BaseModel):
    """A SparkMES tag (AtomicTag or Folder)."""
    name: str = Field(..., description="Tag name")
    tagType: str = Field(..., description="Tag type: AtomicTag or Folder")
    value: Optional[Any] = Field(None, description="Tag value (for AtomicTag)")
    tags: Optional[list["SparkMESTag"]] = Field(None, description="Nested tags (for Folder)")

    model_config = {"extra": "ignore"}


class SparkMESConfig(BaseModel):
    """Per-machine SparkMES configuration."""
    machine_name: str = Field("Machine 1", description="SparkMES machine name")
    type_id: str = Field(
        "Simulators/AdvancedDiscreteMachineSimulator",
        description="SparkMES type identifier"
    )
    next_machine_path: Optional[str] = Field(
        None,
        description="Path to next machine in the line (e.g., '[default]Simulation/Plant/Line/Machine 2')"
    )
    cycle_time_seconds: float = Field(
        30.0,
        description="Average cycle time in seconds"
    )
    scrap_rate: float = Field(
        0.01,
        description="Scrap rate (0.01 = 1%)"
    )
    # Optional correlation overrides (auto-detected if None)
    running_field: Optional[str] = Field(
        None,
        description="Telemetry field name for running state (auto-detected if None)"
    )
    count_field: Optional[str] = Field(
        None,
        description="Telemetry field name for part count (auto-detected if None)"
    )

    model_config = {"extra": "ignore"}


class SparkMESPayload(BaseModel):
    """Complete SparkMES payload structure."""
    name: str = Field(..., description="Machine name")
    typeId: str = Field(..., description="Type identifier")
    parameters: dict[str, SparkMESParameter] = Field(
        default_factory=dict,
        description="Machine parameters"
    )
    tagType: str = Field("UdtInstance", description="Tag type")
    tags: list[SparkMESTag] = Field(default_factory=list, description="Machine tags")

    model_config = {"extra": "ignore"}

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return self.model_dump(exclude_none=False)
