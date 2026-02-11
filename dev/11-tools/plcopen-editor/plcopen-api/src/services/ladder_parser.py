"""Parser for ladder logic programs in JSON and text formats."""
import re
import logging
from typing import Any, Dict, List, Optional, Union

from .ladder_elements import (
    Contact,
    InvertedContact,
    Output,
    SetCoil,
    ResetCoil,
    Timer,
    Counter,
    AnalogOutput,
)
from .ladder_rung import Rung

logger = logging.getLogger(__name__)


def parse_ladder_json(data: Dict[str, Any]) -> List[Rung]:
    """Parse ladder program from JSON format.

    Expected JSON format:
    {
        "rungs": [
            {
                "description": "Motor Control",
                "elements": [
                    {"type": "contact", "name": "Start"},
                    {"type": "inverted_contact", "name": "Stop"},
                    {"type": "output", "name": "Motor"}
                ]
            }
        ]
    }

    Element types:
    - contact: Normally open contact
    - inverted_contact: Normally closed contact
    - output: Output coil
    - set_coil: Set/Latch coil
    - reset_coil: Reset/Unlatch coil
    - timer: Timer (TON/TOFF/PULSE)
    - counter: Counter (CTU/CTD/CTUD)

    Args:
        data: JSON dictionary with program definition

    Returns:
        List of Rung objects
    """
    rungs = []

    if "rungs" not in data:
        raise ValueError("JSON must contain 'rungs' array")

    for i, rung_data in enumerate(data["rungs"]):
        try:
            rung = _parse_rung_json(rung_data, i + 1)
            rungs.append(rung)
        except Exception as e:
            logger.error(f"Error parsing rung {i + 1}: {e}")
            raise ValueError(f"Error in rung {i + 1}: {e}")

    return rungs


def _parse_rung_json(rung_data: Dict[str, Any], rung_num: int) -> Rung:
    """Parse a single rung from JSON.

    Args:
        rung_data: Dictionary with rung definition
        rung_num: Rung number for error messages

    Returns:
        Rung object
    """
    description = rung_data.get("description", f"Rung {rung_num}")
    elements_data = rung_data.get("elements", [])

    if not elements_data:
        raise ValueError("Rung must have at least one element")

    elements = []
    for elem_data in elements_data:
        elem = _parse_element_json(elem_data)
        elements.append(elem)

    return Rung(elements=elements, description=description)


def _parse_element_json(elem_data: Dict[str, Any]):
    """Parse a single element from JSON.

    Args:
        elem_data: Dictionary with element definition

    Returns:
        Element object
    """
    elem_type = elem_data.get("type", "").lower()
    name = elem_data.get("name")

    if not name:
        raise ValueError("Element must have a 'name'")

    if elem_type == "contact":
        return Contact(_name=name)

    elif elem_type == "inverted_contact" or elem_type == "nc_contact":
        return InvertedContact(_name=name)

    elif elem_type == "output" or elem_type == "coil":
        negated = elem_data.get("negated", False)
        return Output(_name=name, negated=negated)

    elif elem_type == "set_coil" or elem_type == "latch":
        return SetCoil(_name=name)

    elif elem_type == "reset_coil" or elem_type == "unlatch":
        return ResetCoil(_name=name)

    elif elem_type == "timer":
        preset = elem_data.get("preset_ms", elem_data.get("preset", 1000))
        timer_type = elem_data.get("timer_type", "TON").upper()
        return Timer(_name=name, preset_ms=preset, timer_type=timer_type)

    elif elem_type == "counter":
        preset = elem_data.get("preset", 10)
        counter_type = elem_data.get("counter_type", "CTU").upper()
        return Counter(_name=name, preset=preset, counter_type=counter_type)

    elif elem_type == "analog_output":
        min_value = elem_data.get("min_value", 0.0)
        max_value = elem_data.get("max_value", 100.0)
        step = elem_data.get("step", 1.0)
        return AnalogOutput(
            _name=name,
            min_value=float(min_value),
            max_value=float(max_value),
            step=float(step),
        )

    else:
        raise ValueError(f"Unknown element type: {elem_type}")


def parse_ladder_text(text: str) -> List[Rung]:
    """Parse ladder program from simple text format.

    Text format examples:
        RUNG "Motor Control": Start AND NOT Stop -> Motor
        RUNG "Alarm": Sensor1 OR Sensor2 -> Alarm
        RUNG: Input1 -> Output1

    Syntax:
        RUNG ["description"]: <logic> -> <output>

        Logic elements:
        - Name: Normally open contact
        - NOT Name: Normally closed contact
        - AND: Series connection (implicit between contacts)
        - OR: Parallel connection (not yet supported)

    Args:
        text: Text program definition

    Returns:
        List of Rung objects
    """
    rungs = []
    lines = text.strip().split("\n")

    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        try:
            rung = _parse_rung_text(line, i + 1)
            if rung:
                rungs.append(rung)
        except Exception as e:
            logger.error(f"Error parsing line {i + 1}: {e}")
            raise ValueError(f"Syntax error on line {i + 1}: {e}")

    return rungs


