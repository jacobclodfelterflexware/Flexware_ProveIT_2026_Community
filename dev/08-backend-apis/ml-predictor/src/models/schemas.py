"""Pydantic schemas for ML Predictor API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ============== Prediction Schemas ==============

class PredictionPoint(BaseModel):
    """A single prediction point with confidence interval."""
    date: str
    value: float
    lower: float
    upper: float


class PredictionMetrics(BaseModel):
    """Model performance metrics."""
    rmse: Optional[float] = None
    mae: Optional[float] = None
    mape: Optional[float] = None


class PredictionResponse(BaseModel):
    """Response for time series prediction endpoint."""
    machine_id: str = Field(..., alias="machineId")
    field: str
    topic: str
    horizon: str  # "week" or "month"
    predictions: list[PredictionPoint]
    historical: list[PredictionPoint]  # Recent historical data for context
    metrics: PredictionMetrics
    trained_at: Optional[datetime] = Field(None, alias="trainedAt")
    data_points_used: int = Field(..., alias="dataPointsUsed")

    class Config:
        populate_by_name = True


class PredictionRequest(BaseModel):
    """Request body for triggering prediction training."""
    fields: Optional[list[str]] = None  # If None, predict all numeric fields
    horizon: str = "week"  # "week" or "month"


# ============== Regression Schemas ==============

class FeatureInfo(BaseModel):
    """Information about a feature in regression model."""
    machine_id: str = Field(..., alias="machineId")
    machine_name: Optional[str] = Field(None, alias="machineName")
    topic: str
    field: str
    coefficient: float
    p_value: Optional[float] = Field(None, alias="pValue")
    importance: Optional[float] = None


class RegressionResponse(BaseModel):
    """Response for regression analysis endpoint."""
    machine_id: str = Field(..., alias="machineId")
    target_field: str = Field(..., alias="targetField")
    target_topic: str = Field(..., alias="targetTopic")
    features: list[FeatureInfo]
    intercept: float
    r_squared: float = Field(..., alias="rSquared")
    correlation_matrix: dict  # field -> {field -> correlation}
    trained_at: Optional[datetime] = Field(None, alias="trainedAt")
    data_points_used: int = Field(..., alias="dataPointsUsed")

    class Config:
        populate_by_name = True


class RegressionRequest(BaseModel):
    """Request body for regression analysis."""
    target_field: str = Field(..., alias="targetField")
    target_topic: str = Field(..., alias="targetTopic")
    include_similar: bool = Field(True, alias="includeSimilar")
    additional_machine_ids: Optional[list[str]] = Field(None, alias="additionalMachineIds")


# ============== Training Schemas ==============

class TrainingRequest(BaseModel):
    """Request to trigger model training."""
    prediction: bool = True
    regression: bool = True
    fields: Optional[list[str]] = None  # If None, train for all numeric fields


class TrainingResponse(BaseModel):
    """Response after training is triggered."""
    machine_id: str = Field(..., alias="machineId")
    status: str  # "started", "completed", "failed"
    message: str
    prediction_trained: bool = Field(False, alias="predictionTrained")
    regression_trained: bool = Field(False, alias="regressionTrained")


# ============== Correlation Schemas ==============

class CorrelationEntry(BaseModel):
    """A single correlation between two fields."""
    source_machine_id: str = Field(..., alias="sourceMachineId")
    source_machine_name: Optional[str] = Field(None, alias="sourceMachineName")
    source_topic: str = Field(..., alias="sourceTopic")
    source_field: str = Field(..., alias="sourceField")
    target_field: str = Field(..., alias="targetField")
    correlation: float
    p_value: Optional[float] = Field(None, alias="pValue")


class CorrelationsResponse(BaseModel):
    """Response for correlation analysis."""
    machine_id: str = Field(..., alias="machineId")
    field: str
    correlations: list[CorrelationEntry]

    class Config:
        populate_by_name = True


# ============== Machine Info Schemas ==============

class FieldDefinition(BaseModel):
    """Definition of a machine field."""
    name: str
    type: str
    formula: Optional[str] = None
    static_value: Optional[str] = None
    description: Optional[str] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class TopicDefinition(BaseModel):
    """Definition of a topic with its fields."""
    topic_path: str
    fields: list[FieldDefinition]


class MachineDefinition(BaseModel):
    """Machine definition from machine-simulator."""
    id: Optional[str] = None
    name: str
    description: Optional[str] = None
    machine_type: Optional[str] = None
    topic_path: Optional[str] = None
    fields: Optional[list[FieldDefinition]] = None
    topics: Optional[list[TopicDefinition]] = None
    publish_interval_ms: int = 5000
    status: str = "draft"
    similarity_results: Optional[list[dict]] = None


# ============== Health Check ==============

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    neo4j_connected: bool
    version: str = "1.0.0"
