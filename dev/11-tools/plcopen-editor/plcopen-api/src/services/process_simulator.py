"""Process Simulation Engine - Simulates physical I/O behavior.

This module provides a framework for simulating physical machines/processes
that interact with the ladder logic simulator. Instead of manually toggling
inputs, the process simulator automatically changes I/O based on defined
physical behaviors.

Example: A conveyor belt simulation where:
- When Motor output is ON, the conveyor moves
- After X seconds of movement, Entry_Sensor triggers
- After more time, Exit_Sensor triggers
- Objects move through the system realistically
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .ladder_simulator import LadderSimulator

logger = logging.getLogger(__name__)


@dataclass
class ProcessVariable:
    """A physical process variable (not just boolean I/O).

    Used for continuous values like position, level, temperature.
    """
    name: str
    value: float = 0.0
    min_value: float = 0.0
    max_value: float = 100.0
    unit: str = ""


@dataclass
class TimedEvent:
    """An event scheduled to occur after a delay."""
    trigger_time: float  # When to trigger (absolute time)
    action: Callable[[], None]  # What to do
    description: str = ""
    cancelled: bool = False


class ProcessMachine(ABC):
    """Base class for simulated physical machines.

    Subclass this to create specific machine simulations.
    Each machine has access to the ladder simulator's I/O state.
    """

    def __init__(self, name: str):
        self.name = name
        self.enabled = True
        self.variables: Dict[str, ProcessVariable] = {}
        self._simulator: Optional["LadderSimulator"] = None
        self._pending_events: List[TimedEvent] = []
        self._last_update_time: float = 0.0

    def attach(self, simulator: "LadderSimulator"):
        """Attach this machine to a ladder simulator."""
        self._simulator = simulator
        self._last_update_time = time.time()
        self.on_attach()

    def on_attach(self):
        """Called when machine is attached to simulator. Override to initialize."""
        pass

    def read_output(self, name: str) -> bool:
        """Read a PLC output (coil) value."""
        if self._simulator:
            return self._simulator.io_state.get(name, False)
        return False

    def write_input(self, name: str, value: bool):
        """Write a PLC input (sensor) value."""
        if self._simulator:
            self._simulator.io_state[name] = value

    def schedule_event(self, delay_seconds: float, action: Callable[[], None], description: str = ""):
        """Schedule an action to occur after a delay."""
        trigger_time = time.time() + delay_seconds
        event = TimedEvent(trigger_time=trigger_time, action=action, description=description)
        self._pending_events.append(event)
        logger.debug(f"[{self.name}] Scheduled: {description} in {delay_seconds:.2f}s")

    def cancel_events(self, description_match: str = ""):
        """Cancel pending events, optionally matching description."""
        for event in self._pending_events:
            if not description_match or description_match in event.description:
                event.cancelled = True

    def process_events(self):
        """Process any pending timed events."""
        current_time = time.time()
        remaining_events = []

        for event in self._pending_events:
            if event.cancelled:
                continue
            if current_time >= event.trigger_time:
                try:
                    event.action()
                    logger.debug(f"[{self.name}] Executed: {event.description}")
                except Exception as e:
                    logger.error(f"[{self.name}] Event error: {e}")
            else:
                remaining_events.append(event)

        self._pending_events = remaining_events

    @abstractmethod
    def update(self, dt: float):
        """Update the machine simulation.

        Args:
            dt: Time elapsed since last update in seconds
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """Get machine status for display."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "variables": {k: v.value for k, v in self.variables.items()},
            "pending_events": len(self._pending_events),
        }


class ConveyorMachine(ProcessMachine):
    """Simulates a conveyor belt with entry and exit sensors.

    Physical behavior:
    - Motor output drives the conveyor
    - Objects enter periodically when conveyor is running
    - Entry_Sensor triggers when object arrives at entry point
    - Exit_Sensor triggers when object reaches exit point
    - Object clears exit sensor after passing through

    I/O Mapping:
    - Outputs (from PLC): Conveyor_Motor
    - Inputs (to PLC): Entry_Sensor, Exit_Sensor
    """

    def __init__(self, name: str = "Conveyor",
                 motor_output: str = "Conveyor_Motor",
                 entry_sensor: str = "Entry_Sensor",
                 exit_sensor: str = "Exit_Sensor",
                 belt_length: float = 10.0,  # Units
                 belt_speed: float = 2.0,    # Units per second
                 object_spawn_interval: float = 3.0):  # Seconds between objects
        super().__init__(name)

        # I/O names
        self.motor_output = motor_output
        self.entry_sensor = entry_sensor
        self.exit_sensor = exit_sensor

        # Physical parameters
        self.belt_length = belt_length
        self.belt_speed = belt_speed
        self.object_spawn_interval = object_spawn_interval

        # Entry and exit sensor positions
        self.entry_pos = 1.0  # Position on belt where entry sensor is
        self.exit_pos = belt_length - 1.0  # Position where exit sensor is

        # State
        self.objects: List[float] = []  # List of object positions on belt
        self._time_since_last_spawn = 0.0
        self._motor_was_on = False

    def on_attach(self):
        """Initialize I/O when attached."""
        self.write_input(self.entry_sensor, False)
        self.write_input(self.exit_sensor, False)

    def update(self, dt: float):
        """Update conveyor simulation."""
        motor_on = self.read_output(self.motor_output)

        if motor_on:
            # Move all objects
            movement = self.belt_speed * dt
            new_objects = []

            entry_triggered = False
            exit_triggered = False

            for pos in self.objects:
                new_pos = pos + movement

                # Check if object just passed entry sensor
                if pos < self.entry_pos <= new_pos:
                    entry_triggered = True

                # Check if object just passed exit sensor
                if pos < self.exit_pos <= new_pos:
                    exit_triggered = True

                # Keep object if still on belt
                if new_pos <= self.belt_length + 1.0:
                    new_objects.append(new_pos)
                else:
                    logger.debug(f"[{self.name}] Object exited belt")

            self.objects = new_objects

            # Update sensors based on object proximity
            # Entry sensor ON if any object is near entry position
            entry_active = any(abs(p - self.entry_pos) < 0.5 for p in self.objects)
            exit_active = any(abs(p - self.exit_pos) < 0.5 for p in self.objects)

            self.write_input(self.entry_sensor, entry_active)
            self.write_input(self.exit_sensor, exit_active)

            # Spawn new objects periodically
            self._time_since_last_spawn += dt
            if self._time_since_last_spawn >= self.object_spawn_interval:
                self.objects.append(0.0)  # New object at start of belt
                self._time_since_last_spawn = 0.0
                logger.debug(f"[{self.name}] New object spawned")

        else:
            # Motor off - sensors stay in current state
            # But clear spawn timer when stopped
            self._time_since_last_spawn = 0.0

        self._motor_was_on = motor_on
        self.process_events()

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status.update({
            "motor_on": self.read_output(self.motor_output),
            "objects": self.objects,
            "entry_sensor": self.read_output(self.entry_sensor) if self._simulator else False,
            "exit_sensor": self.read_output(self.exit_sensor) if self._simulator else False,
        })
        return status


class TankMachine(ProcessMachine):
    """Simulates a tank with fill/drain valves and level sensors.

    Physical behavior:
    - Fill_Valve output opens inlet, level rises
    - Drain_Valve output opens drain, level falls
    - Level_Low sensor activates when level < low threshold
    - Level_High sensor activates when level > high threshold

    I/O Mapping:
    - Outputs (from PLC): Fill_Valve, Drain_Valve
    - Inputs (to PLC): Level_Low, Level_High
    """

    def __init__(self, name: str = "Tank",
                 fill_valve: str = "Fill_Valve",
                 drain_valve: str = "Drain_Valve",
                 level_low: str = "Level_Low",
                 level_high: str = "Level_High",
                 tank_capacity: float = 100.0,  # Units (e.g., gallons)
                 fill_rate: float = 10.0,       # Units per second
                 drain_rate: float = 8.0,       # Units per second
                 low_threshold: float = 20.0,   # Low level threshold
                 high_threshold: float = 80.0): # High level threshold
        super().__init__(name)

        # I/O names
        self.fill_valve = fill_valve
        self.drain_valve = drain_valve
        self.level_low = level_low
        self.level_high = level_high

        # Physical parameters
        self.tank_capacity = tank_capacity
        self.fill_rate = fill_rate
        self.drain_rate = drain_rate
        self.low_threshold = low_threshold
        self.high_threshold = high_threshold

        # State
        self.variables["level"] = ProcessVariable(
            name="level", value=50.0, min_value=0.0,
            max_value=tank_capacity, unit="units"
        )

    def on_attach(self):
        """Initialize sensors based on current level."""
        level = self.variables["level"].value
        self.write_input(self.level_low, level <= self.low_threshold)
        self.write_input(self.level_high, level >= self.high_threshold)

    def update(self, dt: float):
        """Update tank simulation."""
        level_var = self.variables["level"]
        current_level = level_var.value

        fill_on = self.read_output(self.fill_valve)
        drain_on = self.read_output(self.drain_valve)

        # Calculate level change
        delta = 0.0
        if fill_on:
            delta += self.fill_rate * dt
        if drain_on:
            delta -= self.drain_rate * dt

        # Update level with clamping
        new_level = max(0.0, min(self.tank_capacity, current_level + delta))
        level_var.value = new_level

        # Update level sensors
        self.write_input(self.level_low, new_level <= self.low_threshold)
        self.write_input(self.level_high, new_level >= self.high_threshold)

        self.process_events()

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status.update({
            "level": self.variables["level"].value,
            "fill_on": self.read_output(self.fill_valve),
            "drain_on": self.read_output(self.drain_valve),
            "level_low_active": self._simulator.io_state.get(self.level_low, False) if self._simulator else False,
            "level_high_active": self._simulator.io_state.get(self.level_high, False) if self._simulator else False,
        })
        return status


class TrafficLightMachine(ProcessMachine):
    """Simulates traffic light with car detection sensors.

    Physical behavior:
    - Cars arrive randomly at North and East approaches
    - Car sensors detect waiting vehicles
    - Timer expires after vehicle leaves detection zone

    I/O Mapping:
    - Outputs (from PLC): Green_NS, Yellow_NS, Red_NS, Green_EW, Yellow_EW, Red_EW
    - Inputs (to PLC): Car_NS, Car_EW
    """

    def __init__(self, name: str = "TrafficLight",
                 car_ns: str = "Car_NS",
                 car_ew: str = "Car_EW",
                 green_ns: str = "Green_NS",
                 green_ew: str = "Green_EW",
                 avg_car_interval: float = 5.0):  # Average seconds between car arrivals
        super().__init__(name)

        # I/O names
        self.car_ns = car_ns
        self.car_ew = car_ew
        self.green_ns = green_ns
        self.green_ew = green_ew

        # Parameters
        self.avg_car_interval = avg_car_interval

        # State
        self._ns_car_waiting = False
        self._ew_car_waiting = False
        self._time_since_ns_car = 0.0
        self._time_since_ew_car = 0.0

        # Random intervals (will be regenerated)
        import random
        self._next_ns_car = random.uniform(1.0, avg_car_interval * 2)
        self._next_ew_car = random.uniform(1.0, avg_car_interval * 2)

    def on_attach(self):
        """Initialize sensors."""
        self.write_input(self.car_ns, False)
        self.write_input(self.car_ew, False)

    def update(self, dt: float):
        """Update traffic simulation."""
        import random

        self._time_since_ns_car += dt
        self._time_since_ew_car += dt

        # Spawn cars randomly
        if self._time_since_ns_car >= self._next_ns_car:
            self._ns_car_waiting = True
            self.write_input(self.car_ns, True)
            self._time_since_ns_car = 0.0
            self._next_ns_car = random.uniform(2.0, self.avg_car_interval * 2)
            logger.debug(f"[{self.name}] Car arrived at NS")

        if self._time_since_ew_car >= self._next_ew_car:
            self._ew_car_waiting = True
            self.write_input(self.car_ew, True)
            self._time_since_ew_car = 0.0
            self._next_ew_car = random.uniform(2.0, self.avg_car_interval * 2)
            logger.debug(f"[{self.name}] Car arrived at EW")

        # Cars leave when they get green light
        if self._ns_car_waiting and self.read_output(self.green_ns):
            # Schedule car to leave after a short delay
            self.schedule_event(1.5, lambda: self._clear_ns_car(), "NS car leaves")
            self._ns_car_waiting = False

        if self._ew_car_waiting and self.read_output(self.green_ew):
            self.schedule_event(1.5, lambda: self._clear_ew_car(), "EW car leaves")
            self._ew_car_waiting = False

        self.process_events()

    def _clear_ns_car(self):
        self.write_input(self.car_ns, False)

    def _clear_ew_car(self):
        self.write_input(self.car_ew, False)

    def get_status(self) -> Dict[str, Any]:
        status = super().get_status()
        status.update({
            "ns_car_waiting": self._ns_car_waiting,
            "ew_car_waiting": self._ew_car_waiting,
        })
        return status


class StartStopMachine(ProcessMachine):
    """Simulates simple start/stop pushbutton behavior.

    Physical behavior:
    - Start button: momentary pushbutton (auto-releases after press)
    - Stop button: momentary pushbutton (auto-releases after press)
    - Can simulate random button presses for testing

    I/O Mapping:
    - Inputs (to PLC): Start_PB, Stop_PB
    """

    def __init__(self, name: str = "Pushbuttons",
                 start_button: str = "Start",
                 stop_button: str = "Stop",
                 auto_cycle: bool = True,
                 cycle_run_time: float = 5.0,
                 cycle_stop_time: float = 3.0):
        super().__init__(name)

        self.start_button = start_button
        self.stop_button = stop_button
        self.auto_cycle = auto_cycle
        self.cycle_run_time = cycle_run_time
        self.cycle_stop_time = cycle_stop_time

        self._cycle_timer = 0.0
        self._in_run_phase = False
        self._button_release_pending = False

    def on_attach(self):
        """Initialize buttons."""
        self.write_input(self.start_button, False)
        self.write_input(self.stop_button, False)

        if self.auto_cycle:
            # Start with a start button press
            self._press_start()

    def _press_start(self):
        """Press start button momentarily."""
        self.write_input(self.start_button, True)
        self.schedule_event(0.2, lambda: self.write_input(self.start_button, False), "Release start")
        logger.debug(f"[{self.name}] Start button pressed")

    def _press_stop(self):
        """Press stop button momentarily."""
        self.write_input(self.stop_button, True)
        self.schedule_event(0.2, lambda: self.write_input(self.stop_button, False), "Release stop")
        logger.debug(f"[{self.name}] Stop button pressed")

    def update(self, dt: float):
        """Update pushbutton simulation."""
        if self.auto_cycle:
            self._cycle_timer += dt

            if not self._in_run_phase:
                # In stop phase - wait, then press start
                if self._cycle_timer >= self.cycle_stop_time:
                    self._press_start()
                    self._in_run_phase = True
                    self._cycle_timer = 0.0
            else:
                # In run phase - wait, then press stop
                if self._cycle_timer >= self.cycle_run_time:
                    self._press_stop()
                    self._in_run_phase = False
                    self._cycle_timer = 0.0

        self.process_events()


class ProcessSimulator:
    """Main process simulation engine.

    Manages multiple ProcessMachine instances and coordinates their
    updates with the ladder simulator.
    """

    def __init__(self):
        self.machines: Dict[str, ProcessMachine] = {}
        self._simulator: Optional["LadderSimulator"] = None
        self.running = False
        self.update_interval_ms = 50  # 50ms update rate
        self._task: Optional[asyncio.Task] = None
        self._last_update = 0.0

    def attach_simulator(self, simulator: "LadderSimulator"):
        """Attach the ladder simulator."""
        self._simulator = simulator
        # Attach all machines to the simulator
        for machine in self.machines.values():
            machine.attach(simulator)

    def add_machine(self, machine: ProcessMachine):
        """Add a machine to the simulation."""
        self.machines[machine.name] = machine
        if self._simulator:
            machine.attach(self._simulator)
        logger.info(f"Added process machine: {machine.name}")

    def remove_machine(self, name: str):
        """Remove a machine from the simulation."""
        if name in self.machines:
            del self.machines[name]
            logger.info(f"Removed process machine: {name}")

    def clear_machines(self):
        """Remove all machines."""
        self.machines.clear()

    def update(self):
        """Update all machines."""
        current_time = time.time()
        dt = current_time - self._last_update if self._last_update > 0 else 0.05
        self._last_update = current_time

        for machine in self.machines.values():
            if machine.enabled:
                try:
                    machine.update(dt)
                except Exception as e:
                    logger.error(f"Error updating {machine.name}: {e}")

    async def start(self):
        """Start the process simulation loop."""
        if self.running:
            return

        self.running = True
        self._last_update = time.time()
        logger.info("Process simulator started")

        while self.running:
            self.update()
            await asyncio.sleep(self.update_interval_ms / 1000)

    def stop(self):
        """Stop the process simulation."""
        self.running = False
        logger.info("Process simulator stopped")

    def get_status(self) -> Dict[str, Any]:
        """Get status of all machines."""
        return {
            "running": self.running,
            "machine_count": len(self.machines),
            "machines": {name: m.get_status() for name, m in self.machines.items()},
        }


# Singleton instance
_process_simulator: Optional[ProcessSimulator] = None


def get_process_simulator() -> ProcessSimulator:
    """Get the global process simulator instance."""
    global _process_simulator
    if _process_simulator is None:
        _process_simulator = ProcessSimulator()
    return _process_simulator


def reset_process_simulator() -> ProcessSimulator:
    """Reset the global process simulator."""
    global _process_simulator
    if _process_simulator:
        _process_simulator.stop()
        _process_simulator.clear_machines()
    _process_simulator = ProcessSimulator()
    return _process_simulator


# Pre-defined scenarios for quick setup


def create_conveyor_scenario() -> Dict[str, Any]:
    """Create a conveyor belt scenario with matching ladder program."""
    return {
        "name": "Conveyor Belt",
        "description": "Conveyor with entry/exit sensors. Start button runs motor, sensors detect objects.",
        "machines": [
            ConveyorMachine(
                name="Conveyor",
                motor_output="Motor",
                entry_sensor="Entry_Sensor",
                exit_sensor="Exit_Sensor",
                belt_speed=3.0,
                object_spawn_interval=2.5,
            ),
            StartStopMachine(
                name="Pushbuttons",
                start_button="Start",
                stop_button="Stop",
                auto_cycle=True,
                cycle_run_time=8.0,
                cycle_stop_time=3.0,
            ),
        ],
        "ladder_program": {
            "rungs": [
                {
                    "description": "Motor Latch On",
                    "elements": [
                        {"type": "contact", "name": "Start"},
                        {"type": "set_coil", "name": "Motor"},
                    ],
                },
                {
                    "description": "Motor Latch Off",
                    "elements": [
                        {"type": "contact", "name": "Stop"},
                        {"type": "reset_coil", "name": "Motor"},
                    ],
                },
                {
                    "description": "Entry Indicator",
                    "elements": [
                        {"type": "contact", "name": "Entry_Sensor"},
                        {"type": "output", "name": "Entry_Light"},
                    ],
                },
                {
                    "description": "Exit Indicator",
                    "elements": [
                        {"type": "contact", "name": "Exit_Sensor"},
                        {"type": "output", "name": "Exit_Light"},
                    ],
                },
            ]
        },
    }


def create_tank_scenario() -> Dict[str, Any]:
    """Create a tank fill/drain scenario with matching ladder program."""
    return {
        "name": "Tank Level Control",
        "description": "Automatic tank filling. Opens fill valve when low, closes when high.",
        "machines": [
            TankMachine(
                name="Tank",
                fill_valve="Fill_Valve",
                drain_valve="Drain_Valve",
                level_low="Level_Low",
                level_high="Level_High",
                fill_rate=15.0,
                drain_rate=5.0,  # Slower drain to show filling
            ),
        ],
        "ladder_program": {
            "rungs": [
                {
                    "description": "Fill when low (latch)",
                    "elements": [
                        {"type": "contact", "name": "Level_Low"},
                        {"type": "set_coil", "name": "Fill_Valve"},
                    ],
                },
                {
                    "description": "Stop fill when high (unlatch)",
                    "elements": [
                        {"type": "contact", "name": "Level_High"},
                        {"type": "reset_coil", "name": "Fill_Valve"},
                    ],
                },
                {
                    "description": "Drain always on (for demo)",
                    "elements": [
                        {"type": "contact", "name": "Drain_Enable"},
                        {"type": "output", "name": "Drain_Valve"},
                    ],
                },
            ]
        },
    }


def create_motor_control_scenario() -> Dict[str, Any]:
    """Create simple motor start/stop with auto-cycling buttons."""
    return {
        "name": "Motor Start/Stop",
        "description": "Simple motor control with automatic start/stop cycling.",
        "machines": [
            StartStopMachine(
                name="Pushbuttons",
                start_button="Start",
                stop_button="Stop",
                auto_cycle=True,
                cycle_run_time=5.0,
                cycle_stop_time=3.0,
            ),
        ],
        "ladder_program": {
            "rungs": [
                {
                    "description": "Motor seal-in circuit",
                    "elements": [
                        {"type": "contact", "name": "Start"},
                        {"type": "inverted_contact", "name": "Stop"},
                        {"type": "output", "name": "Motor"},
                    ],
                },
                {
                    "description": "Motor running indicator",
                    "elements": [
                        {"type": "contact", "name": "Motor"},
                        {"type": "output", "name": "Running_Light"},
                    ],
                },
            ]
        },
    }


# Available scenarios
PROCESS_SCENARIOS = {
    "conveyor": create_conveyor_scenario,
    "tank": create_tank_scenario,
    "motor_control": create_motor_control_scenario,
}


def get_scenario(name: str) -> Dict[str, Any]:
    """Get a pre-defined scenario by name."""
    if name not in PROCESS_SCENARIOS:
        raise ValueError(f"Unknown scenario: {name}. Available: {list(PROCESS_SCENARIOS.keys())}")
    return PROCESS_SCENARIOS[name]()
