"""Prompt templates for schema suggestion LLM calls."""

SYSTEM_PROMPT = """You are an MQTT Schema Advisor for a manufacturing data platform.

Your PRIMARY job is DATA MODEL NORMALIZATION - ensuring all similar data sources conform to the SAME schema with consistent field names, data types, and naming conventions.

## Core Principles

### 1. Schema Normalization is #1 Priority
- Analyze similar messages to understand the COMPLETE expected payload schema
- The payloadMapping MUST include ALL fields that similar messages have, not just fields in the raw payload
- If similar messages have fields like `asset_id`, `timestamp`, `value` - include them in payloadMapping even if the raw payload doesn't have them
- Use format: `"expected_raw_key": "normalized_key"` for fields present in raw payload
- Use format: `"[MISSING]field_name": "normalized_key"` for fields that SHOULD be present based on similar data

### 2. Consistent Naming Conventions
- ALL normalized field names must use snake_case (e.g., `temperature_celsius`, `asset_id`, `timestamp_unix`)
- Numeric values should indicate units in the name (e.g., `temperature_celsius`, `pressure_psi`, `speed_rpm`)
- Timestamps should indicate format (e.g., `timestamp_unix`, `timestamp_iso8601`)
- IDs should be descriptive (e.g., `asset_id`, `machine_id`, `sensor_id`)

### 3. ISA-95 Topic Hierarchy
Structure curated topics following ISA-95:
- Level 4 (Enterprise): `{enterprise}/`
- Level 3 (Site/Plant): `{enterprise}/{site}/`
- Level 2 (Area): `{enterprise}/{site}/{area}/`
- Level 1 (Line): `{enterprise}/{site}/{area}/{line}/`
- Level 0 (Cell): `{enterprise}/{site}/{area}/{line}/{cell}/`
- Equipment: `{enterprise}/{site}/{area}/{line}/{cell}/{equipment}/`
- Metric: `{enterprise}/{site}/{area}/{line}/{cell}/{equipment}/{metric}`

Example: `acme-manufacturing/plant-01/machining/line-a/cell-01/cnc-mill-001/temperature`

### 4. Extract Hierarchy from Context
- Look at similar topic paths to determine enterprise, site, area, line, cell
- If raw topic contains identifiers (e.g., `pump`, `conveyor_035`), use them for equipment name
- Only use "unknown" if there's truly no way to infer the value

## Output Format

You MUST respond with valid JSON:
```json
{
  "recommendedParentTopic": "enterprise/site/area/line/cell/equipment",
  "suggestedTopicName": "metric_name",
  "suggestedFullTopicPath": "enterprise/site/area/line/cell/equipment/metric_name",
  "payloadMapping": {
    "raw_field": "normalized_field",
    "temp": "temperature_celsius",
    "value": "value",
    "[MISSING]asset_id": "asset_id",
    "[MISSING]timestamp": "timestamp_unix"
  },
  "confidence": "low|medium|high",
  "rationale": "Explanation including what fields are missing from raw payload"
}
```

## Example

Given raw payload `{"temp": 45.2}` and similar messages showing `asset_id=conveyor_030, timestamp=1767643630729, value=30.79`:

```json
{
  "recommendedParentTopic": "acme-manufacturing/plant-01/machining/line-a/cell-01/conveyor-030",
  "suggestedTopicName": "temperature",
  "suggestedFullTopicPath": "acme-manufacturing/plant-01/machining/line-a/cell-01/conveyor-030/temperature",
  "payloadMapping": {
    "temp": "temperature_celsius",
    "[MISSING]asset_id": "asset_id",
    "[MISSING]timestamp": "timestamp_unix",
    "[MISSING]value": "value"
  },
  "confidence": "medium",
  "rationale": "Based on similar conveyor temperature topics. Raw payload only has 'temp' but similar messages include asset_id, timestamp, and value fields. The normalized schema should include all these fields for consistency."
}
```
"""


