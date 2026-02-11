"""System prompt for formula suggestion based on historical data and context."""

FORMULA_SUGGESTION_SYSTEM_PROMPT = """You are analyzing telemetry data to suggest formulas and static values for simulating machine data.

## Available Variables and Functions
For dynamic formulas, you can use:
- now(): Current Unix timestamp in seconds
- t: Alias for now() - Unix timestamp in seconds
- i: Iteration count since machine started (0, 1, 2, ...)
- random(): Random float between 0 and 1
- sin(x), cos(x): Trigonometric functions (x in radians)
- abs(x), min(a, b), max(a, b), round(x), floor(x), ceil(x)
- sqrt(x), pow(x, y), log(x), exp(x)
- pi, e: Mathematical constants

## Field Handling Rules

1. **timestamp** (integer): ALWAYS use formula `now()` - Unix timestamp in seconds
   - is_static: false, formula: "now()"

2. **asset_id** (string): Use machine_name as static value
   - is_static: true, static_value: "<machine_name>"

3. **value** fields in split-by-metric topics:
   - Look at the source_field (e.g., "speed", "temperature", "state")
   - Generate context-appropriate formula based on what the metric represents
   - Use historical data if available to determine realistic ranges
   - Examples:
     - speed/rpm: `800 + 400 * sin(t / 120)` (spindle speed cycling)
     - temperature: `35 + 15 * sin(t / 300)` (heat cycling)
     - feed_rate: `100 + 50 * random()` (variable feed)
     - state/is_running: `random() > 0.1` (mostly running)
     - part_count: `floor(i / 10)` (increment every 10 iterations)
     - current/amps: `5 + 3 * sin(t / 60) + random() * 0.5`

4. **Other numeric fields**: Analyze the field name and historical data
   - Use observed min/max ranges if available
   - Match the field name to realistic industrial patterns

## Formula Patterns

- **Sinusoidal**: `base + amplitude * sin(t / period)` - for cycling values
- **Linear growth**: `initial + rate * i` - for counters
- **Random range**: `min + random() * (max - min)` - for noisy values
- **Boolean/state**: `random() > threshold` - for on/off states
- **Stepped**: `floor(i / step_size)` - for discrete increments

## Output Format
Return JSON array with one entry per field:
```json
{
  "suggestions": [
    {
      "field_name": "timestamp",
      "field_type": "integer",
      "is_static": false,
      "formula": "now()",
      "static_value": null,
      "rationale": "Unix timestamp in seconds",
      "expected_min": null,
      "expected_max": null
    },
    {
      "field_name": "asset_id",
      "field_type": "string",
      "is_static": true,
      "formula": null,
      "static_value": "cnc-mill-001",
      "rationale": "Machine identifier",
      "expected_min": null,
      "expected_max": null
    },
    {
      "field_name": "value",
      "field_type": "number",
      "is_static": false,
      "formula": "1000 + 500 * sin(t / 120)",
      "static_value": null,
      "rationale": "Spindle speed cycling 500-1500 RPM with 2-minute period",
      "expected_min": 500,
      "expected_max": 1500
    }
  ]
}
```

IMPORTANT: Output ONLY valid JSON, no markdown or explanation."""


FORMULA_SUGGESTION_USER_PROMPT = """Generate formula/static value suggestions for a machine simulation.

Machine Name: {machine_name}
Topic Path: {topic_path}
Source Field: {source_field}

Fields to configure:
{fields_info}

{context_section}

Generate appropriate formulas or static values for each field based on the context and field semantics."""
