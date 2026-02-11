"""Ladder logic element classes for the simulator."""
from typing import Any, Dict
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time


class LadderElement(ABC):
    """Base class for all ladder elements."""

    @abstractmethod
    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        """Evaluate the element and return its logical state."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the element name."""
        pass


@dataclass
class Contact(LadderElement):
    """Normally Open (NO) contact.

    Returns True when the associated input is True.
    Symbol: ──┤ X ├──
    """
    _name: str

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        return bool(io_state.get(self._name, False))

    def __repr__(self) -> str:
        return f"Contact({self._name})"


@dataclass
class InvertedContact(LadderElement):
    """Normally Closed (NC) contact.

    Returns True when the associated input is False.
    Symbol: ──┤/X ├──
    """
    _name: str

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        return not bool(io_state.get(self._name, False))

    def __repr__(self) -> str:
        return f"InvertedContact({self._name})"


@dataclass
class Output(LadderElement):
    """Output coil.

    Writes the rung result to the associated output.
    Symbol: ──( Y )──
    """
    _name: str
    negated: bool = False

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        # Outputs don't evaluate inputs, they receive values
        return bool(io_state.get(self._name, False))

    def write(self, io_state: Dict[str, Any], value: bool):
        """Write value to this output."""
        final_value = not value if self.negated else value
        io_state[self._name] = final_value

    def __repr__(self) -> str:
        neg = "/" if self.negated else ""
        return f"Output({neg}{self._name})"


@dataclass
class SetCoil(LadderElement):
    """Set (Latch) coil.

    Sets the output to True when energized, stays True until reset.
    Symbol: ──(S Y)──
    """
    _name: str

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        return bool(io_state.get(self._name, False))

    def write(self, io_state: Dict[str, Any], value: bool):
        """Set the output if energized (only sets, never resets)."""
        if value:
            io_state[self._name] = True

    def __repr__(self) -> str:
        return f"SetCoil({self._name})"


@dataclass
class ResetCoil(LadderElement):
    """Reset (Unlatch) coil.

    Resets the output to False when energized.
    Symbol: ──(R Y)──
    """
    _name: str

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        return bool(io_state.get(self._name, False))

    def write(self, io_state: Dict[str, Any], value: bool):
        """Reset the output if energized (only resets, never sets)."""
        if value:
            io_state[self._name] = False

    def __repr__(self) -> str:
        return f"ResetCoil({self._name})"


@dataclass
class Timer(LadderElement):
    """Timer element with ON-delay, OFF-delay, and Pulse variants.

    Timer Types:
    - TON (On-Delay): Output turns ON after input has been ON for preset time
    - TOFF (Off-Delay): Output turns OFF after input has been OFF for preset time
    - PULSE: Output turns ON for preset time when input transitions to ON
    """
    _name: str
    preset_ms: int = 1000
    timer_type: str = "TON"  # TON, TOFF, PULSE
    accumulated_ms: float = field(default=0.0, repr=False)
    done: bool = field(default=False, repr=False)
    _last_input: bool = field(default=False, repr=False)
    _last_time: float = field(default_factory=time.time, repr=False)

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        """Evaluate timer and return done status."""
        return self.done

    def update(self, input_state: bool, io_state: Dict[str, Any]):
        """Update timer based on input state."""
        current_time = time.time()
        elapsed_ms = (current_time - self._last_time) * 1000
        self._last_time = current_time

        if self.timer_type == "TON":
            self._update_ton(input_state, elapsed_ms)
        elif self.timer_type == "TOFF":
            self._update_toff(input_state, elapsed_ms)
        elif self.timer_type == "PULSE":
            self._update_pulse(input_state, elapsed_ms)

        # Store timer state in io_state
        io_state[f"{self._name}.DN"] = self.done
        io_state[f"{self._name}.ACC"] = int(self.accumulated_ms)
        io_state[f"{self._name}.PRE"] = self.preset_ms

        self._last_input = input_state

    def _update_ton(self, input_state: bool, elapsed_ms: float):
        """ON-delay timer logic."""
        if input_state:
            self.accumulated_ms += elapsed_ms
            if self.accumulated_ms >= self.preset_ms:
                self.accumulated_ms = self.preset_ms
                self.done = True
        else:
            self.accumulated_ms = 0
            self.done = False

    def _update_toff(self, input_state: bool, elapsed_ms: float):
        """OFF-delay timer logic."""
        if input_state:
            self.accumulated_ms = 0
            self.done = True
        else:
            if self.done:  # Was previously on
                self.accumulated_ms += elapsed_ms
                if self.accumulated_ms >= self.preset_ms:
                    self.accumulated_ms = self.preset_ms
                    self.done = False

    def _update_pulse(self, input_state: bool, elapsed_ms: float):
        """Pulse timer logic."""
        # Detect rising edge
        if input_state and not self._last_input:
            self.accumulated_ms = 0
            self.done = True

        if self.done:
            self.accumulated_ms += elapsed_ms
            if self.accumulated_ms >= self.preset_ms:
                self.accumulated_ms = self.preset_ms
                self.done = False

    def reset(self):
        """Reset timer to initial state."""
        self.accumulated_ms = 0
        self.done = False
        self._last_input = False
        self._last_time = time.time()

    def __repr__(self) -> str:
        return f"Timer({self._name}, {self.timer_type}, {self.preset_ms}ms)"


