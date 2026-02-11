"""SVG rendering for ladder logic diagrams - Allen-Bradley style."""
from typing import Any, Dict, List, Optional, Tuple
from .ladder_rung import Rung
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


# Colors - Allen-Bradley style
COLORS = {
    "energized": "#00FF00",
    "de_energized": "#666666",
    "background": "#1a1a2e",
    "rail": "#FFFFFF",
    "text": "#FFFFFF",
    "text_dark": "#000000",
    "box_stroke": "#4a4a6a",
    "box_fill": "#2a2a4a",
    "element_bg": "#252540",
}

# Layout constants - compact/scaled down
RAIL_WIDTH = 25
ELEMENT_WIDTH = 50
ELEMENT_HEIGHT = 38
ELEMENT_SPACING = 35  # More space between elements
RUNG_PADDING = 12     # More vertical padding in rungs
HEADER_HEIGHT = 28
RUNG_HEADER_HEIGHT = 18  # Taller rung headers


def svg_header(width: int, height: int) -> str:
    """Generate SVG header."""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100%" viewBox="0 0 {width} {height}" preserveAspectRatio="xMinYMin meet">
  <defs>
    <style>
      .title {{ font: bold 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: {COLORS["text"]}; }}
      .rung-label {{ font: bold 8px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: {COLORS["text"]}; }}
      .tag-name {{ font: bold 7px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: {COLORS["text"]}; text-anchor: middle; }}
      .tag-type {{ font: 7px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: {COLORS["text"]}; text-anchor: middle; }}
      .tag-value {{ font: bold 7px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; text-anchor: middle; }}
      .legend {{ font: 7px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: {COLORS["text"]}; }}
      .table-header {{ font: bold 7px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: {COLORS["text"]}; }}
      .table-cell {{ font: 7px -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; fill: {COLORS["text"]}; }}
    </style>
  </defs>
  <rect width="100%" height="100%" fill="{COLORS["background"]}"/>
'''


def svg_footer() -> str:
    return '</svg>'


def svg_contact(x: int, y: int, name: str, is_nc: bool, state: bool, io_value: bool, wire_y: int) -> Tuple[str, int]:
    """Render a contact element. Returns (svg_string, width)."""
    color = COLORS["energized"] if state else COLORS["de_energized"]
    value_color = COLORS["energized"] if io_value else COLORS["de_energized"]
    contact_type = "NC" if is_nc else "NO"
    value_text = "TRUE" if io_value else "FALSE"

    w = ELEMENT_WIDTH

    # Center points
    cx = x + w // 2

    # Calculate box to fully contain all content
    box_bottom = wire_y + 20
    h = box_bottom - y

    # Calculate text width limit for scaling
    max_text_width = w - 4

    svg = f'''
  <g>
    <!-- Element box -->
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2"
          fill="{COLORS["element_bg"]}" stroke="{COLORS["box_stroke"]}" stroke-width="1"/>

    <!-- Tag name at top (scaled to fit) -->
    <text x="{cx}" y="{y + 8}" class="tag-name" textLength="{max_text_width}" lengthAdjust="spacingAndGlyphs">{name}</text>

    <!-- Continuous wire through element -->
    <line x1="{x}" y1="{wire_y}" x2="{x + w}" y2="{wire_y}" stroke="{color}" stroke-width="1"/>

    <!-- Left bracket -->
    <line x1="{x + 8}" y1="{wire_y - 5}" x2="{x + 8}" y2="{wire_y + 5}" stroke="{color}" stroke-width="1"/>

    <!-- Right bracket -->
    <line x1="{x + w - 8}" y1="{wire_y - 5}" x2="{x + w - 8}" y2="{wire_y + 5}" stroke="{color}" stroke-width="1"/>

    <!-- NC diagonal slash -->
    {f'<line x1="{x + 10}" y1="{wire_y + 4}" x2="{x + w - 10}" y2="{wire_y - 4}" stroke="{color}" stroke-width="1"/>' if is_nc else ""}

    <!-- Type label -->
    <text x="{cx}" y="{wire_y + 12}" class="tag-type">{contact_type}</text>

    <!-- Value -->
    <text x="{cx}" y="{wire_y + 18}" class="tag-value" fill="{value_color}">{value_text}</text>
  </g>