def build_user_prompt(
    raw_topic: str,
    raw_payload: str,
    similar_topics: list,
    similar_messages: list,
    curated_tree: dict
) -> str:
    """Build the user prompt with context."""
    # Format similar topics
    topics_context = _format_similar_topics(similar_topics)

    # Format similar messages with emphasis on payload schema
    messages_context = _format_similar_messages(similar_messages)

    # Extract common payload fields from similar messages
    payload_schema = _extract_payload_schema(similar_messages)

    # Format curated tree
    tree_context = _format_tree(curated_tree)

    return f"""## New Raw Topic to Normalize

**Raw Topic:** `{raw_topic}`

**Raw Payload:**
```json
{raw_payload}
```

## Similar Topics Found

{topics_context}

## Similar Messages Found (ANALYZE THESE FOR PAYLOAD SCHEMA)

{messages_context}

## Common Payload Fields in Similar Messages

{payload_schema}

## Existing Curated Topic Structure

{tree_context}

---

IMPORTANT: Your payloadMapping must include ALL fields seen in similar messages, marking missing fields with [MISSING] prefix.

Respond with JSON only.
"""


def _format_similar_topics(topics: list) -> str:
    """Format similar topics for prompt."""
    if not topics:
        return "No similar topics found."

    lines = []
    for i, t in enumerate(topics[:15], 1):
        broker_tag = "CURATED" if t.get("broker") == "curated" else "uncurated"
        score = t.get("score", 0)
        lines.append(f"{i}. [{broker_tag}] `{t.get('path')}` (similarity: {score:.2f})")

    return "\n".join(lines)


def _format_similar_messages(messages: list) -> str:
    """Format similar messages for prompt."""
    if not messages:
        return "No similar messages found."

    lines = []
    curated_msgs = [m for m in messages if m.get("broker") == "curated"][:10]
    uncurated_msgs = [m for m in messages if m.get("broker") == "uncurated"][:10]

    if curated_msgs:
        lines.append("**From Curated Broker (PREFERRED SCHEMA):**")
        for m in curated_msgs:
            lines.append(f"  - Topic: `{m.get('topicPath')}`")
            lines.append(f"    Payload: `{m.get('payloadText', '')[:150]}`")

    if uncurated_msgs:
        lines.append("\n**From Uncurated Broker:**")
        for m in uncurated_msgs:
            lines.append(f"  - Topic: `{m.get('topicPath')}`")
            lines.append(f"    Payload: `{m.get('payloadText', '')[:150]}`")

    return "\n".join(lines) if lines else "No similar messages found."


def _extract_payload_schema(messages: list) -> str:
    """Extract and summarize common payload fields from similar messages."""
    if not messages:
        return "No payload schema information available."

    # Parse payload fields from payloadText (format: "key=value, key=value")
    all_fields = set()
    field_examples = {}

    for m in messages[:20]:
        payload_text = m.get("payloadText", "")
        # Parse "key=value, key=value" format
        for part in payload_text.split(", "):
            if "=" in part:
                key, value = part.split("=", 1)
                key = key.strip()
                all_fields.add(key)
                if key not in field_examples:
                    field_examples[key] = value.strip()

    if not all_fields:
        return "Could not parse payload fields from similar messages."

    lines = ["**Expected fields based on similar messages:**"]
    for field in sorted(all_fields):
        example = field_examples.get(field, "")
        lines.append(f"  - `{field}` (example: {example})")

    return "\n".join(lines)


def _format_tree(tree: dict, indent: int = 0) -> str:
    """Format topic tree for prompt."""
    if not tree:
        return "No curated topic tree available."

    lines = []
    _tree_to_lines(tree, lines, indent, max_depth=4)

    if len(lines) > 50:
        lines = lines[:50]
        lines.append("  ... (truncated)")

    return "\n".join(lines) if lines else "Empty tree."


def _tree_to_lines(tree: dict, lines: list, indent: int, max_depth: int):
    """Recursively format tree."""
    if indent >= max_depth * 2:
        return

    for key, subtree in sorted(tree.items()):
        lines.append("  " * indent + f"- {key}/")
        if isinstance(subtree, dict) and subtree:
            _tree_to_lines(subtree, lines, indent + 1, max_depth)
