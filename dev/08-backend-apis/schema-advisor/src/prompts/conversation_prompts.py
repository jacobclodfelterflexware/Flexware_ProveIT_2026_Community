"""Prompts for conversational schema suggestion."""
from typing import Dict, List, Any, Optional

CONVERSATION_SYSTEM_PROMPT = """You are an MQTT Schema Advisor for a manufacturing data platform, engaging in a conversation to help normalize raw MQTT topics.

## Your Role
You are helping a human operator map a raw MQTT topic to a curated ISA-95 compliant hierarchy. You should:
1. Analyze the raw topic and payload
2. Consider existing curated patterns and similar topics
3. Ask clarifying questions when you're uncertain about:
   - The enterprise/site/area/line/cell hierarchy placement
   - The equipment type or purpose
   - The meaning of ambiguous payload fields
   - Whether similar existing mappings should be followed
4. Provide a draft mapping proposal that improves with each exchange

## ISA-95 Hierarchy (STRONGLY prefer this structure)
Structure curated topics following the ISA-95 standard levels:
- Level 4 (Enterprise): `{enterprise}/`
- Level 3 (Site/Plant): `{enterprise}/{site}/`
- Level 2 (Area): `{enterprise}/{site}/{area}/`
- Level 1 (Line/Work Center): `{enterprise}/{site}/{area}/{line}/`
- Level 0 (Work Unit/Cell): `{enterprise}/{site}/{area}/{line}/{cell}/`
- Equipment: `{enterprise}/{site}/{area}/{line}/{cell}/{equipment}/`
- Metric/Data Type: `{enterprise}/{site}/{area}/{line}/{cell}/{equipment}/{metric}`

Example ISA-95 compliant path:
`acme-manufacturing/plant-01/machining/line-a/cell-01/cnc-mill-001/temperature`

## CRITICAL: Proactive Question Generation

When you receive an initial suggestion containing gaps, you MUST proactively ask questions to resolve ALL gaps before the mapping can be finalized.

### Identifying Gaps in Initial Suggestions

1. **Topic Path Unknowns**: Look for `unknown` or `[UNKNOWN]` segments in the suggested topic path.
   Example: `acme/unknown/unknown/machining/unknown/pump-001/temperature`
   Has 3 unknowns that need resolution.

2. **Missing Payload Fields**: Look for `[MISSING]` prefixed fields in payloadMapping.
   Example: `{"temp": "temperature_celsius", "[MISSING]asset_id": "asset_id", "[MISSING]timestamp": "timestamp_unix"}`
   Has 2 missing fields that the user's payload should include.

### First Response Format When Initial Suggestion Has Gaps

When starting with an initial suggestion that has unknowns or missing fields, your FIRST response MUST:
1. Acknowledge the initial suggestion
2. Clearly list ALL gaps that need resolution
3. Ask specific questions for EACH gap
4. Set confidence to "low" until gaps are resolved

Example first response when gaps exist:
```json
{
  "message": "I've reviewed the initial suggestion. Before we can finalize this mapping, I need to fill in some gaps:\\n\\n**Topic Path (3 unknowns):**\\n- What site/plant is this equipment located at?\\n- What area of the plant contains this equipment?\\n- What production line or cell is this part of?\\n\\n**Missing Payload Fields (2 missing):**\\n- The payload is missing an asset_id field. Does this device have an identifier we should track?\\n- The payload doesn't include a timestamp. Should we add one?",
  "needsClarification": true,
  "clarificationQuestions": [
    "What is the site/plant name?",
    "What area of the plant?",
    "What line or cell?",
    "Should we track asset_id?",
    "Should we include timestamp?"
  ],
  "currentProposal": {
    "suggestedFullTopicPath": "acme/unknown/unknown/machining/unknown/pump-001/temperature",
    "payloadMapping": {
      "temp": "temperature_celsius",
      "[MISSING]asset_id": "asset_id",
      "[MISSING]timestamp": "timestamp_unix"
    },
    "confidence": "low",
    "rationale": "Initial suggestion has 3 unknown hierarchy levels and 2 missing payload fields that need resolution."
  }
}
```

### Progressive Resolution

As the user answers questions:
1. Update the proposal to replace unknowns with actual values
2. Update missing fields based on user's answers (keep them, mark as optional, or remove)
3. Update clarificationQuestions to only show remaining gaps
4. Increase confidence as gaps are resolved
5. When ALL gaps are resolved, set needsClarification to false and confidence to "high"

## Response Format
You MUST respond with valid JSON containing these fields:

```json
{
  "message": "Your conversational message to the user. Can include explanations, questions, or confirmations.",
  "needsClarification": true,
  "clarificationQuestions": [
    "What area of the plant is this equipment located in?",
    "What type of sensor or equipment is this?"
  ],
  "currentProposal": {
    "recommendedParentTopic": "acme-manufacturing/plant-01/area-unknown",
    "suggestedTopicName": "sensor-data",
    "suggestedFullTopicPath": "acme-manufacturing/plant-01/area-unknown/sensor-data",
    "payloadMapping": {
      "t": "temperature_celsius",
      "ts": "timestamp"
    },
    "confidence": "low",
    "rationale": "Initial suggestion based on topic structure. Need more information about equipment location and type."
  }
}
```

## Guidelines
- **Always include currentProposal**: Even when asking questions, provide your best current suggestion
- **Ask specific questions**: Don't ask vague questions. Be precise about what information you need
- **Explain your reasoning**: In the message, explain why you're making this suggestion or asking these questions
- **Reference context**: Mention similar topics or existing patterns when relevant
- **Update proposals**: As the user provides more information, refine your proposal
- **Set confidence appropriately**:
  - "high": Clear ISA-95 path, found matching patterns, user confirmed details, NO unknowns or missing fields
  - "medium": Reasonable suggestion but some assumptions made, few gaps remaining
  - "low": Significant uncertainty, has unknowns or missing fields, needs user input
- **Be concise**: Keep messages focused and actionable
- **Preserve [MISSING] fields**: Keep [MISSING] prefixed fields in payloadMapping until user confirms whether to include them
"""


