"""Main ladder logic simulator engine."""
import asyncio
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .ladder_rung import Rung
from .ladder_elements import Timer, Counter

logger = logging.getLogger(__name__)


@dataclass
class SimulatorStats:
    """Statistics for the simulator."""
    scan_count: int = 0
    last_scan_time_ms: float = 0.0
    avg_scan_time_ms: float = 0.0
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None


class LadderSimulator:
    """Lightweight ladder logic simulator.

    Executes ladder logic programs with configurable scan cycle timing.
    Provides programmatic I/O access and ASCII rendering.

    Example:
        simulator = LadderSimulator()
        simulator.load_program([rung1, rung2])
        await simulator.start()

        # Write inputs
        simulator.write_io("Start", True)

        # Read outputs
        outputs = simulator.read_io()
    """

    def __init__(self, scan_time_ms: int = 20):
        """Initialize the simulator.

        Args:
            scan_time_ms: Time between scan cycles in milliseconds
        """
        self.rungs: List[Rung] = []
        self.io_state: Dict[str, Any] = {}
        self.running: bool = False
        self.scan_time_ms: int = scan_time_ms
        self._task: Optional[asyncio.Task] = None
        self._timers: List[Timer] = []
        self._counters: List[Counter] = []
        self.stats = SimulatorStats()
        # Auto-simulation state
        self.auto_simulate: bool = False
        self.auto_sim_patterns: Dict[str, Dict] = {}
        # External values injected from MQTT - these override simulated values
        self.external_values: Dict[str, Any] = {}

    def load_program(self, rungs: List[Rung]):
        """Load a ladder program.

        Args:
            rungs: List of Rung objects to execute
        """
        self.rungs = rungs
        self._timers = []
        self._counters = []

        # Clear old I/O state and external values before loading new program
        self.io_state = {}
        self.external_values = {}

        # Initialize I/O state for all variables
        for rung in self.rungs:
            for elem in rung.elements:
                name = elem.name
                if name not in self.io_state:
                    self.io_state[name] = False

                # Collect timers and counters for updates
                if isinstance(elem, Timer):
                    self._timers.append(elem)
                elif isinstance(elem, Counter):
                    self._counters.append(elem)

        # Reset statistics
        self.stats = SimulatorStats()
        logger.info(f"Loaded program with {len(rungs)} rungs")

    def scan_cycle(self):
        """Execute one PLC scan cycle.

        Evaluates all rungs in order, updating outputs based on inputs.
        """
        import time
        start_time = time.time()

        # Update auto-simulated inputs if enabled
        if self.auto_simulate:
            self._update_auto_simulation()

        # Update timers with their input states
        for timer in self._timers:
            # Get the timer's enable input (typically the rung result up to the timer)
            # For simplicity, we check if timer.name exists in io_state
            input_state = self.io_state.get(f"_{timer.name}_EN", False)
            timer.update(input_state, self.io_state)

        # Update counters with their input states
        for counter in self._counters:
            input_state = self.io_state.get(f"_{counter.name}_CU", False)
            counter.update(input_state, self.io_state)

        # Evaluate all rungs
        for rung in self.rungs:
            try:
                rung.evaluate(self.io_state)
            except Exception as e:
                logger.warning(f"Rung evaluation error ({rung.description}): {e}")

        # Re-apply external values AFTER rung evaluation
        # This ensures MQTT-injected values override simulated analog outputs
        for name, value in self.external_values.items():
            self.io_state[name] = value

        # Update statistics
        elapsed_ms = (time.time() - start_time) * 1000
        self.stats.scan_count += 1
        self.stats.last_scan_time_ms = elapsed_ms

        # Running average
        if self.stats.avg_scan_time_ms == 0:
            self.stats.avg_scan_time_ms = elapsed_ms
        else:
            self.stats.avg_scan_time_ms = (
                0.9 * self.stats.avg_scan_time_ms + 0.1 * elapsed_ms
            )

    def read_io(self, names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Read I/O values.

        Args:
            names: Optional list of names to read. If None, returns all.

        Returns:
            Dictionary of I/O values
        """
        if names is None:
            return self.io_state.copy()
        return {name: self.io_state.get(name, None) for name in names}

    def write_io(self, name: str, value: Any, strict: bool = True, external: bool = False):
        """Write a single I/O value.

        Args:
            name: Variable name
            value: Value to write
            strict: If True, only write to variables that exist in the current program.
                    If False, create new variables if they don't exist.
            external: If True, mark this as an externally-controlled value that persists
                     across scan cycles (e.g., MQTT values).
        """
        if strict and name not in self.io_state:
            logger.debug(f"Ignoring write to unknown variable: {name} (not in current program)")
            return
        self.io_state[name] = value
        if external:
            self.external_values[name] = value
            logger.debug(f"External write I/O: {name} = {value}")
        else:
            logger.debug(f"Write I/O: {name} = {value}")

    def write_multiple_io(self, values: Dict[str, Any], strict: bool = True, external: bool = False):
        """Write multiple I/O values.

        Args:
            values: Dictionary of name -> value pairs
            strict: If True, only write to variables that exist in the current program.
                    If False, create new variables if they don't exist.
            external: If True, mark these as externally-controlled values that persist
                     across scan cycles (e.g., MQTT values).
        """
        written = {}
        ignored = []
        for name, value in values.items():
            if strict and name not in self.io_state:
                ignored.append(name)
                continue
            self.io_state[name] = value
            if external:
                self.external_values[name] = value
            written[name] = value
        if written:
            log_prefix = "External write" if external else "Write"
            # Use info level for external writes (MQTT) to make them visible
            if external:
                logger.info(f"{log_prefix} multiple I/O: {written}")
            else:
                logger.debug(f"{log_prefix} multiple I/O: {written}")
        if ignored:
            logger.debug(f"Ignored unknown variables: {ignored}")

    async def start(self):
        """Start the scan cycle loop.

        Runs continuously until stop() is called.
        """
        if self.running:
            logger.warning("Simulator already running")
            return

        self.running = True
        self.stats.started_at = datetime.now()
        self.stats.stopped_at = None
        logger.info(f"Starting ladder simulator (scan time: {self.scan_time_ms}ms)")

        while self.running:
            try:
                self.scan_cycle()
            except Exception as e:
                logger.error(f"Error in scan cycle #{self.stats.scan_count}: {e}")
                self.stats.scan_count += 1  # Still count failed scans
            await asyncio.sleep(self.scan_time_ms / 1000)

    def stop(self):
        """Stop the scan cycle loop."""
        if not self.running:
            logger.warning("Simulator not running")
            return

        self.running = False
        self.stats.stopped_at = datetime.now()
        logger.info(
            f"Stopped ladder simulator after {self.stats.scan_count} scan cycles"
        )

    def single_scan(self):
        """Execute a single scan cycle without starting the loop.

        Useful for step-by-step debugging or immediate evaluation.
        """
        self.scan_cycle()

    def get_status(self) -> Dict[str, Any]:
        """Get simulator status.

        Returns:
            Dictionary with status information
        """
        return {
            "running": self.running,
            "auto_simulate": self.auto_simulate,
            "scan_time_ms": self.scan_time_ms,
            "rung_count": len(self.rungs),
            "io_count": len(self.io_state),
            "stats": {
                "scan_count": self.stats.scan_count,
                "last_scan_time_ms": round(self.stats.last_scan_time_ms, 3),
                "avg_scan_time_ms": round(self.stats.avg_scan_time_ms, 3),
                "started_at": (
                    self.stats.started_at.isoformat()
                    if self.stats.started_at
                    else None
                ),
                "stopped_at": (
                    self.stats.stopped_at.isoformat()
                    if self.stats.stopped_at
                    else None
                ),
            },
        }

    def reset(self):
        """Reset the simulator to initial state.

        Clears all I/O values and resets timers/counters.
        """
        # Reset all I/O to False
        for name in self.io_state:
            self.io_state[name] = False

        # Reset timers
        for timer in self._timers:
            timer.reset()

        # Reset counters
        for counter in self._counters:
            counter.reset()

        # Reset statistics
        self.stats = SimulatorStats()
        logger.info("Simulator reset")

    def enable_auto_simulation(self, inputs: Optional[List[str]] = None):
        """Enable automatic input simulation.

        This makes the ladder diagram dynamic by automatically toggling inputs
        in realistic patterns (pulse behavior like button presses).

        Args:
            inputs: List of input names to auto-simulate. If None, simulates all inputs.
        """
        import time
        self.auto_simulate = True
        target_inputs = inputs or list(self.get_inputs().keys())

        current_time = time.time() * 1000  # ms

        for i, name in enumerate(target_inputs):
            # Stagger the patterns so they don't all toggle at once
            self.auto_sim_patterns[name] = {
                'type': 'pulse',  # pulse: OFF -> ON briefly -> OFF
                'period_ms': 2000 + (i * 700),  # Different periods for each input
                'pulse_duration_ms': 400,  # How long the pulse stays ON
                'last_change': current_time,
                'pulse_start': None,
            }

        logger.info(f"Auto-simulation enabled for {len(target_inputs)} inputs")

    def disable_auto_simulation(self):
        """Disable automatic input simulation."""
        self.auto_simulate = False
        self.auto_sim_patterns = {}
        logger.info("Auto-simulation disabled")

    def _update_auto_simulation(self):
        """Update auto-simulated inputs during scan cycle."""
        if not self.auto_simulate:
            return

        import time
        current_time = time.time() * 1000  # ms

        for name, pattern in self.auto_sim_patterns.items():
            if pattern['type'] == 'pulse':
                # Pulse: OFF -> ON for pulse_duration -> OFF, then wait for period
                if pattern['pulse_start'] is None:
                    # Not in pulse, check if time to start a new pulse
                    elapsed = current_time - pattern['last_change']
                    if elapsed >= pattern['period_ms']:
                        self.io_state[name] = True
                        pattern['pulse_start'] = current_time
                        pattern['last_change'] = current_time
                        logger.info(f"Auto-sim: {name} -> TRUE (pulse start)")
                else:
                    # In pulse, check if time to end
                    pulse_elapsed = current_time - pattern['pulse_start']
                    if pulse_elapsed >= pattern['pulse_duration_ms']:
                        self.io_state[name] = False
                        pattern['pulse_start'] = None
                        pattern['last_change'] = current_time
                        logger.info(f"Auto-sim: {name} -> FALSE (pulse end)")

    def get_inputs(self) -> Dict[str, bool]:
        """Get all input values (contacts).

        Returns dictionary of input name -> value.
        """
        inputs = {}
        for rung in self.rungs:
            for elem in rung.get_inputs():
                name = elem.name
                inputs[name] = self.io_state.get(name, False)
        return inputs

    def get_outputs(self) -> Dict[str, Any]:
        """Get all output values (coils and analog outputs).

        Returns dictionary of output name -> value.
        Values can be boolean (for regular outputs) or numeric (for analog outputs).
        """
        outputs = {}
        for rung in self.rungs:
            output = rung.get_output()
            if output:
                outputs[output.name] = self.io_state.get(output.name, False)
        return outputs


# Singleton instance for global access
_simulator: Optional[LadderSimulator] = None


def get_ladder_simulator() -> LadderSimulator:
    """Get the global ladder simulator instance."""
    global _simulator
    if _simulator is None:
        _simulator = LadderSimulator()
    return _simulator


def reset_ladder_simulator():
    """Reset the global ladder simulator instance."""
    global _simulator
    if _simulator:
        _simulator.stop()
    _simulator = LadderSimulator()
    return _simulator
