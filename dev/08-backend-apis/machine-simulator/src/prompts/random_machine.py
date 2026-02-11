"""System prompt for random machine generation."""

# SparkMES structure template that must be included in all generated machines
SPARKMES_STRUCTURE_TEMPLATE = """{
  "name": "<use suggestedName>",
  "typeId": "Simulators/AdvancedDiscreteMachineSimulator",
  "parameters": {
    "NextMachinePath": { "dataType": "String", "value": "" },
    "SerialGenerator": { "dataType": "Integer", "value": 1 },
    "Simulate": { "dataType": "Integer", "value": 1 }
  },
  "tagType": "UdtInstance",
  "tags": [
    { "value": "<generate-uuid>", "name": "SerialNumber", "tagType": "AtomicTag" },
    { "name": "CycleInfo", "tagType": "Folder", "tags": [
      { "value": false, "name": "CycleComplete", "tagType": "AtomicTag" },
      { "value": true, "name": "CycleStart", "tagType": "AtomicTag" }
    ]},
    { "name": "Counts", "tagType": "Folder", "tags": [
      { "value": 0, "name": "Outfeed", "tagType": "AtomicTag" },
      { "value": 0, "name": "Infeed", "tagType": "AtomicTag" },
      { "value": 0, "name": "Scrap", "tagType": "AtomicTag" }
    ]},
    { "name": "StatusRaw", "tagType": "Folder", "tags": [
      { "value": true, "name": "Running", "tagType": "AtomicTag" },
      { "value": false, "name": "Paused", "tagType": "AtomicTag" },
      { "value": false, "name": "Light Screen Tripped", "tagType": "AtomicTag" },
      { "value": false, "name": "E-Stop", "tagType": "AtomicTag" }
    ]},
    { "name": "Simulator", "tagType": "AtomicTag" },
    { "name": "Status", "tagType": "Folder", "tags": [
      { "name": "Status", "tagType": "AtomicTag" }
    ]},
    { "name": "PartInfo", "tagType": "Folder", "tags": [
      { "value": 1, "name": "PartCode", "tagType": "AtomicTag" }
    ]},
    { "name": "SimulationData", "tagType": "Folder", "tags": [
      { "value": 0, "name": "TimeInCycle", "tagType": "AtomicTag" }
    ]},
    { "name": "Alarms", "tagType": "Folder", "tags": [
      { "value": false, "name": "OutOfSpec", "tagType": "AtomicTag" }
    ]},
    { "name": "ProcessData", "tagType": "Folder", "tags": [
      { "name": "ConsSerial1", "tagType": "AtomicTag" },
      { "name": "ProcessData1", "tagType": "AtomicTag" },
      { "name": "ProcessData2", "tagType": "AtomicTag" },
      { "name": "ProcessData3", "tagType": "AtomicTag" },
      { "name": "ProcessData4", "tagType": "AtomicTag" },
      { "name": "ConsSerial2", "tagType": "AtomicTag" },
      { "name": "ConsSerial3", "tagType": "AtomicTag" }
    ]}
  ]
}"""

RANDOM_MACHINE_SYSTEM_PROMPT = """You are a manufacturing equipment simulator designer. Generate realistic industrial machine payload schemas.

Your task is to generate a random machine with:
1. A realistic machine type (CNC mill, conveyor belt, robotic arm, temperature sensor, hydraulic pump, compressor, packaging machine, welding robot, etc.)
2. A payload schema with 3-8 fields typical for that equipment type
3. Classify each field as DYNAMIC (telemetry that changes over time) or STATIC (fixed identifiers)
4. A SparkMES structure for MES (Manufacturing Execution System) integration

The SparkMES structure MUST follow this EXACT format with ALL tags included:
""" + SPARKMES_STRUCTURE_TEMPLATE + """

IMPORTANT: In the SparkMES structure:
- Set "name" to match your suggestedName
- Generate a valid UUID for SerialNumber (e.g., "36f0064b-43e7-4c1b-9f9c-c0a901ffaea2")
- Include ALL folders and tags exactly as shown - do not add or remove any

Output valid JSON only, no markdown formatting or explanation."""

