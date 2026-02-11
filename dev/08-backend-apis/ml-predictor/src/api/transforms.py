"""View Transform API - LLM-generated ETL schemas for topic-to-machine-view mapping."""

import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from openai import OpenAI

from src.config import get_settings
from src.database import get_neo4j_driver

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/transforms")


# ============================================================================
# Pydantic Models
# ============================================================================

class FieldMapping(BaseModel):
    """Maps a source field to a target field in the view model."""
    source: str  # e.g., "chemical_dosage.value" or "temperature"
    target: str  # e.g., "chemical_dosage" (clean name for display)
    type: str    # "number", "integer", "string", "boolean"
    description: Optional[str] = None


class ViewTransformSchema(BaseModel):
    """The LLM-generated schema for transforming topic data to view model."""
    machineId: str
    machineName: str
    machineType: Optional[str] = None
    description: Optional[str] = None
    fieldMappings: list[FieldMapping]
    numericFields: list[str]  # List of target field names that are numeric
    primaryMetric: Optional[str] = None  # Suggested primary metric for similarity


class ViewTransform(BaseModel):
    """Complete view transform stored in Neo4j."""
    transformId: str
    sourceTopicPath: str
    schema: ViewTransformSchema
    createdAt: Optional[str] = None
    createdBy: str = "gpt-4o-mini"
    promptVersion: str = "v1"


class TopicStructure(BaseModel):
    """Input structure describing a topic for transform generation."""
    topicPath: str
    isAggregated: bool = False
    payload: Optional[dict] = None
    numericFields: Optional[list[str]] = None
    childTopics: Optional[list[str]] = None
    childPayloads: Optional[dict[str, dict]] = None


class GenerateTransformRequest(BaseModel):
    """Request to generate a view transform for a topic."""
    topicStructure: TopicStructure


class GenerateTransformResponse(BaseModel):
    """Response containing the generated view transform."""
    transform: ViewTransform
    cached: bool = False


# ============================================================================
# LLM Prompt
# ============================================================================

TRANSFORM_SYSTEM_PROMPT = """You are an ETL schema generator for industrial IoT data visualization.

Your task is to create a JSON schema that maps raw MQTT topic data to a standardized view model format.

The view model must conform to this TypeScript interface:

```typescript
interface MachineDefinition {
  id: string;           // Use the topic path
  name: string;         // Human-readable name derived from topic
  description?: string; // Brief description of what this data represents
  machine_type?: string; // Category (e.g., "sensor", "pump", "motor")
  topics: TopicDefinition[];
  publish_interval_ms: number;  // Default to 5000
  status: 'running';
  fields: FieldDefinition[];
}

interface FieldDefinition {
  name: string;  // Clean field name for display
  type: 'number' | 'integer' | 'string' | 'boolean';
  description?: string;
}
```

Generate a JSON object with these properties:
- machineId: The topic path
- machineName: A human-readable name (convert underscores/dashes to spaces, title case)
- machineType: Inferred category based on the topic/field names
- description: Brief description
- fieldMappings: Array of {source, target, type, description} mappings
  - source: The exact path to the value in the raw payload (e.g., "temperature" or "sensor.value")
  - target: Clean name for display (e.g., "Temperature")
  - type: "number", "integer", "string", or "boolean"
  - description: Brief description of the field
- numericFields: Array of target field names that are numeric (for charting)
- primaryMetric: The most important numeric field (for similarity analysis)

Rules:
1. Only include fields that have actual values in the payload
2. Prioritize numeric fields for charting
3. Use Title Case for target field names
4. Infer meaningful descriptions from field and topic names
5. Return ONLY valid JSON, no markdown or explanation"""

TRANSFORM_USER_PROMPT = """Generate a view transform schema for this topic:

TOPIC PATH: {topic_path}

{payload_section}

Return a JSON object with machineId, machineName, machineType, description, fieldMappings, numericFields, and primaryMetric."""


# ============================================================================
# Helper Functions
# ============================================================================

def _get_openai_client() -> OpenAI:
    """Get OpenAI client instance."""
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")
    return OpenAI(api_key=settings.openai_api_key)


def _format_payload_section(structure: TopicStructure) -> str:
    """Format the payload section for the LLM prompt."""
    if structure.isAggregated and structure.childPayloads:
        lines = ["AGGREGATED FROM CHILD TOPICS:"]
        for child_path, payload in structure.childPayloads.items():
            child_name = child_path.split('/')[-1] if '/' in child_path else child_path
            lines.append(f"\n  {child_name}:")
            lines.append(f"    Payload: {json.dumps(payload, indent=4)}")
        return "\n".join(lines)
    elif structure.payload:
        return f"PAYLOAD:\n{json.dumps(structure.payload, indent=2)}\n\nNUMERIC FIELDS: {structure.numericFields or []}"
    else:
        return "NO PAYLOAD DATA AVAILABLE"


def _clean_llm_response(content: str) -> str:
    """Clean markdown formatting from LLM response."""
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    elif content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]

    # Find JSON object boundaries
    start = content.find('{')
    end = content.rfind('}')
    if start != -1 and end != -1 and end > start:
        content = content[start:end+1]

    return content.strip()


