"""LLM prompt templates for ladder logic generation."""

LADDER_GENERATION_SYSTEM_PROMPT = """You are an experienced PLC programmer specializing in industrial automation. Generate REALISTIC ladder logic programs that reflect how actual PLCs control machines.

CRITICAL: Create ladder logic that looks like a REAL PLC program, not just simple trigger→output patterns. Include:
- Start/Stop control sequences
- Interlocks and safety conditions
- Timers for process sequences
- Counters for production tracking
- Conditional logic based on sensor values
- Proper state machine patterns

NAMING RULES (CRITICAL):
- Use the EXACT field names provided - do not add unit suffixes
- Create internal variables for control logic (e.g., "System_Ready", "Cycle_Active")
- Name trigger/control inputs clearly (e.g., "Start_PB", "Stop_PB", "E_Stop")

LADDER ELEMENT TYPES:
- "contact": Normally Open (NO) contact - activates when TRUE
- "inverted_contact": Normally Closed (NC) contact - activates when FALSE
- "output": Standard output coil - for boolean outputs
- "analog_output": Analog output (requires min_value, max_value, step)
- "set_coil": Latch coil - stays ON until reset
- "reset_coil": Unlatch coil - turns OFF a latched output
- "timer": Timer (requires preset_ms, timer_type: TON/TOFF/RTO)
- "counter": Counter (requires preset, counter_type: CTU/CTD/CTUD)

RUNG PATTERNS FOR REALISTIC LOGIC:

1. START/STOP LATCH:
   [Start_PB]---[/Stop_PB]---[/E_Stop]---(S:Running)---
   [Running]-----------------------------(Running)----  (seal-in)

2. INTERLOCK:
   [Running]---[Pressure_OK]---[Temp_OK]---(Enable_Operation)---

3. TIMER SEQUENCE:
   [Start_Cycle]---(TON:Warmup_Timer, 5000ms)---
   [Warmup_Timer.DN]---(Process_Ready)---

4. COUNTER:
   [Cycle_Complete]---(CTU:Part_Counter, preset=9999)---

5. ANALOG WITH ENABLE:
   [System_Running]---(AO:temperature, min=20, max=80, step=0.5)---

Generate 10-20 rungs that show a complete control sequence for the machine type.

Output valid JSON only, no markdown formatting."""

