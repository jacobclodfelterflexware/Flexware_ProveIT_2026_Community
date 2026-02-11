from pydantic import BaseModel, Field
from typing import Optional, Any
from enum import Enum


class ChartPreferences(BaseModel):
    """Optional preferences to constrain chart generation."""
    chart_types: Optional[list[str]] = Field(
        default=None,
        description="Limit to specific chart types (e.g., ['line', 'scatter'])"
    )
    time_window: Optional[str] = Field(
        default="1h",
        description="Default time window (e.g., '1h', '24h', '7d')"
    )
    max_series: Optional[int] = Field(
        default=10,
        description="Maximum number of data series to display"
    )


class ChartGenerateRequest(BaseModel):
    """Request to generate a chart from natural language."""
    query: str = Field(..., description="Natural language chart request")
    conversation_id: Optional[str] = Field(
        default=None,
        description="Optional conversation ID for multi-turn refinement"
    )
    preferences: Optional[ChartPreferences] = None


class ChartDataPoint(BaseModel):
    """A single data point for chart rendering."""
    x: Any = Field(..., description="X-axis value (typically timestamp or category)")
    y: Any = Field(..., description="Y-axis value")
    series: Optional[str] = Field(default=None, description="Series identifier for multi-series charts")
    label: Optional[str] = Field(default=None, description="Optional label for the point")


class ChartDataset(BaseModel):
    """A dataset for chart rendering."""
    label: str
    data: list[ChartDataPoint]
    borderColor: Optional[str] = None
    backgroundColor: Optional[str] = None
    fill: Optional[bool] = False
    tension: Optional[float] = 0.1


class ChartConfig(BaseModel):
    """Chart.js compatible configuration."""
    type: str = Field(..., description="Chart type: line, bar, scatter, pie, doughnut, etc.")
    data: dict = Field(..., description="Chart data with labels and datasets")
    options: dict = Field(default_factory=dict, description="Chart.js options")


class SkillParameters(BaseModel):
    """Parameters selected by LLM for skill execution."""
    skill_id: str
    parameters: dict
    reasoning: Optional[str] = None


class RAGContext(BaseModel):
    """Context retrieved via RAG for LLM prompting."""
    matching_topics: list[dict]
    topic_hierarchy: dict
    time_range_available: Optional[str] = None
    available_fields: list[str]


class ChartGenerateResponse(BaseModel):
    """Response from chart generation."""
    chart_id: str = Field(..., description="Unique chart ID for streaming")
    skill_used: str = Field(..., description="The skill that was selected")
    chart_config: ChartConfig = Field(..., description="Chart.js configuration")
    initial_data: dict = Field(..., description="Initial query results")
    stream_url: str = Field(..., description="SSE stream URL for real-time updates")
    parameters_used: dict = Field(..., description="Validated parameters passed to skill")
    reasoning: str = Field(..., description="LLM explanation for skill selection")
    rag_context: Optional[RAGContext] = Field(
        default=None,
        description="RAG context used (for debugging)"
    )


class ChartValidateRequest(BaseModel):
    """Request to validate skill parameters without executing."""
    skill_id: str
    parameters: dict


class ChartValidateResponse(BaseModel):
    """Validation result."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    sanitized_parameters: Optional[dict] = None


class SkillInfo(BaseModel):
    """Information about an available skill."""
    id: str
    name: str
    description: str
    category: str
    parameters_schema: dict
    chart_type: str
    supports_streaming: bool


class SkillListResponse(BaseModel):
    """List of available skills."""
    skills: list[SkillInfo]


class StreamMessage(BaseModel):
    """Message format for SSE streaming."""
    type: str = Field(..., description="Message type: data_point, error, complete")
    timestamp: Optional[str] = None
    series: Optional[str] = None
    value: Optional[Any] = None
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None
    suggestions: Optional[list[str]] = None