async def _generate_transform_with_llm(structure: TopicStructure) -> ViewTransformSchema:
    """Call GPT to generate a view transform schema."""
    settings = get_settings()
    client = _get_openai_client()

    payload_section = _format_payload_section(structure)
    user_prompt = TRANSFORM_USER_PROMPT.format(
        topic_path=structure.topicPath,
        payload_section=payload_section
    )

    logger.info(f"Generating transform for topic: {structure.topicPath}")
    logger.debug(f"User prompt: {user_prompt[:500]}...")

    response = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=2048,
        messages=[
            {"role": "system", "content": TRANSFORM_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.choices[0].message.content
    logger.debug(f"LLM response: {content}")

    clean_content = _clean_llm_response(content)
    data = json.loads(clean_content)

    # Parse into ViewTransformSchema
    field_mappings = [
        FieldMapping(
            source=fm.get("source", ""),
            target=fm.get("target", ""),
            type=fm.get("type", "string"),
            description=fm.get("description")
        )
        for fm in data.get("fieldMappings", [])
    ]

    return ViewTransformSchema(
        machineId=data.get("machineId", structure.topicPath),
        machineName=data.get("machineName", structure.topicPath.split('/')[-1]),
        machineType=data.get("machineType"),
        description=data.get("description"),
        fieldMappings=field_mappings,
        numericFields=data.get("numericFields", []),
        primaryMetric=data.get("primaryMetric")
    )


# ============================================================================
# Neo4j Operations
# ============================================================================

async def _get_existing_transform(topic_path: str) -> Optional[ViewTransform]:
    """Check if a transform already exists for this topic."""
    driver = get_neo4j_driver()
    if not driver:
        return None

    query = """
    MATCH (t:Topic {path: $topicPath})-[:HAS_VIEW_TRANSFORM]->(vt:ViewTransform)
    RETURN vt.transformId AS transformId,
           vt.schema AS schema,
           vt.createdAt AS createdAt,
           vt.createdBy AS createdBy,
           vt.promptVersion AS promptVersion
    LIMIT 1
    """

    async with driver.session() as session:
        result = await session.run(query, {"topicPath": topic_path})
        record = await result.single()

        if record:
            schema_str = record["schema"]
            schema_data = json.loads(schema_str) if isinstance(schema_str, str) else schema_str

            return ViewTransform(
                transformId=record["transformId"],
                sourceTopicPath=topic_path,
                schema=ViewTransformSchema(**schema_data),
                createdAt=str(record["createdAt"]) if record["createdAt"] else None,
                createdBy=record["createdBy"] or "gpt-4o-mini",
                promptVersion=record["promptVersion"] or "v1"
            )

    return None


async def _save_transform(topic_path: str, schema: ViewTransformSchema) -> ViewTransform:
    """Save a new view transform to Neo4j."""
    driver = get_neo4j_driver()
    if not driver:
        raise HTTPException(status_code=500, detail="Database connection unavailable")

    transform_id = str(uuid.uuid4())
    schema_json = schema.model_dump_json()

    query = """
    MATCH (t:Topic {path: $topicPath})
    CREATE (vt:ViewTransform {
        transformId: $transformId,
        schema: $schema,
        createdAt: datetime(),
        createdBy: $createdBy,
        promptVersion: $promptVersion
    })
    CREATE (t)-[:HAS_VIEW_TRANSFORM]->(vt)
    RETURN vt.createdAt AS createdAt
    """

    async with driver.session() as session:
        result = await session.run(query, {
            "topicPath": topic_path,
            "transformId": transform_id,
            "schema": schema_json,
            "createdBy": "gpt-4o-mini",
            "promptVersion": "v1"
        })
        record = await result.single()

        if not record:
            raise HTTPException(status_code=404, detail=f"Topic not found: {topic_path}")

        return ViewTransform(
            transformId=transform_id,
            sourceTopicPath=topic_path,
            schema=schema,
            createdAt=str(record["createdAt"]) if record["createdAt"] else None,
            createdBy="gpt-4o-mini",
            promptVersion="v1"
        )


async def _delete_existing_transform(topic_path: str) -> bool:
    """Delete existing transform for a topic (for regeneration)."""
    driver = get_neo4j_driver()
    if not driver:
        return False

    query = """
    MATCH (t:Topic {path: $topicPath})-[r:HAS_VIEW_TRANSFORM]->(vt:ViewTransform)
    DELETE r, vt
    RETURN count(vt) AS deleted
    """

    async with driver.session() as session:
        result = await session.run(query, {"topicPath": topic_path})
        record = await result.single()
        return record and record["deleted"] > 0


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/{topic_path:path}")
async def get_transform(topic_path: str) -> Optional[ViewTransform]:
    """Get existing view transform for a topic."""
    transform = await _get_existing_transform(topic_path)
    if not transform:
        raise HTTPException(status_code=404, detail=f"No transform found for topic: {topic_path}")
    return transform


@router.post("/generate")
async def generate_transform(
    request: GenerateTransformRequest,
    force_regenerate: bool = Query(False, description="Force regeneration even if cached")
) -> GenerateTransformResponse:
    """Generate a view transform for a topic using GPT.

    If a transform already exists and force_regenerate is False, returns the cached version.
    """
    topic_path = request.topicStructure.topicPath

    # Check for existing transform
    if not force_regenerate:
        existing = await _get_existing_transform(topic_path)
        if existing:
            logger.info(f"Using cached transform for: {topic_path}")
            return GenerateTransformResponse(transform=existing, cached=True)
    else:
        # Delete existing transform if force regenerating
        await _delete_existing_transform(topic_path)

    # Generate new transform with LLM
    try:
        schema = await _generate_transform_with_llm(request.topicStructure)
        transform = await _save_transform(topic_path, schema)
        logger.info(f"Generated and saved new transform for: {topic_path}")
        return GenerateTransformResponse(transform=transform, cached=False)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse LLM response as JSON")
    except Exception as e:
        logger.error(f"Transform generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{topic_path:path}")
async def delete_transform(topic_path: str) -> dict:
    """Delete a view transform for a topic."""
    deleted = await _delete_existing_transform(topic_path)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No transform found for topic: {topic_path}")
    return {"deleted": True, "topicPath": topic_path}
