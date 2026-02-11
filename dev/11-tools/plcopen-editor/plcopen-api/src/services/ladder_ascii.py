"""ASCII rendering for ladder logic diagrams - Allen-Bradley style."""
from typing import Any, Dict, List, Optional
from .ladder_rung import Rung
from .ladder_elements import (
    Contact,
    InvertedContact,
    Output,
    SetCoil,
    ResetCoil,
    Timer,
    Counter,
)


def render_rung_ab(
    rung: Rung,
    io_state: Dict[str, Any],
    rung_num: int,
    width: int = 80,
) -> str:
    """Render a single rung in Allen-Bradley style.

    Args:
        rung: The rung to render
        io_state: Current I/O state
        rung_num: Rung number for display
        width: Total width of the diagram

    Returns:
        Multi-line ASCII representation
    """
    lines = []

    # Get elements
    inputs = rung.get_inputs()
    output = rung.get_output()

    # Rung description
    desc = rung.description or f"Rung {rung_num}"
    lines.append(f"+{'-' * (width - 2)}+")
    lines.append(f"| RUNG {rung_num:03d}: {desc:<{width - 15}}|")
    lines.append(f"+{'-' * (width - 2)}+")
    lines.append("|")

    # Build each element as a block
    for elem in inputs:
        if isinstance(elem, (Contact, InvertedContact)):
            io_val = io_state.get(elem.name, False)
            state = elem.evaluate(io_state)
            is_nc = isinstance(elem, InvertedContact)

            name = elem.name
            contact_type = "NC" if is_nc else "NO"
            state_char = "#" if state else "."
            val_char = "*" if io_val else "o"

            lines.append(f"|     {name}")
            lines.append(f"|    +-----+")
            if is_nc:
                lines.append(f"|----+/ {state_char} +----")
            else:
                lines.append(f"|----+  {state_char}  +----")
            lines.append(f"|    +-----+")
            lines.append(f"|     {contact_type} [{val_char}]")
            lines.append("|")

        elif isinstance(elem, Timer):
            done = io_state.get(f"{elem.name}.DN", False)
            acc = io_state.get(f"{elem.name}.ACC", 0)
            state_char = "#" if done else "."

            lines.append(f"|  +-------------+")
            lines.append(f"|  | {elem.timer_type:<4} {elem.name:>6} |")
            lines.append(f"|  +-------------+")
            lines.append(f"|  | PRE: {elem.preset_ms:>5}ms|")
            lines.append(f"|  | ACC: {acc:>5}ms|")
            lines.append(f"|  | DN:  [{state_char}]     |")
            lines.append(f"|  +-------------+")
            lines.append("|")

        elif isinstance(elem, Counter):
            done = io_state.get(f"{elem.name}.DN", False)
            count = io_state.get(f"{elem.name}.CV", 0)
            state_char = "#" if done else "."

            lines.append(f"|  +-------------+")
            lines.append(f"|  | {elem.counter_type:<4} {elem.name:>6} |")
            lines.append(f"|  +-------------+")
            lines.append(f"|  | PRE: {elem.preset:>6}|")
            lines.append(f"|  | ACC: {count:>6}|")
            lines.append(f"|  | DN:  [{state_char}]     |")
            lines.append(f"|  +-------------+")
            lines.append("|")

    # Add output
    if output:
        out_state = io_state.get(output.name, False)
        state_char = "#" if out_state else "."
        val_char = "*" if out_state else "o"

        if isinstance(output, SetCoil):
            coil_sym = "L"
            coil_type = "LATCH"
        elif isinstance(output, ResetCoil):
            coil_sym = "U"
            coil_type = "UNLATCH"
        else:
            coil_sym = " "
            coil_type = "COIL"

        name = output.name

        lines.append(f"|     {name}")
        lines.append(f"|    +-----+")
        lines.append(f"|----({coil_sym} {state_char} {coil_sym})----+")
        lines.append(f"|    +-----+     |")
        lines.append(f"|     {coil_type} [{val_char}]   |")

    lines.append(f"+{'-' * (width - 2)}+")

    return "\n".join(lines)