'''
    return svg, w


def svg_coil(x: int, y: int, name: str, coil_type: str, state: bool, wire_y: int) -> Tuple[str, int]:
    """Render an output coil. Returns (svg_string, width)."""
    color = COLORS["energized"] if state else COLORS["de_energized"]
    value_text = "TRUE" if state else "FALSE"

    w = ELEMENT_WIDTH
    cx = x + w // 2

    # Calculate box to fully contain all content
    box_bottom = wire_y + 20
    h = box_bottom - y

    # Symbol letter for latch/unlatch
    symbol = ""
    if coil_type == "LATCH":
        symbol = "L"
    elif coil_type == "UNLATCH":
        symbol = "U"

    # Calculate text width limit for scaling
    max_text_width = w - 4

    svg = f'''
  <g>
    <!-- Element box -->
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2"
          fill="{COLORS["element_bg"]}" stroke="{COLORS["box_stroke"]}" stroke-width="1"/>

    <!-- Tag name at top (scaled to fit) -->
    <text x="{cx}" y="{y + 8}" class="tag-name" textLength="{max_text_width}" lengthAdjust="spacingAndGlyphs">{name}</text>

    <!-- Left wire to coil -->
    <line x1="{x}" y1="{wire_y}" x2="{cx - 8}" y2="{wire_y}" stroke="{color}" stroke-width="1"/>

    <!-- Coil circle -->
    <ellipse cx="{cx}" cy="{wire_y}" rx="8" ry="5"
             fill="none" stroke="{color}" stroke-width="1"/>

    <!-- Symbol inside coil (only for latch/unlatch) -->
    {f'<text x="{cx}" y="{wire_y + 2}" class="tag-value" fill="{color}" style="font-size:5px">{symbol}</text>' if symbol else ""}

    <!-- Right wire from coil -->
    <line x1="{cx + 8}" y1="{wire_y}" x2="{x + w}" y2="{wire_y}" stroke="{color}" stroke-width="1"/>

    <!-- Type label -->
    <text x="{cx}" y="{wire_y + 12}" class="tag-type">{coil_type}</text>

    <!-- Value -->
    <text x="{cx}" y="{wire_y + 18}" class="tag-value" fill="{color}">{value_text}</text>
  </g>
'''
    return svg, w


def svg_timer(x: int, y: int, elem: Timer, io_state: Dict[str, Any]) -> Tuple[str, int]:
    """Render a timer block. Returns (svg_string, width)."""
    done = io_state.get(f"{elem.name}.DN", False)
    timing = io_state.get(f"{elem.name}.TT", False)
    acc = io_state.get(f"{elem.name}.ACC", 0)

    color = COLORS["energized"] if done else COLORS["de_energized"]

    w = ELEMENT_WIDTH
    h = ELEMENT_HEIGHT

    # Calculate text width limit for scaling
    max_text_width = w - 4

    svg = f'''
  <g>
    <!-- Timer box -->
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="1"
          fill="{COLORS["element_bg"]}" stroke="{color}" stroke-width="1"/>

    <!-- Header bar -->
    <rect x="{x}" y="{y}" width="{w}" height="10" rx="1"
          fill="{color}"/>
    <text x="{x + w // 2}" y="{y + 7}" class="tag-name" fill="{COLORS["text_dark"]}" style="font-size:5px" textLength="{max_text_width}" lengthAdjust="spacingAndGlyphs">{elem.timer_type}-{elem.name}</text>

    <!-- Values -->
    <text x="{x + 2}" y="{y + 18}" class="table-cell" style="text-anchor: start; font-size:6px">PRE:{elem.preset_ms}</text>
    <text x="{x + 2}" y="{y + 26}" class="table-cell" style="text-anchor: start; font-size:6px">ACC:{acc}</text>

    <!-- Status indicators -->
    <text x="{x + 2}" y="{y + 34}" class="table-cell" style="text-anchor: start; font-size:6px">DN:</text>
    <rect x="{x + 14}" y="{y + 28}" width="6" height="6" fill="{COLORS["energized"] if done else COLORS["de_energized"]}" rx="1"/>

    <text x="{x + 26}" y="{y + 34}" class="table-cell" style="text-anchor: start; font-size:6px">TT:</text>
    <rect x="{x + 36}" y="{y + 28}" width="6" height="6" fill="{COLORS["energized"] if timing else COLORS["de_energized"]}" rx="1"/>

    <!-- Wire connections -->
    <line x1="{x - ELEMENT_SPACING}" y1="{y + h // 2}" x2="{x}" y2="{y + h // 2}" stroke="{COLORS["rail"]}" stroke-width="1"/>
    <line x1="{x + w}" y1="{y + h // 2}" x2="{x + w + ELEMENT_SPACING}" y2="{y + h // 2}" stroke="{COLORS["rail"]}" stroke-width="1"/>
  </g>
