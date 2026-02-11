"""Pydantic models for simulated machines."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .sparkmes import SparkMESConfig


class FieldType(str, Enum):
    """Supported field types."""
    STRING = "string"
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"


class MachineStatus(str, Enum):
    """Machine lifecycle status."""
    DRAFT = "draft"           # Configured but not publishing
    RUNNING = "running"       # Actively publishing simulated data


class FieldDefinition(BaseModel):
    """Definition of a single field in the machine payload."""
    name: str = Field(..., description="Field name in the payload")
    type: FieldType = Field(..., description="Data type of the field")
    formula: Optional[str] = Field(None, description="Math formula for dynamic values (e.g., '20 + 5 * sin(t / 60)')")
    static_value: Optional[Any] = Field(None, description="Static value for non-dynamic fields")
    description: Optional[str] = Field(None, description="Human-readable description")
    min_value: Optional[float] = Field(None, description="Expected minimum value (for numeric)")
    max_value: Optional[float] = Field(None, description="Expected maximum value (for numeric)")

    model_config = {"extra": "ignore"}

    def model_dump(self, **kwargs):
        """Override to exclude None values by default."""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)


class TopicDefinition(BaseModel):
    """Definition of a single topic and its fields for multi-topic machines."""
    topic_path: str = Field(..., description="MQTT topic path")
    fields: list[FieldDefinition] = Field(default_factory=list, description="Fields for this topic's payload")

    model_config = {"extra": "ignore"}


class MachineDefinition(BaseModel):
    """Complete definition of a simulated machine."""
    id: Optional[str] = Field(None, description="UUID, assigned on creation")
    name: str = Field(..., description="User-provided machine name")
    description: Optional[str] = Field(None, description="Machine description")
    machine_type: Optional[str] = Field(None, description="Type of machine (e.g., CNC Mill, Conveyor)")

    # Topic & Schema - Support both single topic (backward compat) and multi-topic
    topic_path: Optional[str] = Field(None, description="MQTT topic path for single-topic machines")
    schema_proposal_id: Optional[str] = Field(None, description="FK to SchemaProposal after approval")

    # Fields - For single-topic machines (backward compat)
    fields: list[FieldDefinition] = Field(default_factory=list, description="Payload field definitions for single-topic")

    # Multi-topic support - Each topic has its own path and fields
    topics: list[TopicDefinition] = Field(default_factory=list, description="Multiple topics with their own fields")

    # Publishing config
    publish_interval_ms: int = Field(5000, description="Publish interval in milliseconds")

    # Status
    status: MachineStatus = Field(MachineStatus.DRAFT, description="Current status")

    # Image
    image_base64: Optional[str] = Field(None, description="Base64 encoded image of the machine")

    # SparkMES integration
    sparkmes_enabled: bool = Field(True, description="Enable SparkMES tag publishing to separate topic")
    sparkmes: Optional[dict] = Field(None, description="Full SparkMES tag structure from LLM")

    # CESMII SM Profile (Machine Identification)
    smprofile: Optional[dict] = Field(None, description="CESMII SM Profile payload (Machine Identification)")

    # Metadata
    created_at: Optional[datetime] = None
    created_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    last_published_at: Optional[datetime] = None

    # Similarity context (stored during creation for detail page visualization)
    similarity_results: list[dict] = Field(default_factory=list, description="Similarity search results from creation")

    def get_all_topics(self) -> list[TopicDefinition]:
        """Get all topics - either from topics list or single topic_path/fields."""
        if self.topics:
            return self.topics
        elif self.topic_path:
            return [TopicDefinition(topic_path=self.topic_path, fields=self.fields)]
        return []


class GenerateRandomRequest(BaseModel):
    """Request to generate a random machine."""
    machine_type_hint: Optional[str] = Field(None, description="Optional hint for machine type")


class GeneratePromptedRequest(BaseModel):
    """Request to generate a machine from user prompt."""
    prompt: str = Field(..., description="User's description of the desired machine")
    conversation_history: Optional[list[dict]] = Field(None, description="Previous messages in conversation")


class ContextTopic(BaseModel):
    """A topic fetched from the knowledge graph for LLM context."""
    topic_path: str
    field_names: list[str]
    payload_preview: str  # Truncated JSON preview


class GeneratedMachineResponse(BaseModel):
    """LLM-generated machine definition (before approval)."""
    machine_type: str
    suggested_name: str
    description: Optional[str] = None
    topic_path: Optional[str] = None  # Set during Connect flow via similarity search
    fields: list[FieldDefinition]
    publish_interval_ms: int = 5000
    rationale: Optional[str] = None
    context_topics: Optional[list[ContextTopic]] = None  # Topics used for generation context
    sparkmes: Optional[dict] = Field(None, description="SparkMES tag structure from LLM")
    smprofile: Optional[dict] = Field(None, description="CESMII SM Profile payload")

    model_config = {"extra": "ignore"}

    def model_dump(self, **kwargs):
        """Override to exclude None values by default."""
        kwargs.setdefault("exclude_none", True)
        return super().model_dump(**kwargs)


class CreateMachineRequest(BaseModel):
    """Request to create/save a machine after approval."""
    name: str
    description: Optional[str] = None
    machine_type: Optional[str] = None
    # Single topic (backward compat)
    topic_path: Optional[str] = None
    schema_proposal_id: Optional[str] = None
    fields: list[FieldDefinition] = Field(default_factory=list)
    # Multi-topic support
    topics: list[TopicDefinition] = Field(default_factory=list)
    publish_interval_ms: int = 5000
    # Image
    image_base64: Optional[str] = None
    # Similarity context from creation
    similarity_results: list[dict] = Field(default_factory=list, description="Similarity search results to persist")
    # SparkMES integration
    sparkmes_enabled: bool = Field(True, description="Enable SparkMES tag publishing")
    sparkmes: Optional[dict] = Field(None, description="SparkMES tag structure from LLM")
    # CESMII SM Profile
    smprofile: Optional[dict] = Field(None, description="CESMII SM Profile payload")
    # Creator
    created_by: Optional[str] = Field(None, description="Name of the person who created this machine")


class MachineListResponse(BaseModel):
    """Response for listing machines."""
    machines: list[MachineDefinition]
    total: int


class MachineStatusResponse(BaseModel):
    """Response for machine status."""
    id: str
    name: str
    status: MachineStatus
    is_running: bool
    last_published_at: Optional[datetime] = None
    messages_published: int = 0


class GenerateSMProfileRequest(BaseModel):
    """Request to generate a CESMII SM Profile for a machine."""
    machine_type: str = Field(..., description="Type of machine")
    machine_name: str = Field(..., description="Name of machine")
    description: Optional[str] = Field(None, description="Machine description")


class GenerateSMProfileResponse(BaseModel):
    """Response containing generated SM Profile."""
    smprofile: dict = Field(..., description="Generated SM Profile payload")


class GenerateLadderRequest(BaseModel):
    """Request to generate ladder logic for a machine."""
    machine_type: str = Field(..., description="Type of machine (e.g., 'Conveyor Belt', 'CNC Mill')")
    fields: list[FieldDefinition] = Field(..., description="Machine fields to map as I/O")
    description: Optional[str] = Field(None, description="Optional description of the machine")


class LadderElement(BaseModel):
    """A single element in a ladder rung."""
    type: str = Field(..., description="Element type: contact, inverted_contact, output, set_coil, reset_coil, timer, counter")
    name: str = Field(..., description="Element name/tag")
    preset_ms: Optional[int] = Field(None, description="Timer preset in milliseconds")
    timer_type: Optional[str] = Field(None, description="Timer type: TON, TOFF")
    preset: Optional[int] = Field(None, description="Counter preset value")
    counter_type: Optional[str] = Field(None, description="Counter type: CTU, CTD")


class LadderRung(BaseModel):
    """A single rung in ladder logic."""
    description: str = Field(..., description="Description of what this rung does")
    elements: list[LadderElement] = Field(..., description="Elements in series on this rung")


class LadderProgram(BaseModel):
    """Complete ladder logic program."""
    rungs: list[LadderRung] = Field(..., description="List of rungs in the program")


class IOMapping(BaseModel):
    """Mapping of I/O names."""
    inputs: list[str] = Field(default_factory=list, description="Input tag names")
    outputs: list[str] = Field(default_factory=list, description="Output tag names")
    internal: list[str] = Field(default_factory=list, description="Internal bit names")


class GenerateLadderResponse(BaseModel):
    """Response containing generated ladder logic."""
    ladder_program: LadderProgram = Field(..., description="The generated ladder program")
    io_mapping: IOMapping = Field(..., description="Mapping of inputs, outputs, and internal bits")
    rationale: Optional[str] = Field(None, description="Explanation of the control logic design")
