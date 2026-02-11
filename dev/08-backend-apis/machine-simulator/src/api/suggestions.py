"""Suggestion API endpoints for schema, formulas, and intervals."""

import json
import logging
from typing import Optional, Any
from pydantic import BaseModel, Field
import httpx

from fastapi import APIRouter, HTTPException

from ..config import config
from ..models import FieldDefinition, FieldType
from ..services import machine_store
from ..services.llm_generator import llm_generator
from ..prompts import (
    FORMULA_SUGGESTION_SYSTEM_PROMPT,
    FORMULA_SUGGESTION_USER_PROMPT,
    TOPIC_SUGGESTION_SYSTEM_PROMPT,
    TOPIC_SUGGESTION_USER_PROMPT,
    UNIFIED_SUGGESTION_SYSTEM_PROMPT,
    UNIFIED_SUGGESTION_USER_PROMPT,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/suggestions", tags=["suggestions"])


# ============== Request/Response Models ==============

class SchemaSuggestionRequest(BaseModel):
    """Request for schema suggestion."""
    topic_path: str = Field(..., description="Target topic path")
    fields: list[FieldDefinition] = Field(..., description="Current field definitions")


class SimilarSchemaResult(BaseModel):
    """A single similar schema/message result."""
    topic_path: str
    similarity: float
    field_names: list[str]
    proposal_id: Optional[str] = None
    proposal_name: Optional[str] = None


class SchemaSuggestionResponse(BaseModel):
    """Response with schema suggestion."""
    suggested_fields: list[FieldDefinition]
    based_on: str  # 'similar_schema' | 'original' | 'no_match'
    similar_results: list[SimilarSchemaResult] = []  # Top 20 similar results
    overall_confidence: float = 0.0  # 0-1 confidence score
    confidence: str = "low"  # 'high' | 'medium' | 'low'


class SimilarTopicContext(BaseModel):
    """Context from a similar topic for formula generation."""
    topic_path: str
    similarity: float
    field_names: list[str]
    historical_payloads: list[dict] = []
    source_field: Optional[str] = None  # For split-by-metric topics


class FormulaSuggestionRequest(BaseModel):
    """Request for formula suggestions."""
    topic_path: str = Field(..., description="Target topic path")
    fields: list[FieldDefinition] = Field(..., description="Field definitions needing formulas")
    machine_name: Optional[str] = Field(None, description="Machine name for asset_id default")
    similar_topics: Optional[list[SimilarTopicContext]] = Field(None, description="Similar topics with historical context")
    source_field: Optional[str] = Field(None, description="Source field name for split-by-metric topics (e.g., 'speed', 'temperature')")


class FieldFormulaSuggestion(BaseModel):
    """Formula suggestion for a single field."""
    field_name: str
    field_type: str = "number"
    formula: Optional[str] = None  # For dynamic fields
    static_value: Optional[str] = None  # For static fields
    is_static: bool = False
    rationale: str
    expected_min: Optional[float] = None
    expected_max: Optional[float] = None


class FormulaSuggestionResponse(BaseModel):
    """Response with formula suggestions."""
    suggestions: list[FieldFormulaSuggestion]
    based_on: str  # 'historical_analysis' | 'field_ranges' | 'default'


class IntervalSuggestionRequest(BaseModel):
    """Request for publish interval suggestion."""
    topic_path: str = Field(..., description="Target topic path")


class IntervalSuggestionResponse(BaseModel):
    """Response with interval suggestion."""
    suggested_interval_ms: int
    min_interval_ms: int
    max_interval_ms: int
    based_on: str  # 'similar_topics' | 'default'
    sample_count: int = 0


class TopicSuggestionRequest(BaseModel):
    """Request for topic path suggestion."""
    machine_type: str = Field(..., description="Type of machine")
    machine_name: str = Field(default="", description="Name of the machine (for unique topic generation)")
    fields: list[FieldDefinition] = Field(..., description="Field definitions")


class SuggestedTopic(BaseModel):
    """A suggested topic path with similarity info."""
    topic_path: str
    similarity: float
    field_names: list[str]


class TopicSuggestionResponse(BaseModel):
    """Response with topic suggestions."""
    suggested_topic: Optional[str] = None
    similar_topics: list[SuggestedTopic] = []
    confidence: str = "low"  # 'high' | 'medium' | 'low'


# ============== Unified Suggestion Models ==============

class UnifiedSuggestionRequest(BaseModel):
    """Request for unified topic + schema suggestion."""
    machine_type: str = Field(..., description="Type of machine")
    machine_name: str = Field(..., description="Name of the machine")
    fields: list[FieldDefinition] = Field(..., description="Original field definitions")


class HistoricalPayload(BaseModel):
    """A historical payload from a topic."""
    payload: dict = Field(default_factory=dict)
    timestamp: Optional[str] = None


class SimilarResult(BaseModel):
    """A similar topic with its field names and historical payloads."""
    topic_path: str
    similarity: float  # Weighted: 60% topic semantic + 40% field Jaccard
    field_names: list[str]
    historical_payloads: list[HistoricalPayload] = []  # Last 10 payloads for top 10 results


class TopicSuggestion(BaseModel):
    """A suggested topic with its fields (for multi-topic machines)."""
    topic_path: str
    fields: list[FieldDefinition] = []
    # Maps which original field this topic represents (e.g., "spindle_speed" -> /speed topic)
    source_field: Optional[str] = None


class UnifiedSuggestionResponse(BaseModel):
    """Response with unified topic + schema suggestion."""
    # Single topic suggestion (backward compat)
    suggested_topic: Optional[str] = None
    suggested_fields: list[FieldDefinition] = []

    # Multi-topic suggestions (when split pattern detected)
    suggested_topics: list[TopicSuggestion] = []

    # Pattern detected from similar topics
    topic_pattern: str = "single"  # "single" | "split_by_metric"

    # Context for UI display
    similar_results: list[SimilarResult] = []
    confidence: str = "low"  # 'high' | 'medium' | 'low'
    overall_similarity: float = 0.0


# ============== Helper Functions ==============

def _analyze_field_values(historical_payloads: list[dict]) -> dict[str, dict]:
    """
    Analyze historical payloads to infer field characteristics.

    Returns a dict mapping field_name -> {
        'inferred_type': 'number'|'integer'|'string'|'boolean',
        'is_dynamic': bool,  # True if value varies across payloads
        'static_value': Any,  # If static, the constant value
        'min_value': float,  # If dynamic numeric, observed min
        'max_value': float,  # If dynamic numeric, observed max
        'sample_values': list,  # Sample of observed values
    }
    """
    if not historical_payloads:
        return {}

    # Collect all values for each field
    field_values: dict[str, list] = {}
    for hp in historical_payloads:
        payload = hp.get("payload", {}) if isinstance(hp, dict) else {}
        for key, value in payload.items():
            if key not in field_values:
                field_values[key] = []
            field_values[key].append(value)

    # Analyze each field
    result = {}
    for field_name, values in field_values.items():
        if not values:
            continue

        # Determine if static or dynamic
        unique_values = set(str(v) for v in values)  # Convert to str for comparison
        is_dynamic = len(unique_values) > 1

        # Infer type from first non-None value
        sample_value = next((v for v in values if v is not None), None)
        if sample_value is None:
            inferred_type = "string"
        elif isinstance(sample_value, bool):
            inferred_type = "boolean"
        elif isinstance(sample_value, int) and not isinstance(sample_value, bool):
            # Check if values are actually floats stored as ints
            if all(isinstance(v, int) and not isinstance(v, bool) for v in values if v is not None):
                inferred_type = "integer"
            else:
                inferred_type = "number"
        elif isinstance(sample_value, (float, int)):
            inferred_type = "number"
        else:
            inferred_type = "string"

        analysis = {
            "inferred_type": inferred_type,
            "is_dynamic": is_dynamic,
            "sample_values": list(unique_values)[:5],  # Keep up to 5 samples
        }

        if is_dynamic:
            # For dynamic numeric fields, capture min/max
            if inferred_type in ("number", "integer"):
                numeric_values = [v for v in values if isinstance(v, (int, float)) and not isinstance(v, bool)]
                if numeric_values:
                    analysis["min_value"] = min(numeric_values)
                    analysis["max_value"] = max(numeric_values)
        else:
            # Static field - store the constant value
            analysis["static_value"] = sample_value

        result[field_name] = analysis

    return result


def calculate_jaccard_similarity(keys1: list[str], keys2: list[str]) -> float:
    """Calculate Jaccard similarity between two sets of keys."""
    if not keys1 and not keys2:
        return 1.0
    if not keys1 or not keys2:
        return 0.0

    set1 = set(keys1)
    set2 = set(keys2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)

    return intersection / union if union > 0 else 0.0


def generate_default_formula(field: FieldDefinition) -> tuple[str, str]:
    """Generate a default formula based on field definition."""
    if field.type == FieldType.INTEGER:
        if field.min_value is not None and field.max_value is not None:
            mid = (field.min_value + field.max_value) / 2
            amp = (field.max_value - field.min_value) / 2
            return (
                f"round({mid} + {amp} * sin(t / 300))",
                f"Sinusoidal integer between {int(field.min_value)} and {int(field.max_value)}"
            )
        return "i", "Incrementing counter"

    elif field.type == FieldType.NUMBER:
        if field.min_value is not None and field.max_value is not None:
            mid = (field.min_value + field.max_value) / 2
            amp = (field.max_value - field.min_value) / 2
            return (
                f"{mid} + {amp} * sin(t / 300)",
                f"Sinusoidal value between {field.min_value} and {field.max_value}"
            )
        return "random() * 100", "Random value 0-100"

    elif field.type == FieldType.BOOLEAN:
        return "random() > 0.5", "Random boolean"

    return "t", "Current timestamp"


# ============== Endpoints ==============

@router.post("/schema", response_model=SchemaSuggestionResponse)
async def suggest_schema(request: SchemaSuggestionRequest):
    """
    Suggest schema adjustments based on similar topics in the knowledge graph.

    Returns top 20 similar results for context window analysis.
    If overall confidence is high, generates a normalized schema proposal.
    If confidence is low, the machine is considered "novel" and keeps original fields.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password)
    )

    try:
        current_field_names = [f.name for f in request.fields]

        # Query for topics with bound schemas and their field names
        with driver.session() as session:
            result = session.run("""
                MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
                WHERE t.path <> $topicPath AND m.rawPayload IS NOT NULL
                OPTIONAL MATCH (tb:TopicBinding {topicPath: t.path})
                OPTIONAL MATCH (sp:SchemaProposal {id: tb.proposalId})
                WITH t, m, tb, sp
                ORDER BY m.timestamp DESC
                WITH t.path as topicPath,
                     collect(m.rawPayload)[0] as latestPayload,
                     tb.proposalId as boundProposalId,
                     sp.name as boundProposalName,
                     sp.expectedSchema as boundSchema
                WHERE latestPayload IS NOT NULL
                RETURN topicPath, latestPayload, boundProposalId, boundProposalName, boundSchema
                LIMIT 200
            """, {"topicPath": request.topic_path})

            # Collect all matches with their similarity scores
            all_matches = []

            for record in result:
                payload_str = record["latestPayload"]
                bound_schema = record["boundSchema"]

                try:
                    payload = json.loads(payload_str)
                    if isinstance(payload, dict):
                        payload_keys = list(payload.keys())
                        similarity = calculate_jaccard_similarity(current_field_names, payload_keys)

                        all_matches.append({
                            "topic_path": record["topicPath"],
                            "proposal_id": record["boundProposalId"],
                            "proposal_name": record["boundProposalName"],
                            "schema": bound_schema,
                            "payload_keys": payload_keys,
                            "similarity": similarity,
                        })
                except (json.JSONDecodeError, TypeError):
                    continue

        # Sort by similarity and take top 20
        all_matches.sort(key=lambda x: x["similarity"], reverse=True)
        top_20 = all_matches[:20]

        # Build similar_results for response
        similar_results = [
            SimilarSchemaResult(
                topic_path=m["topic_path"],
                similarity=m["similarity"],
                field_names=m["payload_keys"],
                proposal_id=m["proposal_id"],
                proposal_name=m["proposal_name"],
            )
            for m in top_20
        ]

        # Calculate overall confidence based on top results
        if not top_20:
            overall_confidence = 0.0
        else:
            # Weight top results more heavily
            weights = [1.0 / (i + 1) for i in range(len(top_20))]
            weighted_sum = sum(m["similarity"] * w for m, w in zip(top_20, weights))
            total_weight = sum(weights)
            overall_confidence = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Determine confidence level
        if overall_confidence >= 0.7:
            confidence = "high"
        elif overall_confidence >= 0.4:
            confidence = "medium"
        else:
            confidence = "low"

        # If confidence is high/medium, generate normalized schema from top results
        if confidence in ("high", "medium") and top_20:
            # Count field name occurrences across top results
            field_counts: dict[str, int] = {}
            field_types: dict[str, str] = {}

            for match in top_20:
                for key in match["payload_keys"]:
                    field_counts[key] = field_counts.get(key, 0) + 1

                # Try to get field types from schema if available
                if match["schema"]:
                    try:
                        schema_obj = json.loads(match["schema"])
                        for name, prop in schema_obj.get("properties", {}).items():
                            if name not in field_types:
                                field_types[name] = prop.get("type", "string")
                    except (json.JSONDecodeError, KeyError):
                        pass

            # Include fields that appear in at least 20% of top results
            min_occurrences = max(1, len(top_20) // 5)
            common_fields = [
                (name, count) for name, count in field_counts.items()
                if count >= min_occurrences
            ]
            common_fields.sort(key=lambda x: x[1], reverse=True)

            # Build suggested fields from common fields
            suggested_fields = []
            type_map = {
                "number": FieldType.NUMBER,
                "integer": FieldType.INTEGER,
                "boolean": FieldType.BOOLEAN,
                "string": FieldType.STRING,
            }

            for name, _ in common_fields:
                field_type_str = field_types.get(name, "string")
                suggested_fields.append(FieldDefinition(
                    name=name,
                    type=type_map.get(field_type_str, FieldType.STRING),
                ))

            if suggested_fields:
                return SchemaSuggestionResponse(
                    suggested_fields=suggested_fields,
                    based_on="similar_schema",
                    similar_results=similar_results,
                    overall_confidence=overall_confidence,
                    confidence=confidence,
                )

        # Low confidence or no common fields - novel machine, keep original fields
        return SchemaSuggestionResponse(
            suggested_fields=request.fields,
            based_on="original",
            similar_results=similar_results,
            overall_confidence=overall_confidence,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"Error suggesting schema: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate schema suggestion")
    finally:
        driver.close()


@router.post("/formulas", response_model=FormulaSuggestionResponse)
async def suggest_formulas(request: FormulaSuggestionRequest):
    """
    Suggest formulas for numeric fields and static values for other fields.

    Uses LLM with context from similar topics and historical data to generate
    appropriate formulas and static values.
    """
    try:
        # Build fields info string
        fields_info = ""
        for field in request.fields:
            fields_info += f"- {field.name} ({field.type})"
            if field.min_value is not None or field.max_value is not None:
                fields_info += f" [range: {field.min_value or '?'} - {field.max_value or '?'}]"
            fields_info += "\n"

        # Build context section from similar topics
        context_section = ""
        if request.similar_topics:
            context_section = "Historical context from similar topics:\n"
            for topic in request.similar_topics[:5]:  # Limit to 5 topics
                context_section += f"\nTopic: {topic.topic_path} (similarity: {topic.similarity:.2f})\n"
                context_section += f"Fields: {', '.join(topic.field_names)}\n"
                if topic.historical_payloads:
                    context_section += "Sample payloads:\n"
                    for payload in topic.historical_payloads[:3]:  # Limit to 3 payloads
                        payload_str = json.dumps(payload, separators=(',', ':'))
                        if len(payload_str) > 150:
                            payload_str = payload_str[:150] + "..."
                        context_section += f"  {payload_str}\n"
        else:
            context_section = "No historical context available - use field semantics and industrial patterns."

        # Format the user prompt
        user_prompt = FORMULA_SUGGESTION_USER_PROMPT.format(
            machine_name=request.machine_name or "machine-001",
            topic_path=request.topic_path,
            source_field=request.source_field or "N/A",
            fields_info=fields_info,
            context_section=context_section,
        )

        # Call LLM
        response = await llm_generator.generate(
            system_prompt=FORMULA_SUGGESTION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=2048,
        )

        # Parse JSON response
        response_text = response.strip()
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        parsed = json.loads(response_text)
        suggestions_data = parsed.get("suggestions", [])

        suggestions = []
        for s in suggestions_data:
            suggestions.append(FieldFormulaSuggestion(
                field_name=s.get("field_name", ""),
                field_type=s.get("field_type", "number"),
                formula=s.get("formula"),
                static_value=s.get("static_value"),
                is_static=s.get("is_static", False),
                rationale=s.get("rationale", ""),
                expected_min=s.get("expected_min"),
                expected_max=s.get("expected_max"),
            ))

        return FormulaSuggestionResponse(
            suggestions=suggestions,
            based_on="llm_context_aware",
        )

    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM response as JSON: {e}, falling back to defaults")
        # Fall back to default formula generation
        return _generate_default_formula_response(request)
    except Exception as e:
        logger.error(f"Error generating formula suggestions: {e}")
        # Fall back to default formula generation
        return _generate_default_formula_response(request)


def _generate_default_formula_response(request: FormulaSuggestionRequest) -> FormulaSuggestionResponse:
    """Generate default formulas when LLM fails."""
    suggestions = []

    for field in request.fields:
        if field.name == "timestamp":
            suggestions.append(FieldFormulaSuggestion(
                field_name=field.name,
                field_type=str(field.type),
                formula="t",
                is_static=False,
                rationale="Unix timestamp in seconds",
            ))
        elif field.name == "asset_id":
            suggestions.append(FieldFormulaSuggestion(
                field_name=field.name,
                field_type=str(field.type),
                static_value=request.machine_name or "machine-001",
                is_static=True,
                rationale="Machine identifier",
            ))
        elif field.type in (FieldType.NUMBER, FieldType.INTEGER):
            formula, rationale = generate_default_formula(field)
            suggestions.append(FieldFormulaSuggestion(
                field_name=field.name,
                field_type=str(field.type),
                formula=formula,
                is_static=False,
                rationale=rationale,
                expected_min=field.min_value,
                expected_max=field.max_value,
            ))
        elif field.type == FieldType.BOOLEAN:
            suggestions.append(FieldFormulaSuggestion(
                field_name=field.name,
                field_type=str(field.type),
                formula="random() > 0.5",
                is_static=False,
                rationale="Random boolean value",
            ))
        elif field.type == FieldType.STRING:
            suggestions.append(FieldFormulaSuggestion(
                field_name=field.name,
                field_type=str(field.type),
                static_value=field.name,
                is_static=True,
                rationale=f"Static string value for {field.name}",
            ))

    return FormulaSuggestionResponse(
        suggestions=suggestions,
        based_on="default",
    )


@router.post("/interval", response_model=IntervalSuggestionResponse)
async def suggest_interval(request: IntervalSuggestionRequest):
    """
    Suggest publish interval based on similar topics' message frequencies.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password)
    )

    try:
        # Query for message timestamps from similar topics
        with driver.session() as session:
            result = session.run("""
                MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
                WHERE t.path STARTS WITH split($topicPath, '/')[0]
                AND t.path <> $topicPath
                WITH t, m
                ORDER BY m.timestamp DESC
                WITH t.path as topicPath, collect(m.timestamp)[0..10] as timestamps
                WHERE size(timestamps) > 1
                RETURN topicPath, timestamps
                LIMIT 20
            """, {"topicPath": request.topic_path})

            intervals = []
            for record in result:
                timestamps = record["timestamps"]
                # Calculate intervals between consecutive messages
                for i in range(len(timestamps) - 1):
                    try:
                        t1 = timestamps[i]
                        t2 = timestamps[i + 1]
                        if hasattr(t1, 'timestamp') and hasattr(t2, 'timestamp'):
                            interval_ms = int((t1.timestamp() - t2.timestamp()) * 1000)
                            if 100 <= interval_ms <= 60000:  # Reasonable bounds
                                intervals.append(interval_ms)
                    except (TypeError, ValueError):
                        continue

        if intervals:
            # Use median interval
            sorted_intervals = sorted(intervals)
            median_idx = len(sorted_intervals) // 2
            suggested = sorted_intervals[median_idx]

            return IntervalSuggestionResponse(
                suggested_interval_ms=suggested,
                min_interval_ms=min(intervals),
                max_interval_ms=max(intervals),
                based_on="similar_topics",
                sample_count=len(intervals),
            )

        # Default suggestion
        return IntervalSuggestionResponse(
            suggested_interval_ms=5000,
            min_interval_ms=1000,
            max_interval_ms=60000,
            based_on="default",
            sample_count=0,
        )

    except Exception as e:
        logger.error(f"Error suggesting interval: {e}")
        # Return default on error
        return IntervalSuggestionResponse(
            suggested_interval_ms=5000,
            min_interval_ms=1000,
            max_interval_ms=60000,
            based_on="default",
            sample_count=0,
        )
    finally:
        driver.close()