def render_ladder_ab(
    rungs: List[Rung],
    io_state: Dict[str, Any],
    width: int = 80,
    title: Optional[str] = None,
) -> str:
    """Render a complete ladder diagram in Allen-Bradley style.

    Args:
        rungs: List of rungs to render
        io_state: Current I/O state
        width: Total width of the diagram
        title: Optional title for the diagram

    Returns:
        Multi-line ASCII representation
    """
    lines = []

    # Header
    lines.append("+" + "=" * (width - 2) + "+")
    lines.append("|" + "LADDER LOGIC DIAGRAM".center(width - 2) + "|")
    lines.append("+" + "=" * (width - 2) + "+")
    lines.append("|" + " " * (width - 2) + "|")
    lines.append("|  L1 (HOT)" + " " * (width - 22) + "L2 (NEU)  |")
    lines.append("|   |" + " " * (width - 12) + "|   |")
    lines.append("+" + "-" * (width - 2) + "+")

    # Render each rung
    for i, rung in enumerate(rungs):
        lines.append(render_rung_ab(rung, io_state, i + 1, width))

    # Footer
    lines.append("|   |" + " " * (width - 12) + "|   |")
    lines.append("+" + "=" * (width - 2) + "+")
    lines.append("")
    lines.append("LEGEND:  [#] = Energized/TRUE    [.] = De-energized/FALSE")
    lines.append("         [*] = Tag is TRUE       [o] = Tag is FALSE")
    lines.append("         NO  = Normally Open     NC  = Normally Closed")

    return "\n".join(lines)


def render_io_table_ab(io_state: Dict[str, Any], width: int = 80) -> str:
    """Render I/O state as Allen-Bradley style tag monitor.

    Args:
        io_state: Current I/O state
        width: Total width of the table

    Returns:
        ASCII table representation
    """
    lines = []

    lines.append("")
    lines.append("+" + "=" * (width - 2) + "+")
    lines.append("|" + "TAG MONITOR".center(width - 2) + "|")
    lines.append("+" + "-" * 20 + "+" + "-" * 12 + "+" + "-" * (width - 36) + "+")
    lines.append(f"| {'TAG NAME':<18} | {'VALUE':^10} | {'STATUS':<{width - 38}} |")
    lines.append("+" + "-" * 20 + "+" + "-" * 12 + "+" + "-" * (width - 36) + "+")

    for name in sorted(io_state.keys()):
        value = io_state[name]
        if isinstance(value, bool):
            val_display = "TRUE" if value else "FALSE"
            status = "[#] ENERGIZED" if value else "[.] DE-ENERGIZED"
        else:
            val_display = str(value)
            status = "-"

        name_col = name[:18]
        lines.append(f"| {name_col:<18} | {val_display:^10} | {status:<{width - 38}} |")

    lines.append("+" + "-" * 20 + "+" + "-" * 12 + "+" + "-" * (width - 36) + "+")

    return "\n".join(lines)


def render_full_diagram(
    rungs: List[Rung],
    io_state: Dict[str, Any],
    title: Optional[str] = None,
    include_io_table: bool = True,
    include_legend: bool = False,
    width: int = 80,
) -> str:
    """Render a complete diagram with optional I/O table and legend.

    Args:
        rungs: List of rungs to render
        io_state: Current I/O state
        title: Optional title
        include_io_table: Whether to include the I/O state table
        include_legend: Whether to include the symbol legend
        width: Total width

    Returns:
        Complete ASCII diagram
    """
    parts = []

    # Main ladder
    parts.append(render_ladder_ab(rungs, io_state, width, title))

    # I/O table
    if include_io_table:
        parts.append(render_io_table_ab(io_state, width))

    return "\n".join(parts)


# Keep old function names for backward compatibility
def render_rung(rung: Rung, io_state: Dict[str, Any], rung_num: int, width: int = 80) -> str:
    return render_rung_ab(rung, io_state, rung_num, width)

def render_ladder(rungs: List[Rung], io_state: Dict[str, Any], width: int = 80, title: Optional[str] = None) -> str:
    return render_ladder_ab(rungs, io_state, width, title)

def render_io_table(io_state: Dict[str, Any], width: int = 80) -> str:
    return render_io_table_ab(io_state, width)

def render_legend(width: int = 80) -> str:
    return ""