RANDOM_MACHINE_USER_PROMPT = """Generate a random industrial machine definition.

Output JSON in this exact format:
{
  "machineType": "Equipment type name",
  "suggestedName": "equipment-identifier-001",
  "description": "Brief description of what this equipment does",
  "fields": [
    {"name": "temperature_c", "type": "number", "minValue": 20, "maxValue": 85},
    {"name": "pressure_bar", "type": "number", "minValue": 0, "maxValue": 10},
    {"name": "part_count", "type": "integer", "minValue": 0, "maxValue": 999999},
    {"name": "is_running", "type": "boolean"},
    {"name": "asset_id", "type": "string", "staticValue": "equipment-001"}
  ],
  "publishIntervalMs": 5000,
  "SparkMES": {
    "name": "equipment-identifier-001",
    "typeId": "Simulators/AdvancedDiscreteMachineSimulator",
    "parameters": {
      "NextMachinePath": { "dataType": "String", "value": "" },
      "SerialGenerator": { "dataType": "Integer", "value": 1 },
      "Simulate": { "dataType": "Integer", "value": 1 }
    },
    "tagType": "UdtInstance",
    "tags": [
      { "value": "36f0064b-43e7-4c1b-9f9c-c0a901ffaea2", "name": "SerialNumber", "tagType": "AtomicTag" },
      { "name": "CycleInfo", "tagType": "Folder", "tags": [
        { "value": false, "name": "CycleComplete", "tagType": "AtomicTag" },
        { "value": true, "name": "CycleStart", "tagType": "AtomicTag" }
      ]},
      { "name": "Counts", "tagType": "Folder", "tags": [
        { "value": 0, "name": "Outfeed", "tagType": "AtomicTag" },
        { "value": 0, "name": "Infeed", "tagType": "AtomicTag" },
        { "value": 0, "name": "Scrap", "tagType": "AtomicTag" }
      ]},
      { "name": "StatusRaw", "tagType": "Folder", "tags": [
        { "value": true, "name": "Running", "tagType": "AtomicTag" },
        { "value": false, "name": "Paused", "tagType": "AtomicTag" },
        { "value": false, "name": "Light Screen Tripped", "tagType": "AtomicTag" },
        { "value": false, "name": "E-Stop", "tagType": "AtomicTag" }
      ]},
      { "name": "Simulator", "tagType": "AtomicTag" },
      { "name": "Status", "tagType": "Folder", "tags": [
        { "name": "Status", "tagType": "AtomicTag" }
      ]},
      { "name": "PartInfo", "tagType": "Folder", "tags": [
        { "value": 1, "name": "PartCode", "tagType": "AtomicTag" }
      ]},
      { "name": "SimulationData", "tagType": "Folder", "tags": [
        { "value": 0, "name": "TimeInCycle", "tagType": "AtomicTag" }
      ]},
      { "name": "Alarms", "tagType": "Folder", "tags": [
        { "value": false, "name": "OutOfSpec", "tagType": "AtomicTag" }
      ]},
      { "name": "ProcessData", "tagType": "Folder", "tags": [
        { "name": "ConsSerial1", "tagType": "AtomicTag" },
        { "name": "ProcessData1", "tagType": "AtomicTag" },
        { "name": "ProcessData2", "tagType": "AtomicTag" },
        { "name": "ProcessData3", "tagType": "AtomicTag" },
        { "name": "ProcessData4", "tagType": "AtomicTag" },
        { "name": "ConsSerial2", "tagType": "AtomicTag" },
        { "name": "ConsSerial3", "tagType": "AtomicTag" }
      ]}
    ]
  }
}

FIELD CLASSIFICATION RULES:

DYNAMIC fields (telemetry - values change over time, will be simulated):
- Measurements: temperature, pressure, voltage, current, humidity, speed, rpm, flow_rate, power, level, weight, distance
- Counters: part_count, cycle_count, error_count, uptime_seconds
- States: is_running, is_active, alarm, fault, mode, status
- For DYNAMIC fields: use "minValue" and "maxValue" to define the expected range
- Do NOT use "staticValue" for dynamic fields

STATIC fields (identifiers - fixed values that never change):
- Only use for: asset_id, machine_id, serial_number, location, model_number
- For STATIC fields: use "staticValue" with an example value
- Do NOT use "minValue"/"maxValue" for static fields

EXAMPLE - temperature_c is DYNAMIC (it's a measurement that changes):
{"name": "temperature_c", "type": "number", "minValue": 20, "maxValue": 85}

EXAMPLE - asset_id is STATIC (it's a fixed identifier):
{"name": "asset_id", "type": "string", "staticValue": "pump-001"}

Most fields should be DYNAMIC. Only 1-2 identifier fields should be STATIC.

IMPORTANT: The SparkMES structure MUST be included with ALL tags exactly as shown in the example."""