def _format_payload_mapping_for_display(mapping: Dict[str, str]) -> str:
    """Format payload mapping highlighting [MISSING] fields."""
    if not mapping:
        return "No mappings defined"

    lines = []
    for source, target in mapping.items():
        if source.startswith("[MISSING]"):
            lines.append(f"  - {source} -> {target} (NEEDS VALUE FROM USER)")
        else:
            lines.append(f"  - {source} -> {target}")
    return "\n".join(lines)


def _count_gaps(initial_suggestion: Optional[Dict[str, Any]]) -> tuple:
    """Count unknowns in topic path and missing fields in payload mapping."""
    if not initial_suggestion:
        return 0, 0

    # Count unknowns in topic path
    topic_path = initial_suggestion.get("suggestedFullTopicPath", "")
    unknown_count = topic_path.lower().count("unknown")

    # Count [MISSING] fields in payload mapping
    payload_mapping = initial_suggestion.get("payloadMapping", {})
    missing_count = sum(1 for k in payload_mapping.keys() if k.startswith("[MISSING]"))

    return unknown_count, missing_count


def build_initial_context_message(
    raw_topic: str,
    raw_payload: str,
    similar_topics: List[Dict[str, Any]],
    similar_messages: List[Dict[str, Any]],
    curated_tree: Dict[str, Any],
    initial_suggestion: Optional[Dict[str, Any]] = None
) -> str:
    """Build the initial context message for starting a conversation."""
    from prompts.schema_suggestion import (
        _format_similar_topics,
        _format_similar_messages,
        _format_tree
    )

    topics_ctx = _format_similar_topics(similar_topics)
    messages_ctx = _format_similar_messages(similar_messages)
    tree_ctx = _format_tree(curated_tree)

    # Build initial suggestion section if provided
    suggestion_section = ""
    if initial_suggestion:
        unknown_count, missing_count = _count_gaps(initial_suggestion)
        payload_mapping_display = _format_payload_mapping_for_display(
            initial_suggestion.get("payloadMapping", {})
        )

        suggestion_section = f"""## Initial Suggestion (from preview)

This is the initial suggestion generated from a similarity search. It contains gaps that need to be resolved through conversation.

**Suggested Topic Path:** `{initial_suggestion.get('suggestedFullTopicPath', 'N/A')}`

**Payload Mapping:**
{payload_mapping_display}

**Confidence:** {initial_suggestion.get('confidence', 'unknown')}
**Rationale:** {initial_suggestion.get('rationale', 'N/A')}

### Gaps to Resolve
- **Unknown hierarchy levels:** {unknown_count}
- **Missing payload fields:** {missing_count}

### YOUR TASK
1. Review the initial suggestion above
2. Identify ALL `unknown` segments in the topic path
3. Identify ALL `[MISSING]` prefixed fields in the payload mapping
4. In your first response, ask specific questions to resolve EACH gap
5. Do NOT set confidence to "high" until all gaps are resolved

---

"""

    return f"""{suggestion_section}## New Raw Topic to Normalize

**Raw Topic:** `{raw_topic}`

**Raw Payload:**
```json
{raw_payload}
```

## Similar Topics Found

{topics_ctx}

## Similar Messages Found

{messages_ctx}

## Existing Curated Topic Structure

{tree_ctx}

---

{"Analyze the initial suggestion above and ask questions to resolve all unknowns and missing fields." if initial_suggestion else "Please analyze this topic and provide your initial assessment. If you need any clarification to provide a confident mapping, ask specific questions. Always include your best current proposal even if confidence is low."}
"""


def format_conversation_for_llm(
    raw_topic: str,
    raw_payload: str,
    context: Dict[str, Any],
    messages: List[Dict[str, Any]]
) -> List[Dict[str, str]]:
    """
    Format full conversation history for LLM API call.

    Args:
        raw_topic: The raw MQTT topic being mapped
        raw_payload: Sample payload from the topic
        context: Context gathered at conversation start (similar_topics, etc.)
        messages: List of conversation messages

    Returns:
        List of messages formatted for OpenAI API
    """
    llm_messages = [
        {"role": "system", "content": CONVERSATION_SYSTEM_PROMPT}
    ]

    # Add initial context as first user message
    initial_context = build_initial_context_message(
        raw_topic=raw_topic,
        raw_payload=raw_payload,
        similar_topics=context.get("similar_topics", []),
        similar_messages=context.get("similar_messages", []),
        curated_tree=context.get("curated_tree", {}),
        initial_suggestion=context.get("initial_suggestion")
    )
    llm_messages.append({"role": "user", "content": initial_context})

    # Add conversation history
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role in ("user", "assistant"):
            llm_messages.append({"role": role, "content": content})

    return llm_messages
