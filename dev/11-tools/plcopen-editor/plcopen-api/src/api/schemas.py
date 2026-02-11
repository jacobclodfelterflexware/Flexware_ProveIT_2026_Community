"""Pydantic schemas for API requests and responses."""
from typing import Optional, List

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str


class ValidationError(BaseModel):
    """Schema for a validation error."""

    line: Optional[int] = None
    column: Optional[int] = None
    message: str
    element: Optional[str] = None


class ValidationResult(BaseModel):
    """Response schema for XML validation."""

    is_valid: bool
    errors: List[ValidationError] = []
    warnings: List[str] = []


class VariableSummary(BaseModel):
    """Summary of a variable declaration."""

    name: str
    type: str
    scope: str  # input, output, local, inOut


class POUSummary(BaseModel):
    """Summary of a Program Organization Unit."""

    name: str
    pou_type: str  # program, function, functionBlock
    language: str  # FBD, LD, SFC, ST, IL
    variables: List[VariableSummary] = []


class ConfigurationSummary(BaseModel):
    """Summary of a configuration."""

    name: str
    resources: List[str] = []


class ProjectSummary(BaseModel):
    """Summary of parsed PLCopen project."""

    name: str
    company_name: Optional[str] = None
    product_name: Optional[str] = None
    product_version: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    pous: List[POUSummary] = []
    configurations: List[ConfigurationSummary] = []
    data_types: List[str] = []


class ImportResult(BaseModel):
    """Response schema for XML import."""

    success: bool
    message: str
    project: Optional[ProjectSummary] = None


class StoredProject(BaseModel):
    """Metadata for a stored project."""

    id: str
    name: str
    created_at: str
    updated_at: str


class ProjectListResponse(BaseModel):
    """Response schema for project list."""

    projects: List[StoredProject] = []


class SaveProjectRequest(BaseModel):
    """Request schema for saving a project."""

    name: str
    xml_content: str


class SaveProjectResponse(BaseModel):
    """Response schema for saving a project."""

    success: bool
    message: str
    project: Optional[StoredProject] = None