# Context-aware prompts for generating machines based on existing knowledge graph assets

CONTEXT_AWARE_RANDOM_SYSTEM_PROMPT = """You are a manufacturing equipment simulator designer. Generate realistic industrial machine payload schemas.

You will be given:
1. Context about existing Topic assets in the knowledge graph
2. A list of ALREADY CREATED simulated machines that you MUST NOT duplicate

Your task is to generate a COMPLETELY NOVEL machine that:
1. Is ABSOLUTELY UNIQUE - has a COMPLETELY DIFFERENT machine type and name from ANY existing machines
2. Is NOT a variation of existing machines (no "cnc-mill-003" if "cnc-mill-001" exists, no "pump-beta" if "pump-alpha" exists)
3. Is CONTEXTUALLY FITTING - makes sense alongside the existing machines (same industrial domain/environment)
4. Has a realistic payload schema with 3-8 fields typical for that equipment type
5. Includes a SparkMES structure for MES (Manufacturing Execution System) integration

Think creatively about what OTHER types of equipment might exist in the same factory/facility. Generate something complementary but completely distinct from what already exists.

CRITICAL: Never generate a machine with the same or similar type/name as any in the existing machines list. If you see "CNC Mill" exists, generate something entirely different like "Hydraulic Press" or "Packaging Robot".

The SparkMES structure MUST follow this EXACT format with ALL tags included:
""" + SPARKMES_STRUCTURE_TEMPLATE + """

IMPORTANT: In the SparkMES structure:
- Set "name" to match your suggestedName
- Generate a valid UUID for SerialNumber (e.g., "36f0064b-43e7-4c1b-9f9c-c0a901ffaea2")
- Include ALL folders and tags exactly as shown - do not add or remove any

Output valid JSON only, no markdown formatting or explanation."""