'''
    return svg, w


def svg_counter(x: int, y: int, elem: Counter, io_state: Dict[str, Any]) -> Tuple[str, int]:
    """Render a counter block. Returns (svg_string, width)."""
    done = io_state.get(f"{elem.name}.DN", False)
    count = io_state.get(f"{elem.name}.CV", 0)

    color = COLORS["energized"] if done else COLORS["de_energized"]

    w = ELEMENT_WIDTH
    h = ELEMENT_HEIGHT

    # Calculate text width limit for scaling
    max_text_width = w - 4

    svg = f'''
  <g>
    <!-- Counter box -->
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="1"
          fill="{COLORS["element_bg"]}" stroke="{color}" stroke-width="1"/>

    <!-- Header bar -->
    <rect x="{x}" y="{y}" width="{w}" height="10" rx="1"
          fill="{color}"/>
    <text x="{x + w // 2}" y="{y + 7}" class="tag-name" fill="{COLORS["text_dark"]}" style="font-size:5px" textLength="{max_text_width}" lengthAdjust="spacingAndGlyphs">{elem.counter_type}-{elem.name}</text>

    <!-- Values -->
    <text x="{x + 2}" y="{y + 18}" class="table-cell" style="text-anchor: start; font-size:6px">PRE:{elem.preset}</text>
    <text x="{x + 2}" y="{y + 26}" class="table-cell" style="text-anchor: start; font-size:6px">CV:{count}</text>

    <!-- Status indicator -->
    <text x="{x + 2}" y="{y + 34}" class="table-cell" style="text-anchor: start; font-size:6px">DN:</text>
    <rect x="{x + 14}" y="{y + 28}" width="6" height="6" fill="{COLORS["energized"] if done else COLORS["de_energized"]}" rx="1"/>

    <!-- Wire connections -->
    <line x1="{x - ELEMENT_SPACING}" y1="{y + h // 2}" x2="{x}" y2="{y + h // 2}" stroke="{COLORS["rail"]}" stroke-width="1"/>
    <line x1="{x + w}" y1="{y + h // 2}" x2="{x + w + ELEMENT_SPACING}" y2="{y + h // 2}" stroke="{COLORS["rail"]}" stroke-width="1"/>
  </g>
'''
    return svg, w


def svg_rung(rung: Rung, io_state: Dict[str, Any], rung_num: int, y_offset: int, width: int) -> Tuple[str, int]:
    """Render a single rung. Returns (svg_string, height)."""
    svg_parts = []

    inputs = rung.get_inputs()
    output = rung.get_output()

    # Rung header
    desc = rung.description or f"Rung {rung_num}"
    svg_parts.append(f'''
  <!-- Rung {rung_num} header -->
  <rect x="0" y="{y_offset}" width="{width}" height="{RUNG_HEADER_HEIGHT}" fill="{COLORS["box_fill"]}"/>
  <text x="{RAIL_WIDTH + 5}" y="{y_offset + 13}" class="rung-label">RUNG {rung_num:03d}: {desc}</text>
  <line x1="0" y1="{y_offset + RUNG_HEADER_HEIGHT}" x2="{width}" y2="{y_offset + RUNG_HEADER_HEIGHT}"
        stroke="{COLORS["box_stroke"]}" stroke-width="1"/>
''')

    # Calculate element positions
    element_y = y_offset + RUNG_HEADER_HEIGHT + RUNG_PADDING
    wire_y = element_y + ELEMENT_HEIGHT // 2 + 10  # Center of contact symbol area

    # Starting x position after left rail
    x = RAIL_WIDTH + ELEMENT_SPACING

    # Left rail to first element wire
    svg_parts.append(f'''
  <line x1="{RAIL_WIDTH}" y1="{wire_y}" x2="{x}" y2="{wire_y}" stroke="{COLORS["rail"]}" stroke-width="1"/>
