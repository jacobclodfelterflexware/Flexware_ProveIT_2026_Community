"""SparkMES payload generator service with cycle state machine."""

import copy
import logging
import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CycleState(Enum):
    """Cycle state machine states."""
    IDLE = "idle"
    IN_CYCLE = "in_cycle"
    COMPLETING = "completing"


@dataclass
class MachineState:
    """Persistent state for a machine's SparkMES simulation."""
    cycle_state: CycleState = CycleState.IDLE
    time_in_cycle: float = 0.0
    current_serial: str = field(default_factory=lambda: str(uuid.uuid4()))
    outfeed_count: int = 0
    infeed_count: int = 0
    scrap_count: int = 0
    part_code: int = 1
    cycle_start_flag: bool = False
    cycle_complete_flag: bool = False
    last_t: float = 0.0


class SparkMESGenerator:
    """Generates SparkMES payloads with correlated telemetry values."""

    def __init__(self):
        # Persistent state per machine
        self._machine_states: Dict[str, MachineState] = {}

    def _get_state(self, machine_id: str) -> MachineState:
        """Get or create machine state."""
        if machine_id not in self._machine_states:
            self._machine_states[machine_id] = MachineState()
        return self._machine_states[machine_id]

    def _find_running_state(self, telemetry: dict) -> bool:
        """Find running state from telemetry using common field names."""
        # Auto-detect from common field names
        for key in ['is_running', 'running', 'status', 'active', 'is_active', 'machine_running']:
            if key in telemetry:
                val = telemetry[key]
                if isinstance(val, bool):
                    return val
                if isinstance(val, str):
                    return val.lower() in ('running', 'active', 'on', 'true', '1')
                return bool(val)

        # Default to running if no indicator found
        return True

    def _find_count_value(self, telemetry: dict) -> Optional[int]:
        """Find part count from telemetry if available."""
        # Auto-detect from common field names
        for key in ['part_count', 'cycle_count', 'count', 'parts', 'cycles', 'total_count']:
            if key in telemetry:
                try:
                    return int(telemetry[key])
                except (ValueError, TypeError):
                    pass

        return None

    def _find_process_data(self, telemetry: dict) -> Dict[str, Any]:
        """Extract process data from telemetry for ProcessData folder."""
        process_data = {}

        # Look for common process data fields
        process_fields = [
            'temperature', 'temp', 'temperature_c', 'temperature_f',
            'pressure', 'pressure_bar', 'pressure_psi',
            'speed', 'rpm', 'velocity',
            'power', 'power_kw', 'current', 'voltage',
            'flow', 'flow_rate',
            'humidity', 'vibration', 'torque'
        ]

        for key in telemetry:
            key_lower = key.lower()
            # Include if it matches process field patterns
            if any(pf in key_lower for pf in process_fields):
                process_data[key] = telemetry[key]

        return process_data

    def _update_cycle_state(
        self,
        state: MachineState,
        is_running: bool,
        t: float,
        cycle_time_seconds: float = 30.0,
        scrap_rate: float = 0.01
    ) -> None:
        """Update the cycle state machine based on running state and time."""
        if state.last_t == 0:
            state.last_t = t

        dt = t - state.last_t
        state.last_t = t

        # Reset transient flags
        state.cycle_start_flag = False
        state.cycle_complete_flag = False

        if not is_running:
            # Machine not running - go to IDLE
            state.cycle_state = CycleState.IDLE
            state.time_in_cycle = 0
            return

        # Machine is running - progress through cycle
        if state.cycle_state == CycleState.IDLE:
            # Start a new cycle
            state.cycle_state = CycleState.IN_CYCLE
            state.cycle_start_flag = True
            state.time_in_cycle = 0
            state.current_serial = str(uuid.uuid4())
            state.infeed_count += 1
            logger.debug(f"Cycle started, serial={state.current_serial}")

        elif state.cycle_state == CycleState.IN_CYCLE:
            state.time_in_cycle += dt

            # Check if cycle is complete
            if state.time_in_cycle >= cycle_time_seconds:
                state.cycle_state = CycleState.COMPLETING
                state.cycle_complete_flag = True

                # Determine if this part is scrap
                if random.random() < scrap_rate:
                    state.scrap_count += 1
                    logger.debug(f"Part scrapped, scrap_count={state.scrap_count}")
                else:
                    state.outfeed_count += 1
                    logger.debug(f"Part completed, outfeed_count={state.outfeed_count}")

                # Cycle part code (1-5)
                state.part_code = (state.part_code % 5) + 1

        elif state.cycle_state == CycleState.COMPLETING:
            # Transition back to IDLE for next cycle
            state.cycle_state = CycleState.IDLE
            state.time_in_cycle = 0

    def _update_tag_values(
        self,
        tags: list,
        state: MachineState,
        telemetry: dict,
        is_running: bool
    ) -> None:
        """Recursively update tag values in the SparkMES structure."""
        for tag in tags:
            if tag.get("tagType") == "Folder" and tag.get("tags"):
                self._update_tag_values(tag["tags"], state, telemetry, is_running)
            elif tag.get("tagType") == "AtomicTag":
                self._update_atomic_tag(tag, state, telemetry, is_running)

    def _update_atomic_tag(
        self,
        tag: dict,
        state: MachineState,
        telemetry: dict,
        is_running: bool
    ) -> None:
        """Update a single atomic tag's value based on its name."""
        name = tag.get("name", "")

        # Map tag names to dynamic values
        if name == "SerialNumber":
            tag["value"] = state.current_serial
        elif name == "CycleComplete":
            tag["value"] = state.cycle_complete_flag
        elif name == "CycleStart":
            tag["value"] = state.cycle_start_flag
        elif name == "Outfeed":
            tag["value"] = state.outfeed_count
        elif name == "Infeed":
            tag["value"] = state.infeed_count
        elif name == "Scrap":
            tag["value"] = state.scrap_count
        elif name == "Running":
            tag["value"] = is_running
        elif name == "Paused":
            tag["value"] = not is_running and state.cycle_state != CycleState.IDLE
        elif name == "TimeInCycle":
            tag["value"] = int(state.time_in_cycle)
        elif name == "PartCode":
            tag["value"] = state.part_code
        elif name == "OutOfSpec":
            tag["value"] = is_running and random.random() < 0.01  # 1% chance when running
        elif name == "Light Screen Tripped":
            tag["value"] = random.random() < 0.001  # 0.1% chance
        elif name == "E-Stop":
            tag["value"] = random.random() < 0.0005  # 0.05% chance
        # ProcessData tags - map to telemetry values
        elif name.startswith("ProcessData"):
            process_data = self._find_process_data(telemetry)
            process_items = list(process_data.items())
            # Extract index from name (ProcessData1 -> index 0)
            try:
                idx = int(name.replace("ProcessData", "")) - 1
                if 0 <= idx < len(process_items):
                    tag["value"] = process_items[idx][1]
            except ValueError:
                pass
        elif name.startswith("ConsSerial"):
            # ConsSerial tags can hold related serial numbers
            tag["value"] = state.current_serial if name == "ConsSerial1" else ""

    def flatten_tags(self, tags: list, prefix: str = "") -> list[tuple[str, Any]]:
        """Flatten nested tag hierarchy into (topic_path_suffix, value) pairs.

        Walks the tag tree and returns a flat list suitable for publishing
        each AtomicTag value to its own MQTT topic.
        """
        result = []
        for tag in tags:
            name = tag.get("name", "")
            path = f"{prefix}/{name}" if prefix else name

            if tag.get("tagType") == "Folder" and tag.get("tags"):
                result.extend(self.flatten_tags(tag["tags"], path))
            elif tag.get("tagType") == "AtomicTag":
                result.append((path, tag.get("value")))
        return result

    def generate_payload(
        self,
        machine_id: str,
        sparkmes_template: dict,
        telemetry: dict,
        iteration: int,
        t: float,
        cycle_time_seconds: float = 30.0,
        scrap_rate: float = 0.01
    ) -> dict:
        """
        Generate a SparkMES payload by updating the template with simulated values.

        Args:
            machine_id: Unique machine identifier for state tracking
            sparkmes_template: The stored SparkMES structure from machine definition
            telemetry: Current telemetry payload for correlation
            iteration: Publish iteration counter
            t: Current timestamp
            cycle_time_seconds: Cycle time for simulation (default 30s)
            scrap_rate: Scrap rate for simulation (default 1%)

        Returns:
            Complete SparkMES payload dictionary with updated values
        """
        # Get or create machine state
        state = self._get_state(machine_id)

        # Determine running state from telemetry
        is_running = self._find_running_state(telemetry)

        # Update cycle state machine
        self._update_cycle_state(state, is_running, t, cycle_time_seconds, scrap_rate)

        # Deep copy template to avoid mutating the original
        payload = copy.deepcopy(sparkmes_template)

        # Update tag values in the structure
        if "tags" in payload:
            self._update_tag_values(payload["tags"], state, telemetry, is_running)

        return payload

    def reset_state(self, machine_id: str) -> None:
        """Reset state for a machine (e.g., when machine stops)."""
        if machine_id in self._machine_states:
            del self._machine_states[machine_id]
            logger.info(f"Reset SparkMES state for machine {machine_id}")


# Singleton instance
sparkmes_generator = SparkMESGenerator()