CONTEXT_AWARE_RANDOM_USER_PROMPT = """Here are {count} existing assets from the knowledge graph for context:

{context_section}

{existing_machines_section}

Based on this industrial context, generate a COMPLETELY NOVEL machine that:
1. Has a DIFFERENT machine type than ANY existing machine listed above
2. Has a DIFFERENT name than ANY existing machine listed above
3. Would fit logically in the same industrial environment
4. Has realistic field names and value ranges appropriate for the new machine type
5. Includes the complete SparkMES structure

CRITICAL: You MUST NOT generate any machine type or name that appears in the "EXISTING MACHINES" list above!

Output JSON in this exact format:
{{
  "machineType": "Equipment type name",
  "suggestedName": "equipment-identifier-001",
  "description": "Brief description of what this equipment does and why it fits the context",
  "fields": [
    {{"name": "temperature_c", "type": "number", "minValue": 20, "maxValue": 85}},
    {{"name": "pressure_bar", "type": "number", "minValue": 0, "maxValue": 10}},
    {{"name": "part_count", "type": "integer", "minValue": 0, "maxValue": 999999}},
    {{"name": "is_running", "type": "boolean"}},
    {{"name": "asset_id", "type": "string", "staticValue": "equipment-001"}}
  ],
  "publishIntervalMs": 5000,
  "SparkMES": {{
    "name": "equipment-identifier-001",
    "typeId": "Simulators/AdvancedDiscreteMachineSimulator",
    "parameters": {{
      "NextMachinePath": {{ "dataType": "String", "value": "" }},
      "SerialGenerator": {{ "dataType": "Integer", "value": 1 }},
      "Simulate": {{ "dataType": "Integer", "value": 1 }}
    }},
    "tagType": "UdtInstance",
    "tags": [
      {{ "value": "36f0064b-43e7-4c1b-9f9c-c0a901ffaea2", "name": "SerialNumber", "tagType": "AtomicTag" }},
      {{ "name": "CycleInfo", "tagType": "Folder", "tags": [
        {{ "value": false, "name": "CycleComplete", "tagType": "AtomicTag" }},
        {{ "value": true, "name": "CycleStart", "tagType": "AtomicTag" }}
      ]}},
      {{ "name": "Counts", "tagType": "Folder", "tags": [
        {{ "value": 0, "name": "Outfeed", "tagType": "AtomicTag" }},
        {{ "value": 0, "name": "Infeed", "tagType": "AtomicTag" }},
        {{ "value": 0, "name": "Scrap", "tagType": "AtomicTag" }}
      ]}},
      {{ "name": "StatusRaw", "tagType": "Folder", "tags": [
        {{ "value": true, "name": "Running", "tagType": "AtomicTag" }},
        {{ "value": false, "name": "Paused", "tagType": "AtomicTag" }},
        {{ "value": false, "name": "Light Screen Tripped", "tagType": "AtomicTag" }},
        {{ "value": false, "name": "E-Stop", "tagType": "AtomicTag" }}
      ]}},
      {{ "name": "Simulator", "tagType": "AtomicTag" }},
      {{ "name": "Status", "tagType": "Folder", "tags": [
        {{ "name": "Status", "tagType": "AtomicTag" }}
      ]}},
      {{ "name": "PartInfo", "tagType": "Folder", "tags": [
        {{ "value": 1, "name": "PartCode", "tagType": "AtomicTag" }}
      ]}},
      {{ "name": "SimulationData", "tagType": "Folder", "tags": [
        {{ "value": 0, "name": "TimeInCycle", "tagType": "AtomicTag" }}
      ]}},
      {{ "name": "Alarms", "tagType": "Folder", "tags": [
        {{ "value": false, "name": "OutOfSpec", "tagType": "AtomicTag" }}
      ]}},
      {{ "name": "ProcessData", "tagType": "Folder", "tags": [
        {{ "name": "ConsSerial1", "tagType": "AtomicTag" }},
        {{ "name": "ProcessData1", "tagType": "AtomicTag" }},
        {{ "name": "ProcessData2", "tagType": "AtomicTag" }},
        {{ "name": "ProcessData3", "tagType": "AtomicTag" }},
        {{ "name": "ProcessData4", "tagType": "AtomicTag" }},
        {{ "name": "ConsSerial2", "tagType": "AtomicTag" }},
        {{ "name": "ConsSerial3", "tagType": "AtomicTag" }}
      ]}}
    ]
  }}
}}

FIELD CLASSIFICATION RULES:

DYNAMIC fields (telemetry - values change over time, will be simulated):
- Measurements: temperature, pressure, voltage, current, humidity, speed, rpm, flow_rate, power, level, weight, distance
- Counters: part_count, cycle_count, error_count, uptime_seconds
- States: is_running, is_active, alarm, fault, mode, status
- For DYNAMIC fields: use "minValue" and "maxValue" to define the expected range
- Do NOT use "staticValue" for dynamic fields

STATIC fields (identifiers - fixed values that never change):
- Only use for: asset_id, machine_id, serial_number, location, model_number
- For STATIC fields: use "staticValue" with an example value
- Do NOT use "minValue"/"maxValue" for static fields

Most fields should be DYNAMIC. Only 1-2 identifier fields should be STATIC.

IMPORTANT: The SparkMES structure MUST be included with ALL tags exactly as shown in the example."""