''')

    # Track the last element's state for wire coloring
    last_state = True  # Start assuming power from rail

    # Render input elements
    for elem in inputs:
        if isinstance(elem, (Contact, InvertedContact)):
            io_val = io_state.get(elem.name, False)
            state = elem.evaluate(io_state)
            is_nc = isinstance(elem, InvertedContact)

            elem_svg, elem_w = svg_contact(x, element_y, elem.name, is_nc, state, io_val, wire_y)
            svg_parts.append(elem_svg)
            x += elem_w

            # Wire to next element (color based on output state of this contact)
            wire_color = COLORS["energized"] if state else COLORS["de_energized"]
            svg_parts.append(f'''
  <line x1="{x}" y1="{wire_y}" x2="{x + ELEMENT_SPACING}" y2="{wire_y}" stroke="{wire_color}" stroke-width="1"/>
''')
            x += ELEMENT_SPACING
            last_state = state

        elif isinstance(elem, Timer):
            elem_svg, elem_w = svg_timer(x, element_y, elem, io_state)
            svg_parts.append(elem_svg)
            x += elem_w + ELEMENT_SPACING

        elif isinstance(elem, Counter):
            elem_svg, elem_w = svg_counter(x, element_y, elem, io_state)
            svg_parts.append(elem_svg)
            x += elem_w + ELEMENT_SPACING

    # Render output
    if output:
        if isinstance(output, Timer):
            # Timer as output
            elem_svg, elem_w = svg_timer(x, element_y, output, io_state)
            svg_parts.append(elem_svg)
            x += elem_w
            done = io_state.get(f"{output.name}.DN", False)
            wire_color = COLORS["energized"] if done else COLORS["de_energized"]
        elif isinstance(output, Counter):
            # Counter as output
            elem_svg, elem_w = svg_counter(x, element_y, output, io_state)
            svg_parts.append(elem_svg)
            x += elem_w
            done = io_state.get(f"{output.name}.DN", False)
            wire_color = COLORS["energized"] if done else COLORS["de_energized"]
        elif isinstance(output, AnalogOutput):
            # AnalogOutput - render as a coil with analog indicator
            out_state = io_state.get(output.name, 0)
            elem_svg, elem_w = svg_coil(x, element_y, output.name, "COIL", True, wire_y)
            svg_parts.append(elem_svg)
            x += elem_w
            wire_color = COLORS["energized"]
        else:
            # Regular coil (Output, SetCoil, ResetCoil)
            out_state = io_state.get(output.name, False)
            if isinstance(output, SetCoil):
                coil_type = "LATCH"
            elif isinstance(output, ResetCoil):
                coil_type = "UNLATCH"
            else:
                coil_type = "COIL"
            elem_svg, elem_w = svg_coil(x, element_y, output.name, coil_type, out_state, wire_y)
            svg_parts.append(elem_svg)
            x += elem_w
            wire_color = COLORS["energized"] if out_state else COLORS["de_energized"]

        # Wire to right rail
        svg_parts.append(f'''
  <line x1="{x}" y1="{wire_y}" x2="{width - RAIL_WIDTH}" y2="{wire_y}" stroke="{wire_color}" stroke-width="1"/>
''')

    rung_height = RUNG_HEADER_HEIGHT + RUNG_PADDING + ELEMENT_HEIGHT + RUNG_PADDING
    return "\n".join(svg_parts), rung_height


def svg_tag_monitor_side(io_state: Dict[str, Any], x_offset: int, y_offset: int, table_width: int, min_height: int) -> Tuple[str, int]:
    """Render tag monitor table on the side. Returns (svg_string, height)."""
    svg_parts = []

    row_height = 24
    header_height = 35

    num_tags = len(io_state)
    table_height = max(min_height, header_height + (num_tags * row_height) + 15)

    # Table background
    svg_parts.append(f'''
  <!-- Tag Monitor (Side Panel) -->
  <rect x="{x_offset}" y="{y_offset}" width="{table_width}" height="{table_height}"
        fill="{COLORS["box_fill"]}" stroke="{COLORS["box_stroke"]}" stroke-width="2" rx="5"/>

  <!-- Title bar -->
  <rect x="{x_offset}" y="{y_offset}" width="{table_width}" height="{header_height}"
        fill="{COLORS["box_stroke"]}" rx="5"/>
  <rect x="{x_offset}" y="{y_offset + header_height - 5}" width="{table_width}" height="5"
        fill="{COLORS["box_stroke"]}"/>
  <text x="{x_offset + table_width // 2}" y="{y_offset + 23}" class="title" style="text-anchor: middle;">TAG MONITOR</text>