def _parse_rung_text(line: str, line_num: int) -> Optional[Rung]:
    """Parse a single rung from text line.

    Args:
        line: Text line to parse
        line_num: Line number for error messages

    Returns:
        Rung object or None if line is empty/comment
    """
    # Match RUNG pattern
    # RUNG "desc": logic -> output
    # RUNG: logic -> output
    rung_match = re.match(
        r'RUNG\s*(?:"([^"]*)")?\s*:\s*(.+?)\s*->\s*(\w+)',
        line,
        re.IGNORECASE,
    )

    if not rung_match:
        # Try simple format: logic -> output
        simple_match = re.match(r"(.+?)\s*->\s*(\w+)", line)
        if simple_match:
            logic_str = simple_match.group(1).strip()
            output_name = simple_match.group(2).strip()
            description = f"Rung {line_num}"
        else:
            raise ValueError(f"Invalid rung syntax: {line}")
    else:
        description = rung_match.group(1) or f"Rung {line_num}"
        logic_str = rung_match.group(2).strip()
        output_name = rung_match.group(3).strip()

    # Parse logic expression
    elements = _parse_logic_text(logic_str)

    # Add output
    if output_name.startswith("!") or output_name.startswith("/"):
        elements.append(Output(_name=output_name[1:], negated=True))
    elif output_name.upper().startswith("S_"):
        elements.append(SetCoil(_name=output_name[2:]))
    elif output_name.upper().startswith("R_"):
        elements.append(ResetCoil(_name=output_name[2:]))
    else:
        elements.append(Output(_name=output_name))

    return Rung(elements=elements, description=description)


def _parse_logic_text(logic_str: str) -> List:
    """Parse logic expression from text.

    Supports:
    - Contact names (normally open)
    - NOT Name or /Name (normally closed)
    - AND (explicit or implicit between contacts)

    Args:
        logic_str: Logic expression string

    Returns:
        List of element objects
    """
    elements = []

    # Split by AND (case insensitive)
    parts = re.split(r"\s+AND\s+", logic_str, flags=re.IGNORECASE)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Check for NOT or / prefix
        if part.upper().startswith("NOT "):
            name = part[4:].strip()
            elements.append(InvertedContact(_name=name))
        elif part.startswith("/"):
            name = part[1:].strip()
            elements.append(InvertedContact(_name=name))
        else:
            elements.append(Contact(_name=part))

    return elements


def parse_ladder(source: Union[str, Dict[str, Any]]) -> List[Rung]:
    """Parse ladder program from either JSON or text format.

    Auto-detects format based on input type.

    Args:
        source: Either a JSON dict or text string

    Returns:
        List of Rung objects
    """
    if isinstance(source, dict):
        return parse_ladder_json(source)
    elif isinstance(source, str):
        # Try to detect if it's JSON
        stripped = source.strip()
        if stripped.startswith("{"):
            import json
            try:
                data = json.loads(source)
                return parse_ladder_json(data)
            except json.JSONDecodeError:
                pass
        # Fall back to text format
        return parse_ladder_text(source)
    else:
        raise ValueError(f"Invalid source type: {type(source)}")


# Example programs for testing
EXAMPLE_PROGRAMS = {
    "simple": {
        "rungs": [
            {
                "description": "Simple Copy",
                "elements": [
                    {"type": "contact", "name": "Input1"},
                    {"type": "output", "name": "Output1"},
                ],
            }
        ]
    },
    "motor_control": {
        "rungs": [
            {
                "description": "Motor Start/Stop",
                "elements": [
                    {"type": "contact", "name": "Start"},
                    {"type": "inverted_contact", "name": "Stop"},
                    {"type": "output", "name": "Motor"},
                ],
            }
        ]
    },
    "latch": {
        "rungs": [
            {
                "description": "Set Latch",
                "elements": [
                    {"type": "contact", "name": "SetButton"},
                    {"type": "set_coil", "name": "Latch"},
                ],
            },
            {
                "description": "Reset Latch",
                "elements": [
                    {"type": "contact", "name": "ResetButton"},
                    {"type": "reset_coil", "name": "Latch"},
                ],
            },
        ]
    },
    "timer_demo": {
        "rungs": [
            {
                "description": "Delayed Start",
                "elements": [
                    {"type": "contact", "name": "Enable"},
                    {"type": "timer", "name": "T1", "preset_ms": 2000, "timer_type": "TON"},
                    {"type": "output", "name": "DelayedOutput"},
                ],
            }
        ]
    },
}


def get_example_program(name: str) -> Dict[str, Any]:
    """Get an example program by name.

    Args:
        name: Example program name

    Returns:
        JSON program definition
    """
    if name not in EXAMPLE_PROGRAMS:
        available = ", ".join(EXAMPLE_PROGRAMS.keys())
        raise ValueError(f"Unknown example: {name}. Available: {available}")
    return EXAMPLE_PROGRAMS[name]
