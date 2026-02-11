"""PLCopen XML import/export endpoints."""
from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from services.xml_validator import PLCopenValidator
from services.xml_parser import PLCopenParser
from services.project_store import get_project_store
from .schemas import (
    ValidationResult,
    ImportResult,
    ProjectListResponse,
    StoredProject,
    SaveProjectRequest,
    SaveProjectResponse,
)

router = APIRouter(prefix="/plcopen", tags=["PLCopen XML"])
logger = logging.getLogger(__name__)


@router.post(
    "/validate",
    response_model=ValidationResult,
    summary="Validate PLCopen XML",
    description="Validate PLCopen XML structure without storing. Returns validation status and any errors found.",
)
async def validate_xml(request: Request):
    """
    Validate PLCopen XML structure.

    Accepts raw PLCopen XML in the request body.
    Returns validation status with detailed error messages if invalid.
    """
    content_type = request.headers.get("content-type", "")
    if (
        "xml" not in content_type.lower()
        and "text/plain" not in content_type.lower()
        and "application/octet-stream" not in content_type.lower()
    ):
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/xml, text/xml, or text/plain",
        )

    try:
        body = await request.body()
        xml_content = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 encoding")

    if not xml_content.strip():
        raise HTTPException(status_code=400, detail="Empty XML content")

    validator = PLCopenValidator()
    result = validator.validate(xml_content)

    return result


@router.post(
    "/import",
    response_model=ImportResult,
    summary="Import PLCopen XML",
    description="Import and parse PLCopen XML. Returns parsed structure summary.",
)
async def import_xml(request: Request):
    """
    Import PLCopen XML and return parsed structure.

    Accepts raw PLCopen XML in the request body.
    Validates the XML and returns a summary of the parsed project structure.
    """
    content_type = request.headers.get("content-type", "")
    if (
        "xml" not in content_type.lower()
        and "text/plain" not in content_type.lower()
        and "application/octet-stream" not in content_type.lower()
    ):
        raise HTTPException(
            status_code=415,
            detail="Content-Type must be application/xml, text/xml, or text/plain",
        )

    try:
        body = await request.body()
        xml_content = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 encoding")

    if not xml_content.strip():
        raise HTTPException(status_code=400, detail="Empty XML content")

    # Validate first
    validator = PLCopenValidator()
    validation = validator.validate(xml_content)

    if not validation.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid PLCopen XML",
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    # Parse the XML
    parser = PLCopenParser()
    try:
        project = parser.parse(xml_content)
    except Exception as e:
        logger.error(f"Failed to parse XML: {e}")
        raise HTTPException(status_code=422, detail=f"Parse error: {str(e)}")

    return ImportResult(success=True, message="XML imported successfully", project=project)


@router.post(
    "/export",
    response_class=PlainTextResponse,
    summary="Export PLCopen XML",
    description="Generate PLCopen XML from provided project data or return template.",
)
async def export_xml(
    request: Request,
    template: bool = False,
    project_name: Optional[str] = "NewProject",
):
    """
    Export PLCopen XML.

    If template=true, returns an empty PLCopen project template.
    Otherwise, accepts PLCopen XML and normalizes/re-serializes it.
    """
    parser = PLCopenParser()

    if template:
        # Return empty project template
        xml_content = parser.create_empty_project(project_name)
        return Response(
            content=xml_content,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="{project_name}.xml"'},
        )

    # For non-template export, accept XML and re-serialize (round-trip)
    # This validates and normalizes the XML
    try:
        body = await request.body()
        xml_content = body.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid UTF-8 encoding")

    if not xml_content.strip():
        raise HTTPException(status_code=400, detail="Empty content")

    # Validate and re-serialize
    validator = PLCopenValidator()
    validation = validator.validate(xml_content)

    if not validation.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid PLCopen XML",
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    # Parse and re-export (normalizes the XML)
    normalized_xml = parser.normalize(xml_content)

    return Response(content=normalized_xml, media_type="application/xml")


@router.get(
    "/projects",
    response_model=ProjectListResponse,
    summary="List all stored projects",
    description="Get a list of all PLCopen XML projects stored on the server.",
)
async def list_projects():
    """List all stored projects."""
    store = get_project_store()
    projects = store.list_projects()
    return ProjectListResponse(
        projects=[StoredProject(**p) for p in projects]
    )


@router.post(
    "/projects",
    response_model=SaveProjectResponse,
    summary="Save a project",
    description="Save a PLCopen XML project to the server.",
)
async def save_project(request: SaveProjectRequest):
    """Save a project to storage."""
    # Validate the XML first
    validator = PLCopenValidator()
    validation = validator.validate(request.xml_content)

    if not validation.is_valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid PLCopen XML",
                "errors": [e.model_dump() for e in validation.errors],
            },
        )

    store = get_project_store()
    try:
        project_meta = store.save_project(
            xml_content=request.xml_content,
            name=request.name,
        )
        return SaveProjectResponse(
            success=True,
            message="Project saved successfully",
            project=StoredProject(**project_meta),
        )
    except Exception as e:
        logger.error(f"Failed to save project: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save project: {str(e)}")


@router.get(
    "/projects/{project_id}",
    response_class=PlainTextResponse,
    summary="Get a project's XML",
    description="Get the PLCopen XML content of a stored project.",
)
async def get_project(project_id: str):
    """Get a project's XML content by ID."""
    store = get_project_store()
    xml_content = store.get_project(project_id)

    if xml_content is None:
        raise HTTPException(status_code=404, detail="Project not found")

    return Response(
        content=xml_content,
        media_type="application/xml",
    )


@router.delete(
    "/projects/{project_id}",
    summary="Delete a project",
    description="Delete a stored project by ID.",
)
async def delete_project(project_id: str):
    """Delete a project by ID."""
    store = get_project_store()
    deleted = store.delete_project(project_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"success": True, "message": "Project deleted successfully"}