''')

    # Column positions - compact for side panel
    col1_x = x_offset + 10
    col2_x = x_offset + table_width - 70
    col3_x = x_offset + table_width - 20

    # Tag rows
    row_y = y_offset + header_height + 20
    for name in sorted(io_state.keys()):
        value = io_state[name]
        if isinstance(value, bool):
            val_text = "TRUE" if value else "FALSE"
            status_color = COLORS["energized"] if value else COLORS["de_energized"]
        else:
            val_text = str(value)
            status_color = COLORS["de_energized"]

        # Truncate long names
        display_name = name[:14] + ".." if len(name) > 16 else name

        svg_parts.append(f'''
  <text x="{col1_x}" y="{row_y}" class="table-cell" style="text-anchor: start; font-size: 10px;">{display_name}</text>
  <text x="{col2_x}" y="{row_y}" class="tag-value" style="font-size: 10px;" fill="{status_color}">{val_text}</text>
  <rect x="{col3_x - 12}" y="{row_y - 10}" width="12" height="12" fill="{status_color}" rx="2"/>
''')
        row_y += row_height

    return "\n".join(svg_parts), table_height


def svg_tag_monitor_bottom(io_state: Dict[str, Any], x_offset: int, y_offset: int, width: int) -> Tuple[str, int]:
    """Render tag monitor table at the bottom in a horizontal layout. Returns (svg_string, height)."""
    svg_parts = []

    num_tags = len(io_state)
    if num_tags == 0:
        return "", 0

    # Horizontal layout: multiple columns of tags
    cols = min(4, max(1, num_tags))  # 1-4 columns
    rows = (num_tags + cols - 1) // cols

    col_width = (width - 40) // cols
    row_height = 28
    header_height = 40
    padding = 15

    table_height = header_height + (rows * row_height) + padding

    # Table background
    svg_parts.append(f'''
  <!-- Tag Monitor (Bottom Panel) -->
  <rect x="{x_offset}" y="{y_offset}" width="{width}" height="{table_height}"
        fill="{COLORS["box_fill"]}" stroke="{COLORS["box_stroke"]}" stroke-width="2" rx="5"/>

  <!-- Title bar -->
  <rect x="{x_offset}" y="{y_offset}" width="{width}" height="{header_height}"
        fill="{COLORS["box_stroke"]}" rx="5"/>
  <rect x="{x_offset}" y="{y_offset + header_height - 5}" width="{width}" height="5"
        fill="{COLORS["box_stroke"]}"/>
  <text x="{x_offset + width // 2}" y="{y_offset + 26}" class="title" style="text-anchor: middle;">TAG MONITOR</text>
''')

    # Render tags in columns
    sorted_tags = sorted(io_state.keys())
    for idx, name in enumerate(sorted_tags):
        col = idx % cols
        row = idx // cols

        tag_x = x_offset + 20 + (col * col_width)
        tag_y = y_offset + header_height + 20 + (row * row_height)

        value = io_state[name]
        if isinstance(value, bool):
            val_text = "TRUE" if value else "FALSE"
            status_color = COLORS["energized"] if value else COLORS["de_energized"]
        else:
            val_text = str(value)
            status_color = COLORS["de_energized"]

        # Truncate long names
        display_name = name[:18] + ".." if len(name) > 20 else name

        svg_parts.append(f'''
  <text x="{tag_x}" y="{tag_y}" class="table-cell" style="text-anchor: start; font-size: 10px;">{display_name}</text>
  <text x="{tag_x + col_width - 80}" y="{tag_y}" class="tag-value" style="font-size: 10px;" fill="{status_color}">{val_text}</text>
  <rect x="{tag_x + col_width - 30}" y="{tag_y - 10}" width="12" height="12" fill="{status_color}" rx="2"/>