@router.post("/topic", response_model=TopicSuggestionResponse)
async def suggest_topic(request: TopicSuggestionRequest):
    """
    Suggest topic path based on similar machines in the knowledge graph.

    Uses weighted similarity:
    - 30% field name Jaccard similarity
    - 70% topic path semantic similarity (via embeddings)
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password)
    )

    try:
        current_field_names = [f.name for f in request.fields]

        # 1. Get semantic topic similarity from ingestor API
        semantic_scores: dict[str, float] = {}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{config.ingestor_url}/api/similar-topics",
                    params={"q": request.machine_type, "k": 100}
                )
                if response.status_code == 200:
                    data = response.json()
                    for result in data.get("results", []):
                        # Ingestor returns 'path' and 'score' fields
                        topic = result.get("path") or result.get("topic") or result.get("topicPath")
                        similarity = result.get("score") or result.get("similarity") or 0.0
                        if topic:
                            semantic_scores[topic] = similarity
                    logger.info(f"Got {len(semantic_scores)} semantic scores for '{request.machine_type}'")
        except Exception as e:
            logger.warning(f"Failed to get semantic similarity from ingestor: {e}")
            # Continue with field similarity only

        # 2. Get topics with payloads from Neo4j
        with driver.session() as session:
            result = session.run("""
                MATCH (t:Topic)-[:HAS_MESSAGE]->(m:Message)
                WITH t, m
                ORDER BY m.timestamp DESC
                WITH t.path as topicPath, collect(m.rawPayload)[0] as latestPayload
                WHERE latestPayload IS NOT NULL
                RETURN topicPath, latestPayload
                LIMIT 200
            """)

            # 3. Calculate weighted similarity for each topic
            matches = []
            for record in result:
                payload_str = record["latestPayload"]
                topic_path = record["topicPath"]

                try:
                    payload = json.loads(payload_str)
                    if isinstance(payload, dict):
                        payload_keys = list(payload.keys())

                        # Field name similarity (Jaccard)
                        field_sim = calculate_jaccard_similarity(current_field_names, payload_keys)

                        # Topic semantic similarity (from embeddings)
                        topic_sim = semantic_scores.get(topic_path, 0.0)

                        # Weighted combination: 30% field, 70% topic semantic
                        weighted_similarity = (0.3 * field_sim) + (0.7 * topic_sim)

                        matches.append({
                            "topic_path": topic_path,
                            "similarity": weighted_similarity,
                            "field_similarity": field_sim,
                            "topic_similarity": topic_sim,
                            "field_names": payload_keys,
                        })
                except (json.JSONDecodeError, TypeError):
                    continue

        # 4. Sort by weighted similarity
        matches.sort(key=lambda x: x["similarity"], reverse=True)
        top_matches = matches[:20]

        # Build response
        similar_topics = [
            SuggestedTopic(
                topic_path=m["topic_path"],
                similarity=m["similarity"],
                field_names=m["field_names"],
            )
            for m in top_matches
        ]

        # Determine confidence based on similarity scores
        if top_matches and top_matches[0]["similarity"] >= 0.7:
            confidence = "high"
        elif top_matches and top_matches[0]["similarity"] >= 0.4:
            confidence = "medium"
        else:
            confidence = "low"

        # 5. Use LLM to generate a UNIQUE topic path based on similar topics context
        suggested_topic = None
        if top_matches:
            try:
                # Format similar topics for LLM context
                similar_topics_text = "\n".join([
                    f"- {m['topic_path']} (similarity: {m['similarity']:.2f})"
                    for m in top_matches[:10]  # Top 10 for context
                ])

                # Format fields for LLM
                fields_text = ", ".join([f.name for f in request.fields])

                # Build user prompt
                user_prompt = TOPIC_SUGGESTION_USER_PROMPT.format(
                    machine_type=request.machine_type,
                    machine_name=request.machine_name or "unnamed",
                    fields=fields_text,
                    similar_topics=similar_topics_text,
                )

                # Call LLM to generate unique topic
                llm_response = await llm_generator.generate(
                    system_prompt=TOPIC_SUGGESTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=256,
                )

                # Extract the topic path (should be just the path, no quotes or explanation)
                if llm_response:
                    suggested_topic = llm_response.strip().strip('"').strip("'")
                    logger.info(f"LLM suggested topic: {suggested_topic}")
            except Exception as e:
                logger.warning(f"Failed to generate topic via LLM: {e}")
                # Fall back to None - user can pick from similar topics

        return TopicSuggestionResponse(
            suggested_topic=suggested_topic,
            similar_topics=similar_topics,
            confidence=confidence,
        )

    except Exception as e:
        logger.error(f"Error suggesting topic: {e}")
        return TopicSuggestionResponse(
            suggested_topic=None,
            similar_topics=[],
            confidence="low",
        )
    finally:
        driver.close()


@router.post("/unified", response_model=UnifiedSuggestionResponse)
async def suggest_unified(request: UnifiedSuggestionRequest):
    """
    Unified topic + schema suggestion endpoint.

    Performs weighted similarity search (60% topic semantic + 40% field Jaccard),
    fetches historical payloads for top results, and uses LLM to suggest both
    a unique topic path and conformant field names.
    """
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.neo4j_uri,
        auth=(config.neo4j_user, config.neo4j_password)
    )

    try:
        current_field_names = [f.name for f in request.fields]

        # 1. Get semantic topic similarity from ingestor API (top 200 results)
        semantic_scores: dict[str, float] = {}
        similar_topic_paths: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{config.ingestor_url}/api/similar-topics",
                    params={"q": request.machine_type, "k": 200}
                )
                if response.status_code == 200:
                    data = response.json()
                    for result in data.get("results", []):
                        topic = result.get("path") or result.get("topic") or result.get("topicPath")
                        similarity = result.get("score") or result.get("similarity") or 0.0
                        if topic:
                            semantic_scores[topic] = similarity
                            similar_topic_paths.append(topic)
                    logger.info(f"Got {len(semantic_scores)} semantic scores for '{request.machine_type}'")
        except Exception as e:
            logger.warning(f"Failed to get semantic similarity from ingestor: {e}")

        # 2. Get latest payloads ONLY for similar topics (optimized query using index)
        with driver.session() as session:
            # Only query topics that came from similarity search - uses topic_path_unique index
            result = session.run("""
                UNWIND $topicPaths AS targetPath
                MATCH (t:Topic {path: targetPath})-[:HAS_MESSAGE]->(m:Message)
                WITH t, m
                ORDER BY m.timestamp DESC
                WITH t.path as topicPath, collect(m.rawPayload)[0] as latestPayload
                WHERE latestPayload IS NOT NULL
                RETURN topicPath, latestPayload
            """, {"topicPaths": similar_topic_paths})

            # 3. Calculate weighted similarity for each topic (60% semantic, 40% field)
            matches = []
            for record in result:
                payload_str = record["latestPayload"]
                topic_path = record["topicPath"]

                try:
                    payload = json.loads(payload_str)
                    if isinstance(payload, dict):
                        payload_keys = list(payload.keys())

                        # Field name similarity (Jaccard) - 20% weight (light tiebreaker)
                        field_sim = calculate_jaccard_similarity(current_field_names, payload_keys)

                        # Topic semantic similarity - 80% weight (dominant factor)
                        topic_sim = semantic_scores.get(topic_path, 0.0)

                        # Weighted combination: 20% field + 80% topic semantic
                        weighted_similarity = (0.2 * field_sim) + (0.8 * topic_sim)

                        matches.append({
                            "topic_path": topic_path,
                            "similarity": weighted_similarity,
                            "field_similarity": field_sim,
                            "topic_similarity": topic_sim,
                            "field_names": payload_keys,
                        })
                except (json.JSONDecodeError, TypeError):
                    continue

        # 4. Sort by weighted similarity and take top 20
        matches.sort(key=lambda x: x["similarity"], reverse=True)

        # Supplement with pure semantic matches if fewer than 10 results
        # (topics without payloads in Neo4j still provide useful context)
        if len(matches) < 10:
            existing_topics = {m["topic_path"] for m in matches}
            for topic, score in sorted(semantic_scores.items(), key=lambda x: x[1], reverse=True):
                if topic not in existing_topics:
                    matches.append({
                        "topic_path": topic,
                        "similarity": score * 0.8,  # Semantic component only (80% weight)
                        "field_similarity": 0.0,
                        "topic_similarity": score,
                        "field_names": [],
                    })
                    if len(matches) >= 10:
                        break

        top_matches = matches[:20]

        # 5. Fetch historical payloads for top 10 results
        for i, match in enumerate(top_matches[:10]):
            with driver.session() as session:
                hist_result = session.run("""
                    MATCH (t:Topic {path: $topicPath})-[:HAS_MESSAGE]->(m:Message)
                    WHERE m.rawPayload IS NOT NULL
                    RETURN m.rawPayload as payload, m.timestamp as timestamp
                    ORDER BY m.timestamp DESC
                    LIMIT 10
                """, {"topicPath": match["topic_path"]})

                historical = []
                for rec in hist_result:
                    try:
                        payload_data = json.loads(rec["payload"])
                        ts = rec["timestamp"]
                        ts_str = ts.isoformat() if hasattr(ts, 'isoformat') else str(ts) if ts else None
                        historical.append({
                            "payload": payload_data,
                            "timestamp": ts_str
                        })
                    except (json.JSONDecodeError, TypeError):
                        continue
                match["historical_payloads"] = historical

        # 6. Build similar_results for response
        similar_results = [
            SimilarResult(
                topic_path=m["topic_path"],
                similarity=m["similarity"],
                field_names=m["field_names"],
                historical_payloads=[
                    HistoricalPayload(payload=h["payload"], timestamp=h.get("timestamp"))
                    for h in m.get("historical_payloads", [])
                ],
            )
            for m in top_matches
        ]

        # 7. Calculate overall confidence
        if not top_matches:
            overall_similarity = 0.0
        else:
            # Weight top results more heavily
            weights = [1.0 / (i + 1) for i in range(len(top_matches))]
            weighted_sum = sum(m["similarity"] * w for m, w in zip(top_matches, weights))
            total_weight = sum(weights)
            overall_similarity = weighted_sum / total_weight if total_weight > 0 else 0.0

        # Determine confidence level (lowered thresholds for more generous matching)
        if top_matches and top_matches[0]["similarity"] >= 0.3:
            confidence = "high"
        elif top_matches and top_matches[0]["similarity"] >= 0.15:
            confidence = "medium"
        else:
            confidence = "low"

        # 8. Use LLM to generate unique topic + schema (always try, even for novel machines)
        suggested_topic = None
        suggested_fields = request.fields  # Default to original fields
        suggested_topics = []  # Multi-topic suggestions
        topic_pattern = "single"  # Default to single topic pattern

        # Always call LLM if we have any context (fields or similar topics)
        if top_matches or request.fields:
            try:
                # Format similar topics with historical payloads for LLM context
                # Extract the field names from the TOP similar topic - this is what the LLM MUST use
                top_similar_fields = top_matches[0]["field_names"] if top_matches else []

                similar_topics_context = ""
                for i, m in enumerate(top_matches[:10], 1):
                    similar_topics_context += f"\n{i}. {m['topic_path']} (similarity: {m['similarity']:.2f})\n"
                    similar_topics_context += f"   Fields: {', '.join(m['field_names'])}\n"

                    # Add historical payloads (limit to 3 for context window)
                    hist_payloads = m.get("historical_payloads", [])[:3]
                    if hist_payloads:
                        similar_topics_context += "   Recent payloads:\n"
                        for h in hist_payloads:
                            payload_str = json.dumps(h["payload"], separators=(',', ':'))
                            # Truncate long payloads
                            if len(payload_str) > 200:
                                payload_str = payload_str[:200] + "..."
                            similar_topics_context += f"   - {payload_str}\n"

                # Log the context being sent to LLM
                logger.info(f"Top similar fields that LLM MUST use: {top_similar_fields}")
                logger.info(f"Similar topics context:\n{similar_topics_context}")

                # Format original fields for the prompt
                original_fields_str = ", ".join([f"{f.name} ({f.type.value})" for f in request.fields])

                # Build user prompt
                user_prompt = UNIFIED_SUGGESTION_USER_PROMPT.format(
                    machine_type=request.machine_type,
                    machine_name=request.machine_name,
                    original_fields=original_fields_str,
                    similar_topics_context=similar_topics_context,
                )

                # Call LLM to generate unified suggestion
                llm_response = await llm_generator.generate(
                    system_prompt=UNIFIED_SUGGESTION_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=2048,  # Increased for multi-topic responses
                )

                # Parse LLM response
                if llm_response:
                    try:
                        # Clean up response - remove markdown code blocks if present
                        cleaned = llm_response.strip()
                        if cleaned.startswith("```"):
                            cleaned = cleaned.split("```")[1]
                            if cleaned.startswith("json"):
                                cleaned = cleaned[4:]
                        cleaned = cleaned.strip()

                        suggestion = json.loads(cleaned)

                        # Get topic pattern
                        topic_pattern = suggestion.get("topic_pattern", "single")

                        type_map = {
                            "number": FieldType.NUMBER,
                            "integer": FieldType.INTEGER,
                            "boolean": FieldType.BOOLEAN,
                            "string": FieldType.STRING,
                        }

                        # Analyze historical payloads for type inference
                        historical_payloads = top_matches[0].get("historical_payloads", []) if top_matches else []
                        field_analysis = _analyze_field_values(historical_payloads)

                        # Parse suggested_topics (new format)
                        suggested_topics = []
                        if "suggested_topics" in suggestion:
                            for st in suggestion["suggested_topics"]:
                                topic_path = st.get("topic_path", "").strip().strip('"').strip("'")
                                source_field = st.get("source_field")

                                # Parse fields for this topic
                                topic_fields = []
                                for sf in st.get("fields", []):
                                    field_name = sf["name"]

                                    # Force correct types for well-known split_by_metric fields
                                    # This prevents LLM from mistyping "value" as "string"
                                    if field_name == "value":
                                        field_type = FieldType.NUMBER
                                    elif field_name == "timestamp":
                                        field_type = FieldType.INTEGER
                                    elif field_name == "asset_id":
                                        field_type = FieldType.STRING
                                    elif field_name == "state":
                                        field_type = FieldType.STRING
                                    elif field_name == "state_duration":
                                        field_type = FieldType.NUMBER
                                    else:
                                        # For non-standard fields, use historical analysis or LLM type
                                        analysis = field_analysis.get(field_name, {})
                                        inferred_type = analysis.get("inferred_type")
                                        if inferred_type:
                                            field_type = type_map.get(inferred_type, FieldType.STRING)
                                        else:
                                            field_type = type_map.get(sf.get("type", "string"), FieldType.STRING)

                                    topic_fields.append(FieldDefinition(name=field_name, type=field_type))

                                suggested_topics.append(TopicSuggestion(
                                    topic_path=topic_path,
                                    fields=topic_fields,
                                    source_field=source_field,
                                ))

                        # For backward compat, also populate suggested_topic/suggested_fields from first topic
                        if suggested_topics:
                            suggested_topic = suggested_topics[0].topic_path
                            suggested_fields = suggested_topics[0].fields

                        logger.info(f"LLM topic_pattern: {topic_pattern}, suggested {len(suggested_topics)} topics")
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse LLM response as JSON: {e}")
            except Exception as e:
                logger.warning(f"Failed to generate unified suggestion via LLM: {e}")

        return UnifiedSuggestionResponse(
            suggested_topic=suggested_topic,
            suggested_fields=suggested_fields,
            suggested_topics=suggested_topics,
            topic_pattern=topic_pattern,
            similar_results=similar_results,
            confidence=confidence,
            overall_similarity=overall_similarity,
        )

    except Exception as e:
        logger.error(f"Error in unified suggestion: {e}")
        return UnifiedSuggestionResponse(
            suggested_topic=None,
            suggested_fields=request.fields,
            suggested_topics=[],
            topic_pattern="single",
            similar_results=[],
            confidence="low",
            overall_similarity=0.0,
        )
    finally:
        driver.close()
