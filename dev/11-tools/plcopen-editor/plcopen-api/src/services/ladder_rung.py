"""Ladder rung evaluation logic."""
from typing import Any, Dict, List, Union
from dataclasses import dataclass, field

from .ladder_elements import (
    LadderElement,
    Contact,
    InvertedContact,
    Output,
    SetCoil,
    ResetCoil,
    Timer,
    Counter,
    AnalogOutput,
)


@dataclass
class SeriesBlock:
    """Series (AND) logic block - all elements must be True."""
    elements: List[LadderElement] = field(default_factory=list)

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        """Evaluate series logic (AND)."""
        if not self.elements:
            return True
        result = True
        for elem in self.elements:
            result = result and elem.evaluate(io_state)
        return result


@dataclass
class ParallelBlock:
    """Parallel (OR) logic block - any element can be True."""
    branches: List[Union[LadderElement, "SeriesBlock", "ParallelBlock"]] = field(
        default_factory=list
    )

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        """Evaluate parallel logic (OR)."""
        if not self.branches:
            return False
        for branch in self.branches:
            if isinstance(branch, (SeriesBlock, ParallelBlock)):
                if branch.evaluate(io_state):
                    return True
            elif isinstance(branch, LadderElement):
                if branch.evaluate(io_state):
                    return True
        return False


@dataclass
class Rung:
    """A single ladder rung with input logic and output.

    A rung consists of:
    - Input logic: contacts, timers, counters (can be series/parallel)
    - Output: coil, set/reset coil

    The rung evaluates the input logic and writes the result to the output.
    """
    elements: List[LadderElement] = field(default_factory=list)
    description: str = ""
    _logic_tree: Union[SeriesBlock, ParallelBlock, None] = field(
        default=None, repr=False
    )

    def __post_init__(self):
        """Build the logic tree from elements."""
        if self.elements:
            self._build_simple_series()

    def _build_simple_series(self):
        """Build a simple series logic from flat element list.

        Assumes all elements except the last are inputs in series,
        and the last element is the output.
        """
        if len(self.elements) < 2:
            return

        # All but last are input logic
        inputs = self.elements[:-1]
        self._logic_tree = SeriesBlock(elements=inputs)

    def get_inputs(self) -> List[LadderElement]:
        """Get all input elements (everything except output)."""
        if len(self.elements) < 2:
            return []
        return self.elements[:-1]

    def get_output(self) -> Union[Output, SetCoil, ResetCoil, AnalogOutput, Timer, Counter, None]:
        """Get the output element."""
        if not self.elements:
            return None
        last = self.elements[-1]
        if isinstance(last, (Output, SetCoil, ResetCoil, AnalogOutput, Timer, Counter)):
            return last
        return None

    def evaluate(self, io_state: Dict[str, Any]) -> bool:
        """Evaluate the rung and write to output.

        Returns:
            The result of the input logic evaluation.
        """
        if not self.elements:
            return False

        # Evaluate input logic (all elements except the last/output element)
        result = True
        for elem in self.elements[:-1]:
            # Evaluate this element and AND with current result
            result = result and elem.evaluate(io_state)

        # Handle the output element (last element in rung)
        output = self.get_output()
        if output:
            if isinstance(output, (Output, SetCoil, ResetCoil, AnalogOutput)):
                output.write(io_state, result)
            elif isinstance(output, Timer):
                # Timer: update with rung result as enable signal
                output.update(result, io_state)
            elif isinstance(output, Counter):
                # Counter: update with rung result as count-up signal
                output.update(result, io_state)

        return result

    def get_all_names(self) -> List[str]:
        """Get all variable names used in this rung."""
        names = []
        for elem in self.elements:
            if hasattr(elem, "name"):
                names.append(elem.name)
        return names

    def __repr__(self) -> str:
        desc = f'"{self.description}"' if self.description else ""
        elems = " -> ".join(str(e) for e in self.elements)
        return f"Rung({desc}: {elems})"


def create_rung(
    inputs: List[LadderElement],
    output: Union[Output, SetCoil, ResetCoil],
    description: str = "",
) -> Rung:
    """Helper function to create a rung from inputs and output.

    Args:
        inputs: List of input elements (contacts, timers, etc.)
        output: The output element (coil)
        description: Optional description

    Returns:
        A configured Rung object
    """
    elements = list(inputs) + [output]
    return Rung(elements=elements, description=description)


def create_series_rung(
    *contacts: str,
    output_name: str,
    description: str = "",
) -> Rung:
    """Create a simple series (AND) rung from contact names.

    Contact names starting with '/' are inverted contacts.

    Example:
        create_series_rung("Start", "/Stop", output_name="Motor")
        # Creates: Start AND (NOT Stop) -> Motor

    Args:
        *contacts: Variable contact names (prefix '/' for NC)
        output_name: Name of the output
        description: Optional description

    Returns:
        A configured Rung object
    """
    elements = []
    for name in contacts:
        if name.startswith("/"):
            elements.append(InvertedContact(_name=name[1:]))
        else:
            elements.append(Contact(_name=name))

    elements.append(Output(_name=output_name))
    return Rung(elements=elements, description=description)