''')

    return "\n".join(svg_parts), table_height


def render_ladder_svg(
    rungs: List[Rung],
    io_state: Dict[str, Any],
    title: Optional[str] = None,
    include_io_table: bool = True
) -> str:
    """Render complete ladder diagram as SVG with tag monitor below."""

    # Full width for ladder - no side panel
    total_width = 1000
    ladder_width = total_width

    # Calculate total height based on rungs
    rungs_height = len(rungs) * (RUNG_HEADER_HEIGHT + RUNG_PADDING + ELEMENT_HEIGHT + RUNG_PADDING)
    legend_height = 50
    content_height = rungs_height + 60  # rungs + power rail labels area + buffer

    # Calculate tag monitor height if needed
    num_tags = len(io_state)
    cols = min(4, max(1, num_tags))
    rows = (num_tags + cols - 1) // cols if num_tags > 0 else 0
    tag_monitor_height = (40 + (rows * 28) + 15 + 20) if include_io_table and num_tags > 0 else 0

    total_height = HEADER_HEIGHT + content_height + legend_height + tag_monitor_height + 20

    svg_parts = []
    svg_parts.append(svg_header(total_width, total_height))

    # Title bar spans full width
    svg_parts.append(f'''
  <!-- Title -->
  <rect x="0" y="0" width="{total_width}" height="{HEADER_HEIGHT}" fill="{COLORS["box_fill"]}"/>
  <text x="{ladder_width // 2}" y="18" class="title" style="text-anchor: middle;">LADDER LOGIC DIAGRAM</text>
  <line x1="0" y1="{HEADER_HEIGHT}" x2="{total_width}" y2="{HEADER_HEIGHT}" stroke="{COLORS["box_stroke"]}" stroke-width="1"/>
''')

    # Power rail labels (within ladder area)
    svg_parts.append(f'''
  <!-- Power Rail Labels -->
  <text x="{RAIL_WIDTH // 2}" y="{HEADER_HEIGHT + 12}" class="tag-type" style="text-anchor: middle;">L1</text>
  <text x="{RAIL_WIDTH // 2}" y="{HEADER_HEIGHT + 20}" class="tag-type" style="text-anchor: middle;">(HOT)</text>
  <text x="{ladder_width - RAIL_WIDTH // 2}" y="{HEADER_HEIGHT + 12}" class="tag-type" style="text-anchor: middle;">L2</text>
  <text x="{ladder_width - RAIL_WIDTH // 2}" y="{HEADER_HEIGHT + 20}" class="tag-type" style="text-anchor: middle;">(NEU)</text>
''')

    # Power rails
    rail_start_y = HEADER_HEIGHT + 22
    rail_end_y = HEADER_HEIGHT + rungs_height
    svg_parts.append(f'''
  <!-- Power Rails -->
  <line x1="{RAIL_WIDTH}" y1="{rail_start_y}" x2="{RAIL_WIDTH}" y2="{rail_end_y}"
        stroke="{COLORS["rail"]}" stroke-width="1"/>
  <line x1="{ladder_width - RAIL_WIDTH}" y1="{rail_start_y}" x2="{ladder_width - RAIL_WIDTH}" y2="{rail_end_y}"
        stroke="{COLORS["rail"]}" stroke-width="1"/>
''')

    # Render rungs
    y = HEADER_HEIGHT + 24
    for i, rung in enumerate(rungs):
        rung_svg, rung_h = svg_rung(rung, io_state, i + 1, y, ladder_width)
        svg_parts.append(rung_svg)
        y += rung_h

    # Legend at bottom of ladder area
    legend_y = HEADER_HEIGHT + content_height + 10
    svg_parts.append(f'''
  <!-- Legend -->
  <text x="{RAIL_WIDTH}" y="{legend_y}" class="legend">LEGEND:</text>
  <rect x="{RAIL_WIDTH + 55}" y="{legend_y - 9}" width="10" height="10" fill="{COLORS["energized"]}" rx="1"/>
  <text x="{RAIL_WIDTH + 70}" y="{legend_y}" class="legend">= Energized / TRUE</text>
  <rect x="{RAIL_WIDTH + 195}" y="{legend_y - 9}" width="10" height="10" fill="{COLORS["de_energized"]}" rx="1"/>
  <text x="{RAIL_WIDTH + 210}" y="{legend_y}" class="legend">= De-energized / FALSE</text>
''')

    # Tag monitor below the legend
    if include_io_table and num_tags > 0:
        tag_monitor_y = legend_y + 30
        table_svg, _ = svg_tag_monitor_bottom(io_state, 20, tag_monitor_y, total_width - 40)
        svg_parts.append(table_svg)

    svg_parts.append(svg_footer())

    return "\n".join(svg_parts)