@dataclass
class AnalogOutput(LadderElement):
    """Analog output for numeric values.

    Simulates analog signals by incrementing/decrementing within a range.
    Symbol: ──(AO Y)──
    """
    _name: str
    min_value: float = 0.0
    max_value: float = 100.0
    step: float = 1.0
    current_value: float = field(default=0.0, repr=False)
    _direction: int = field(default=1, repr=False)  # 1=up, -1=down
    _initialized: bool = field(default=False, repr=False)

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        """Always passes through - analog outputs don't gate logic."""
        return True

    def write(self, io_state: Dict[str, Any], enabled: bool):
        """Update analog value when enabled (rung is true)."""
        # Initialize to min_value on first write
        if not self._initialized:
            self.current_value = self.min_value
            self._initialized = True

        if enabled:
            # Oscillate value within range
            self.current_value += self.step * self._direction
            if self.current_value >= self.max_value:
                self.current_value = self.max_value
                self._direction = -1
            elif self.current_value <= self.min_value:
                self.current_value = self.min_value
                self._direction = 1

        io_state[self._name] = round(self.current_value, 2)

    def reset(self):
        """Reset analog output to initial state."""
        self.current_value = self.min_value
        self._direction = 1
        self._initialized = False

    def __repr__(self) -> str:
        return f"AnalogOutput({self._name}, {self.min_value}-{self.max_value}, step={self.step})"


@dataclass
class Counter(LadderElement):
    """Counter element with Up and Down variants.

    Counter Types:
    - CTU (Count Up): Increments on rising edge, done when count >= preset
    - CTD (Count Down): Decrements on rising edge, done when count <= 0
    - CTUD (Up/Down): Has separate up and down inputs
    """
    _name: str
    preset: int = 10
    counter_type: str = "CTU"  # CTU, CTD, CTUD
    count: int = field(default=0, repr=False)
    done: bool = field(default=False, repr=False)
    _last_input: bool = field(default=False, repr=False)

    @property
    def name(self) -> str:
        return self._name

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        """Evaluate counter and return done status."""
        return self.done

    def update(self, input_state: bool, io_state: Dict[str, Any], down_input: bool = False):
        """Update counter based on input state."""
        if self.counter_type == "CTU":
            # Count up on rising edge
            if input_state and not self._last_input:
                self.count += 1
            self.done = self.count >= self.preset

        elif self.counter_type == "CTD":
            # Count down on rising edge
            if input_state and not self._last_input:
                self.count -= 1
            self.done = self.count <= 0

        elif self.counter_type == "CTUD":
            # Up/down counter
            if input_state and not self._last_input:
                self.count += 1
            # down_input would need separate tracking
            self.done = self.count >= self.preset

        # Store counter state in io_state
        io_state[f"{self._name}.DN"] = self.done
        io_state[f"{self._name}.CV"] = self.count
        io_state[f"{self._name}.PV"] = self.preset

        self._last_input = input_state

    def reset(self):
        """Reset counter to initial state."""
        self.count = 0
        self.done = False
        self._last_input = False

    def __repr__(self) -> str:
        return f"Counter({self._name}, {self.counter_type}, preset={self.preset})"