LADDER_GENERATION_USER_PROMPT = """Generate a REALISTIC ladder logic program for this industrial machine:

Machine Type: {machine_type}
Description: {description}

MACHINE OUTPUT FIELDS (sensor/actuator values to control):
{fields_section}

SIMULATION BEHAVIOR:
{formulas_section}

REQUIREMENTS:
1. Create 10-20 rungs showing realistic PLC control logic
2. Include these control patterns:
   - Start/Stop sequence with seal-in latch
   - Emergency stop interlock
   - System ready/enable logic
   - Timers for warmup, cycle timing, or delays
   - At least one counter for production/cycle tracking
   - Interlocks between related fields

3. For each machine field listed above, create logic that drives it:
   - Boolean fields: Use output coils controlled by conditions
   - Numeric fields: Use analog_output with enable conditions
   - Use the EXACT field names - no unit suffixes

4. Add internal control variables:
   - System_Ready, Cycle_Active, Process_Enable, etc.
   - Timer done bits (.DN) for sequencing
   - Counter bits for tracking

5. Show logical relationships:
   - Pressure must be OK before force is applied
   - Temperature affects other operations
   - State changes based on process completion

EXAMPLE STRUCTURE for a Hydraulic Press:
{{
  "ladder_program": {{
    "rungs": [
      {{
        "description": "Start/Stop Latch - Latches system ON with Start, OFF with Stop or E-Stop",
        "elements": [
          {{"type": "contact", "name": "Start_PB"}},
          {{"type": "inverted_contact", "name": "Stop_PB"}},
          {{"type": "inverted_contact", "name": "E_Stop"}},
          {{"type": "set_coil", "name": "System_Running"}}
        ]
      }},
      {{
        "description": "System Running Seal-in",
        "elements": [
          {{"type": "contact", "name": "System_Running"}},
          {{"type": "output", "name": "System_Running"}}
        ]
      }},
      {{
        "description": "Stop System - Any stop condition resets running state",
        "elements": [
          {{"type": "contact", "name": "Stop_PB"}},
          {{"type": "reset_coil", "name": "System_Running"}}
        ]
      }},
      {{
        "description": "Warmup Timer - 3 second delay after system start",
        "elements": [
          {{"type": "contact", "name": "System_Running"}},
          {{"type": "timer", "name": "Warmup_TMR", "preset_ms": 3000, "timer_type": "TON"}}
        ]
      }},
      {{
        "description": "System Ready - Warmup complete and no faults",
        "elements": [
          {{"type": "contact", "name": "Warmup_TMR.DN"}},
          {{"type": "inverted_contact", "name": "Fault"}},
          {{"type": "output", "name": "System_Ready"}}
        ]
      }},
      {{
        "description": "Pressure Control - Build pressure when system ready",
        "elements": [
          {{"type": "contact", "name": "System_Ready"}},
          {{"type": "analog_output", "name": "pressure", "min_value": 0, "max_value": 100, "step": 2.0}}
        ]
      }},
      {{
        "description": "Pressure OK Interlock - Enable when system ready (pressure builds automatically)",
        "elements": [
          {{"type": "contact", "name": "System_Ready"}},
          {{"type": "contact", "name": "Warmup_TMR.DN"}},
          {{"type": "output", "name": "Pressure_OK"}}
        ]
      }},
      {{
        "description": "Force Output - Only apply force when pressure is adequate",
        "elements": [
          {{"type": "contact", "name": "Pressure_OK"}},
          {{"type": "contact", "name": "Cycle_Active"}},
          {{"type": "analog_output", "name": "force", "min_value": 0, "max_value": 500, "step": 10.0}}
        ]
      }},
      {{
        "description": "Temperature Monitoring - Active when system running",
        "elements": [
          {{"type": "contact", "name": "System_Running"}},
          {{"type": "analog_output", "name": "temperature", "min_value": 20, "max_value": 85, "step": 0.5}}
        ]
      }},
      {{
        "description": "Cycle Timer - Process cycle duration",
        "elements": [
          {{"type": "contact", "name": "Cycle_Active"}},
          {{"type": "timer", "name": "Cycle_TMR", "preset_ms": 5000, "timer_type": "TON"}}
        ]
      }},
      {{
        "description": "Cycle Complete - Timer done signals end of cycle",
        "elements": [
          {{"type": "contact", "name": "Cycle_TMR.DN"}},
          {{"type": "output", "name": "Cycle_Complete"}}
        ]
      }},
      {{
        "description": "Part Counter - Count completed cycles",
        "elements": [
          {{"type": "contact", "name": "Cycle_Complete"}},
          {{"type": "counter", "name": "Part_Counter", "preset": 9999, "counter_type": "CTU"}}
        ]
      }},
      {{
        "description": "Running State Output - Maps to machine state field",
        "elements": [
          {{"type": "contact", "name": "System_Running"}},
          {{"type": "output", "name": "state"}}
        ]
      }}
    ]
  }},
  "io_mapping": {{
    "inputs": ["Start_PB", "Stop_PB", "E_Stop", "Cycle_Start"],
    "outputs": ["state", "pressure", "force", "temperature"],
    "internal": ["System_Running", "System_Ready", "Pressure_OK", "Cycle_Active", "Cycle_Complete", "Warmup_TMR.DN", "Cycle_TMR.DN", "Part_Counter.CV"]
  }},
  "rationale": "Implements a proper industrial control sequence with start/stop latch, warmup timer, pressure interlock before force application, cycle timing, and part counting. The logic ensures safe operation by requiring adequate pressure before applying force."
}}

NOW generate realistic ladder logic for the {machine_type}. Use the exact field names provided. Include timers, counters, interlocks, and proper sequencing that reflects how this machine would actually be controlled."""
