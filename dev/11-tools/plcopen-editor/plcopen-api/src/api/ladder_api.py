"""REST API endpoints for the ladder logic simulator."""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.ladder_simulator import (
    LadderSimulator,
    get_ladder_simulator,
    reset_ladder_simulator,
)
from services.ladder_parser import parse_ladder, get_example_program, EXAMPLE_PROGRAMS
from services.ladder_ascii import render_full_diagram
from services.ladder_svg import render_ladder_svg

router = APIRouter(prefix="/plcopen/simulate/ladder", tags=["Ladder Simulator"])
logger = logging.getLogger(__name__)

# Background task reference
_run_task: Optional[asyncio.Task] = None


# Request/Response Models
class LadderProgramRequest(BaseModel):
    """Request to load a ladder program."""

    program: Dict[str, Any] = Field(
        ...,
        description="Ladder program in JSON format",
        example={
            "rungs": [
                {
                    "description": "Motor Control",
                    "elements": [
                        {"type": "contact", "name": "Start"},
                        {"type": "inverted_contact", "name": "Stop"},
                        {"type": "output", "name": "Motor"},
                    ],
                }
            ]
        },
    )


class LoadResponse(BaseModel):
    """Response for load operation."""

    success: bool
    message: str
    rung_count: int = 0
    variables: List[str] = []


class StatusResponse(BaseModel):
    """Response for status request."""

    success: bool
    running: bool
    auto_simulate: bool = False
    scan_time_ms: int
    rung_count: int
    io_count: int
    stats: Dict[str, Any] = {}


class IOReadResponse(BaseModel):
    """Response for I/O read."""

    success: bool
    io: Dict[str, Any]
    inputs: Dict[str, bool] = {}
    outputs: Dict[str, Any] = {}  # Can be bool or numeric (float)


class IOWriteRequest(BaseModel):
    """Request to write I/O values."""

    values: Dict[str, Any] = Field(
        ...,
        description="Dictionary of variable name to value",
        example={"Start": True, "Stop": False},
    )


class IOWriteResponse(BaseModel):
    """Response for I/O write."""

    success: bool
    message: str
    io: Dict[str, Any] = {}


class RenderResponse(BaseModel):
    """Response for ASCII render."""

    success: bool
    ascii: str
    rung_count: int = 0


class SimpleResponse(BaseModel):
    """Simple success/failure response."""

    success: bool
    message: str


# Endpoints


@router.post("/load", response_model=LoadResponse, summary="Load ladder program")
async def load_program(request: LadderProgramRequest):
    """Load a ladder program from JSON.

    The program format supports:
    - **contact**: Normally Open (NO) contact
    - **inverted_contact**: Normally Closed (NC) contact
    - **output**: Output coil
    - **set_coil**: Set/Latch coil
    - **reset_coil**: Reset/Unlatch coil
    - **timer**: Timer (TON/TOFF/PULSE)
    - **counter**: Counter (CTU/CTD)
    """
    try:
        rungs = parse_ladder(request.program)
        simulator = get_ladder_simulator()

        # Stop if running
        if simulator.running:
            simulator.stop()

        simulator.load_program(rungs)

        # Get all variable names
        variables = list(simulator.io_state.keys())

        return LoadResponse(
            success=True,
            message=f"Loaded {len(rungs)} rungs",
            rung_count=len(rungs),
            variables=variables,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading program: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class LoadJsonRequest(BaseModel):
    """Request to load ladder program with rungs array directly."""

    rungs: List[Dict[str, Any]] = Field(
        ...,
        description="Array of rungs to load",
        example=[
            {
                "description": "Motor Control",
                "elements": [
                    {"type": "contact", "name": "Start"},
                    {"type": "inverted_contact", "name": "Stop"},
                    {"type": "output", "name": "Motor"},
                ],
            }
        ],
    )


@router.post("/load-json", response_model=LoadResponse, summary="Load ladder from JSON rungs")
async def load_json_program(request: LoadJsonRequest):
    """Load a ladder program from a rungs array directly.

    This is a convenience endpoint that accepts rungs directly without
    wrapping in a 'program' object. Useful for loading LLM-generated ladder logic.
    """
    try:
        # Wrap in the expected format
        program = {"rungs": request.rungs}
        rungs = parse_ladder(program)
        simulator = get_ladder_simulator()

        # Stop if running
        if simulator.running:
            simulator.stop()

        simulator.load_program(rungs)

        # Get all variable names
        variables = list(simulator.io_state.keys())

        return LoadResponse(
            success=True,
            message=f"Loaded {len(rungs)} rungs",
            rung_count=len(rungs),
            variables=variables,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading program: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/load-example/{name}",
    response_model=LoadResponse,
    summary="Load example program",
)
async def load_example(name: str):
    """Load a built-in example program.

    Available examples:
    - **simple**: Simple input to output copy
    - **motor_control**: Start/Stop motor control
    - **latch**: Set/Reset latch example
    - **timer_demo**: Timer demonstration
    """
    try:
        program = get_example_program(name)
        rungs = parse_ladder(program)
        simulator = get_ladder_simulator()

        if simulator.running:
            simulator.stop()

        simulator.load_program(rungs)
        variables = list(simulator.io_state.keys())

        return LoadResponse(
            success=True,
            message=f"Loaded example '{name}' with {len(rungs)} rungs",
            rung_count=len(rungs),
            variables=variables,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error loading example: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/examples", summary="List available examples")
async def list_examples():
    """Get list of available example programs."""
    return {
        "examples": list(EXAMPLE_PROGRAMS.keys()),
        "descriptions": {
            "simple": "Simple input to output copy",
            "motor_control": "Start/Stop motor control with NC stop",
            "latch": "Set/Reset latch circuit",
            "timer_demo": "ON-delay timer demonstration",
        },
    }


@router.post("/start", response_model=SimpleResponse, summary="Start simulation")
async def start_simulation():
    """Start the ladder scan cycle.

    The simulator will continuously evaluate rungs at the configured scan rate.
    """
    global _run_task
    simulator = get_ladder_simulator()

    if simulator.running:
        return SimpleResponse(success=True, message="Simulator already running")

    if not simulator.rungs:
        raise HTTPException(status_code=400, detail="No program loaded")

    # Start in background
    _run_task = asyncio.create_task(simulator.start())

    return SimpleResponse(success=True, message="Simulation started")


@router.post("/stop", response_model=SimpleResponse, summary="Stop simulation")
async def stop_simulation():
    """Stop the ladder scan cycle."""
    global _run_task
    simulator = get_ladder_simulator()

    if not simulator.running:
        return SimpleResponse(success=True, message="Simulator not running")

    simulator.stop()

    # Cancel the task if it exists
    if _run_task and not _run_task.done():
        _run_task.cancel()
        try:
            await _run_task
        except asyncio.CancelledError:
            pass

    return SimpleResponse(
        success=True,
        message=f"Simulation stopped after {simulator.stats.scan_count} scans",
    )


@router.post("/reset", response_model=SimpleResponse, summary="Reset simulator")
async def reset_simulation():
    """Reset the simulator to initial state.

    Clears all I/O values and resets timers/counters.
    """
    simulator = get_ladder_simulator()

    if simulator.running:
        simulator.stop()

    simulator.reset()

    return SimpleResponse(success=True, message="Simulator reset")


@router.post("/auto-sim/start", response_model=SimpleResponse, summary="Start automatic I/O simulation")
async def start_auto_simulation():
    """Start automatic simulation of inputs.

    This makes the ladder diagram dynamic by automatically toggling inputs
    in realistic patterns (pulse behavior like button presses).

    Each input will pulse ON briefly at different intervals, creating
    a dynamic visualization of the ladder logic in action.
    """
    simulator = get_ladder_simulator()

    if not simulator.rungs:
        raise HTTPException(status_code=400, detail="No program loaded")

    simulator.enable_auto_simulation()

    return SimpleResponse(success=True, message="Auto-simulation started")


@router.post("/auto-sim/stop", response_model=SimpleResponse, summary="Stop automatic I/O simulation")
async def stop_auto_simulation():
    """Stop automatic input simulation.

    Inputs will retain their last values but will no longer change automatically.
    """
    simulator = get_ladder_simulator()
    simulator.disable_auto_simulation()

    return SimpleResponse(success=True, message="Auto-simulation stopped")


@router.post(
    "/single-scan", response_model=SimpleResponse, summary="Execute single scan"
)
async def single_scan():
    """Execute a single scan cycle without starting continuous mode.

    Useful for step-by-step debugging.
    """
    simulator = get_ladder_simulator()

    if not simulator.rungs:
        raise HTTPException(status_code=400, detail="No program loaded")

    if simulator.running:
        raise HTTPException(
            status_code=400, detail="Stop continuous mode before single-scan"
        )

    simulator.single_scan()

    return SimpleResponse(
        success=True, message=f"Executed scan cycle #{simulator.stats.scan_count}"
    )


@router.get("/status", response_model=StatusResponse, summary="Get simulator status")
async def get_status():
    """Get current simulator status including statistics."""
    simulator = get_ladder_simulator()
    status = simulator.get_status()

    return StatusResponse(
        success=True,
        running=status["running"],
        auto_simulate=status.get("auto_simulate", False),
        scan_time_ms=status["scan_time_ms"],
        rung_count=status["rung_count"],
        io_count=status["io_count"],
        stats=status["stats"],
    )


@router.get("/io", response_model=IOReadResponse, summary="Read all I/O values")
async def read_all_io():
    """Read all I/O values."""
    simulator = get_ladder_simulator()

    return IOReadResponse(
        success=True,
        io=simulator.read_io(),
        inputs=simulator.get_inputs(),
        outputs=simulator.get_outputs(),
    )


@router.post("/io", response_model=IOWriteResponse, summary="Write multiple I/O values")
async def write_multiple_io(request: IOWriteRequest):
    """Write multiple I/O values and execute a scan cycle.

    Values written via this API are marked as 'external' so they persist
    across scan cycles. This is useful for injecting real values from
    external sources like MQTT.
    """
    simulator = get_ladder_simulator()

    # Mark as external so values persist across scan cycles (e.g., MQTT injection)
    simulator.write_multiple_io(request.values, external=True)

    # Execute immediate scan if not in continuous mode
    if not simulator.running:
        simulator.single_scan()

    return IOWriteResponse(
        success=True,
        message=f"Wrote {len(request.values)} values (external)",
        io=simulator.read_io(),
    )


@router.post(
    "/io/{name}", response_model=IOWriteResponse, summary="Write single I/O value"
)
async def write_single_io(name: str, value: bool = Query(..., description="Value to write")):
    """Write a single I/O value and execute a scan cycle.

    Args:
        name: Variable name to write
        value: Boolean value (true/false)
    """
    simulator = get_ladder_simulator()

    simulator.write_io(name, value)

    # Execute immediate scan if not in continuous mode
    if not simulator.running:
        simulator.single_scan()

    return IOWriteResponse(
        success=True,
        message=f"Set {name} = {value}",
        io=simulator.read_io(),
    )


@router.get("/render", response_model=RenderResponse, summary="Render ASCII diagram")
async def render_ascii(
    include_io_table: bool = Query(True, description="Include I/O state table"),
    include_legend: bool = Query(False, description="Include symbol legend"),
    width: int = Query(72, ge=40, le=120, description="Diagram width"),
    title: Optional[str] = Query(None, description="Optional title"),
):
    """Render the ladder diagram as ASCII art with live state.

    The diagram shows:
    - ● for ON/True state
    - ○ for OFF/False state
    - /X for Normally Closed contacts
    """
    simulator = get_ladder_simulator()

    if not simulator.rungs:
        return RenderResponse(
            success=True,
            ascii="No program loaded",
            rung_count=0,
        )

    ascii_output = render_full_diagram(
        rungs=simulator.rungs,
        io_state=simulator.io_state,
        title=title,
        include_io_table=include_io_table,
        include_legend=include_legend,
        width=width,
    )

    return RenderResponse(
        success=True,
        ascii=ascii_output,
        rung_count=len(simulator.rungs),
    )


@router.get("/render/plain", summary="Render plain ASCII (no JSON wrapper)")
async def render_ascii_plain(
    include_io_table: bool = Query(True, description="Include I/O state table"),
    include_legend: bool = Query(False, description="Include symbol legend"),
    width: int = Query(72, ge=40, le=120, description="Diagram width"),
    title: Optional[str] = Query(None, description="Optional title"),
):
    """Render the ladder diagram as plain ASCII text.

    Returns plain text instead of JSON for easier viewing.
    """
    from fastapi.responses import PlainTextResponse

    simulator = get_ladder_simulator()

    if not simulator.rungs:
        return PlainTextResponse("No program loaded")

    ascii_output = render_full_diagram(
        rungs=simulator.rungs,
        io_state=simulator.io_state,
        title=title,
        include_io_table=include_io_table,
        include_legend=include_legend,
        width=width,
    )

    return PlainTextResponse(ascii_output)


@router.get("/render/svg", summary="Render SVG diagram")
async def render_svg(
    include_io_table: bool = Query(True, description="Include I/O state table"),
    title: Optional[str] = Query(None, description="Optional title"),
):
    """Render the ladder diagram as SVG with live state.

    Returns SVG image with Allen-Bradley style rendering:
    - Green for energized/TRUE elements
    - Gray for de-energized/FALSE elements
    - Clear visual contacts, coils, and power rails
    """
    from fastapi.responses import Response

    simulator = get_ladder_simulator()

    if not simulator.rungs:
        # Return empty SVG with message
        svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="100">
  <rect width="100%" height="100%" fill="#1a1a2e"/>
  <text x="200" y="50" fill="#FFFFFF" font-family="monospace" text-anchor="middle">No program loaded</text>
</svg>'''
        return Response(content=svg, media_type="image/svg+xml")

    svg_output = render_ladder_svg(
        rungs=simulator.rungs,
        io_state=simulator.io_state,
        title=title,
        include_io_table=include_io_table,
    )

    return Response(content=svg_output, media_type="image/svg+xml")


@router.get("/render/live", summary="Live simulation viewer")
async def render_live():
    """Render an interactive HTML page with live simulation updates.

    Features:
    - Auto-refreshing SVG diagram (updates every 100ms)
    - Click on inputs to toggle their values
    - Start/Stop simulation controls
    - Real-time state visualization
    - Process simulation with automatic I/O (conveyor, tank, etc.)
    """
    from fastapi.responses import HTMLResponse

    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ladder Logic Live Simulator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #1a1a2e;
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: #2a2a4a;
            padding: 15px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #4a4a6a;
            flex-wrap: wrap;
            gap: 10px;
        }
        .header h1 {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 1px;
            color: #00ff00;
        }
        .controls {
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        .btn {
            padding: 8px 16px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-family: inherit;
            font-size: 12px;
            font-weight: bold;
        }
        .btn-start { background: #00aa00; color: #fff; }
        .btn-start:hover { background: #00cc00; }
        .btn-stop { background: #aa0000; color: #fff; }
        .btn-stop:hover { background: #cc0000; }
        .btn-reset { background: #666; color: #fff; }
        .btn-reset:hover { background: #888; }
        .btn-load { background: #0066aa; color: #fff; }
        .btn-load:hover { background: #0088cc; }
        .status {
            padding: 5px 12px;
            border-radius: 4px;
            font-size: 11px;
        }
        .status-running { background: #004400; color: #00ff00; }
        .status-stopped { background: #440000; color: #ff6666; }
        .main {
            display: flex;
            height: calc(100vh - 60px);
        }
        .diagram-panel {
            flex: 1;
            padding: 20px;
            overflow: auto;
        }
        #ladder-svg {
            background: #1a1a2e;
            border: 1px solid #4a4a6a;
            border-radius: 5px;
        }
        .side-panel {
            width: 320px;
            background: #252540;
            border-left: 2px solid #4a4a6a;
            padding: 15px;
            overflow-y: auto;
        }
        .side-panel h2 {
            font-size: 14px;
            margin-bottom: 15px;
            color: #aaa;
            border-bottom: 1px solid #4a4a6a;
            padding-bottom: 8px;
        }
        .io-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            margin-bottom: 8px;
            background: #1a1a2e;
            border-radius: 4px;
            border: 1px solid #4a4a6a;
        }
        .io-item.clickable { cursor: pointer; }
        .io-item.clickable:hover { background: #2a2a4a; border-color: #00ff00; }
        .io-name { font-weight: 600; font-size: 12px; font-family: 'SF Mono', 'Consolas', 'Monaco', monospace; }
        .io-value {
            padding: 3px 10px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: 600;
            font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
        }
        .io-value.true { background: #004400; color: #00ff00; }
        .io-value.false { background: #333; color: #888; }
        .select-box {
            width: 100%;
            padding: 8px;
            margin-bottom: 10px;
            background: #1a1a2e;
            color: #fff;
            border: 1px solid #4a4a6a;
            border-radius: 4px;
            font-family: inherit;
            font-size: 12px;
        }
        .section {
            margin-bottom: 20px;
        }
        .section-title {
            font-size: 12px;
            color: #00ff00;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .scan-info {
            font-size: 11px;
            color: #888;
            margin-top: 15px;
            padding-top: 10px;
            border-top: 1px solid #4a4a6a;
        }
        .machine-card {
            background: #1a1a2e;
            border: 1px solid #4a4a6a;
            border-radius: 4px;
            padding: 12px;
            margin-bottom: 10px;
        }
        .machine-card h4 {
            font-size: 12px;
            color: #00aaff;
            margin-bottom: 8px;
        }
        .machine-var {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            padding: 4px 0;
            border-bottom: 1px solid #333;
        }
        .machine-var:last-child { border-bottom: none; }
        .var-name { color: #aaa; }
        .var-value { color: #fff; }
        .mode-tabs {
            display: flex;
            gap: 5px;
            margin-bottom: 15px;
        }
        .mode-tab {
            flex: 1;
            padding: 8px;
            border: 1px solid #4a4a6a;
            background: #1a1a2e;
            color: #888;
            cursor: pointer;
            text-align: center;
            font-size: 11px;
            border-radius: 4px;
        }
        .mode-tab.active {
            background: #004400;
            color: #00ff00;
            border-color: #00ff00;
        }
        .mode-tab:hover:not(.active) {
            background: #2a2a4a;
        }
        .hint {
            font-size: 10px;
            color: #666;
            margin-bottom: 10px;
            font-style: italic;
        }
        .progress-bar {
            height: 8px;
            background: #333;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 5px;
        }
        .progress-fill {
            height: 100%;
            background: #00aaff;
            transition: width 0.1s;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>LADDER LOGIC SIMULATOR</h1>
        <div class="controls">
            <button class="btn btn-start" onclick="startSim()">START</button>
            <button class="btn btn-stop" onclick="stopSim()">STOP</button>
            <button class="btn btn-reset" onclick="resetSim()">RESET</button>
            <span id="status" class="status status-stopped">STOPPED</span>
        </div>
    </div>
    <div class="main">
        <div class="diagram-panel">
            <div id="ladder-svg"></div>
        </div>
        <div class="side-panel">
            <div class="mode-tabs">
                <div class="mode-tab active" onclick="setMode('process')" id="tab-process">PROCESS SIM</div>
                <div class="mode-tab" onclick="setMode('manual')" id="tab-manual">MANUAL</div>
            </div>

            <div id="process-mode">
                <div class="section">
                    <div class="section-title">LOAD SCENARIO</div>
                    <p class="hint">Auto-simulates physical I/O behavior</p>
                    <select id="scenario-select" class="select-box" onchange="loadScenario()">
                        <option value="">-- Select Scenario --</option>
                        <option value="conveyor">Conveyor Belt</option>
                        <option value="tank">Tank Level Control</option>
                        <option value="motor_control">Motor Start/Stop</option>
                    </select>
                </div>

                <div class="section" id="machine-section" style="display: none;">
                    <div class="section-title">ACTIVE MACHINES</div>
                    <div id="machine-list"></div>
                </div>
            </div>

            <div id="manual-mode" style="display: none;">
                <div class="section">
                    <div class="section-title">LOAD EXAMPLE</div>
                    <p class="hint">Manual I/O control - click inputs to toggle</p>
                    <select id="example-select" class="select-box" onchange="loadExample()">
                        <option value="">-- Select Example --</option>
                        <option value="simple">Simple</option>
                        <option value="motor_control">Motor Control</option>
                        <option value="latch">Latch</option>
                        <option value="timer_demo">Timer Demo</option>
                    </select>
                </div>
            </div>

            <div class="section">
                <div class="section-title">INPUTS</div>
                <p class="hint" id="io-hint">Click to toggle (manual mode only)</p>
                <div id="input-list"></div>
            </div>

            <div class="section">
                <div class="section-title">OUTPUTS</div>
                <div id="output-list"></div>
            </div>

            <div class="scan-info">
                <div>Scan Count: <span id="scan-count">0</span></div>
                <div>Mode: <span id="sim-mode">Process</span></div>
            </div>
        </div>
    </div>

    <script>
        const LADDER_API = '/api/plcopen/simulate/ladder';
        const PROCESS_API = '/api/plcopen/simulate/process';
        let updateInterval = null;
        let isRunning = false;
        let currentMode = 'process';  // 'process' or 'manual'

        async function fetchJSON(url, method = 'GET') {
            const resp = await fetch(url, { method });
            return resp.json();
        }

        function setMode(mode) {
            currentMode = mode;
            document.getElementById('tab-process').className = mode === 'process' ? 'mode-tab active' : 'mode-tab';
            document.getElementById('tab-manual').className = mode === 'manual' ? 'mode-tab active' : 'mode-tab';
            document.getElementById('process-mode').style.display = mode === 'process' ? 'block' : 'none';
            document.getElementById('manual-mode').style.display = mode === 'manual' ? 'block' : 'none';
            document.getElementById('sim-mode').textContent = mode === 'process' ? 'Process' : 'Manual';
            document.getElementById('io-hint').textContent = mode === 'process' ?
                'Controlled by process simulation' : 'Click to toggle';
        }

        async function loadScenario() {
            const select = document.getElementById('scenario-select');
            const name = select.value;
            if (!name) return;

            // Stop any running simulation
            await fetch(PROCESS_API + '/stop', { method: 'POST' });

            // Load the scenario
            await fetch(PROCESS_API + '/scenarios/' + name + '/load', { method: 'POST' });

            document.getElementById('machine-section').style.display = 'block';
            updateDiagram();
        }

        async function loadExample() {
            const select = document.getElementById('example-select');
            const name = select.value;
            if (!name) return;
            await fetch(LADDER_API + '/load-example/' + name, { method: 'POST' });
            select.value = '';
            updateDiagram();
        }

        async function startSim() {
            if (currentMode === 'process') {
                await fetch(PROCESS_API + '/start', { method: 'POST' });
            } else {
                await fetch(LADDER_API + '/start', { method: 'POST' });
                await fetch(LADDER_API + '/auto-sim/start', { method: 'POST' });
            }
            isRunning = true;
            document.getElementById('status').className = 'status status-running';
            document.getElementById('status').textContent = 'RUNNING';
        }

        async function stopSim() {
            if (currentMode === 'process') {
                await fetch(PROCESS_API + '/stop', { method: 'POST' });
            } else {
                await fetch(LADDER_API + '/auto-sim/stop', { method: 'POST' });
                await fetch(LADDER_API + '/stop', { method: 'POST' });
            }
            isRunning = false;
            document.getElementById('status').className = 'status status-stopped';
            document.getElementById('status').textContent = 'STOPPED';
        }

        async function resetSim() {
            if (currentMode === 'process') {
                await fetch(PROCESS_API + '/reset', { method: 'POST' });
            } else {
                await fetch(LADDER_API + '/reset', { method: 'POST' });
            }
            document.getElementById('machine-section').style.display = 'none';
            document.getElementById('scenario-select').value = '';
            updateDiagram();
        }

        async function toggleIO(name) {
            // Only allow toggling in manual mode
            if (currentMode !== 'manual') return;

            const resp = await fetchJSON(LADDER_API + '/io');
            const currentValue = resp.io[name];
            await fetch(LADDER_API + '/io/' + name + '?value=' + (!currentValue), { method: 'POST' });
            updateDiagram();
        }

        async function updateDiagram() {
            try {
                // Fetch SVG
                const svgResp = await fetch(LADDER_API + '/render/svg');
                const svgText = await svgResp.text();
                document.getElementById('ladder-svg').innerHTML = svgText;

                // Fetch ladder status and I/O
                const status = await fetchJSON(LADDER_API + '/status');
                const io = await fetchJSON(LADDER_API + '/io');

                // Update scan count
                document.getElementById('scan-count').textContent = status.stats.scan_count || 0;

                // Update running status
                if (status.running !== isRunning) {
                    isRunning = status.running;
                    document.getElementById('status').className = 'status ' + (isRunning ? 'status-running' : 'status-stopped');
                    document.getElementById('status').textContent = isRunning ? 'RUNNING' : 'STOPPED';
                }

                // Update inputs list
                const inputList = document.getElementById('input-list');
                const inputs = io.inputs || {};
                let inputHtml = '';
                for (const [name, value] of Object.entries(inputs)) {
                    const clickable = currentMode === 'manual' ? 'clickable' : '';
                    const onclick = currentMode === 'manual' ? `onclick="toggleIO('${name}')"` : '';
                    inputHtml += `
                        <div class="io-item ${clickable}" ${onclick}>
                            <span class="io-name">${name}</span>
                            <span class="io-value ${value ? 'true' : 'false'}">${value ? 'TRUE' : 'FALSE'}</span>
                        </div>
                    `;
                }
                inputList.innerHTML = inputHtml || '<div class="io-item"><span class="io-name" style="color:#666">No inputs</span></div>';

                // Update outputs list
                const outputList = document.getElementById('output-list');
                const outputs = io.outputs || {};
                let outputHtml = '';
                for (const [name, value] of Object.entries(outputs)) {
                    outputHtml += `
                        <div class="io-item">
                            <span class="io-name">${name}</span>
                            <span class="io-value ${value ? 'true' : 'false'}">${value ? 'TRUE' : 'FALSE'}</span>
                        </div>
                    `;
                }
                outputList.innerHTML = outputHtml || '<div class="io-item"><span class="io-name" style="color:#666">No outputs</span></div>';

                // Update machine status (only in process mode)
                if (currentMode === 'process') {
                    try {
                        const processStatus = await fetchJSON(PROCESS_API + '/status');
                        updateMachineStatus(processStatus.machines || {});
                    } catch (e) {
                        // Process API might not be loaded yet
                    }
                }
            } catch (e) {
                console.error('Update error:', e);
            }
        }

        function updateMachineStatus(machines) {
            const machineList = document.getElementById('machine-list');
            let html = '';

            for (const [name, info] of Object.entries(machines)) {
                html += `<div class="machine-card">
                    <h4>${name}</h4>`;

                // Show variables
                const vars = info.variables || {};
                for (const [varName, value] of Object.entries(vars)) {
                    const displayValue = typeof value === 'number' ? value.toFixed(1) : value;
                    html += `<div class="machine-var">
                        <span class="var-name">${varName}</span>
                        <span class="var-value">${displayValue}</span>
                    </div>`;

                    // Add progress bar for level-type variables
                    if (varName === 'level') {
                        const percent = Math.min(100, Math.max(0, value));
                        html += `<div class="progress-bar"><div class="progress-fill" style="width: ${percent}%"></div></div>`;
                    }
                }

                // Show pending events count
                if (info.pending_events > 0) {
                    html += `<div class="machine-var">
                        <span class="var-name">pending events</span>
                        <span class="var-value">${info.pending_events}</span>
                    </div>`;
                }

                html += '</div>';
            }

            if (html) {
                machineList.innerHTML = html;
                document.getElementById('machine-section').style.display = 'block';
            }
        }

        // Start update loop
        updateInterval = setInterval(updateDiagram, 100);
        updateDiagram();
    </script>
</body>
</html>'''

    return HTMLResponse(content=html)


@router.get("/render/simple", summary="Simplified live simulation viewer")
async def render_simple():
    """Render a simplified HTML page with just ladder diagram and I/O toggles.

    This is a minimal viewer designed for embedding in iframes:
    - Ladder diagram (auto-refreshing SVG)
    - Click on inputs to toggle their values
    - Start/Stop/Reset controls
    - No process simulation, no scenarios, no machine status
    """
    from fastapi.responses import HTMLResponse

    html = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ladder Logic Simulator</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #1a1a2e;
            color: #00ff00;
            letter-spacing: 0.5px;
            min-height: 100vh;
        }
        .header {
            background: #2a2a4a;
            padding: 6px 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #4a4a6a;
            flex-wrap: wrap;
            gap: 6px;
        }
        .header h1 {
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 1px;
            color: #00ff00;
        }
        .controls {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        .btn {
            padding: 4px 8px;
            border: none;
            border-radius: 2px;
            cursor: pointer;
            font-family: inherit;
            font-size: 11px;
            font-weight: bold;
        }
        .btn-start { background: #00aa00; color: #fff; }
        .btn-start:hover { background: #00cc00; }
        .btn-stop { background: #aa0000; color: #fff; }
        .btn-stop:hover { background: #cc0000; }
        .btn-reset { background: #666; color: #fff; }
        .btn-reset:hover { background: #888; }
        .status {
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 10px;
        }
        .status-running { background: #004400; color: #00ff00; }
        .status-stopped { background: #440000; color: #ff6666; }
        .main {
            display: flex;
            min-height: calc(100vh - 50px);
        }
        .diagram-panel {
            flex: 1;
            padding: 15px;
        }
        #ladder-svg {
            background: #1a1a2e;
            border: 1px solid #4a4a6a;
            border-radius: 5px;
        }
        .side-panel {
            width: 180px;
            background: #252540;
            border-left: 1px solid #4a4a6a;
            padding: 8px;
        }
        .section {
            margin-bottom: 10px;
        }
        .section-title {
            font-size: 10px;
            color: #00ff00;
            margin-bottom: 5px;
            display: flex;
            align-items: center;
            gap: 4px;
            letter-spacing: 1px;
            text-transform: uppercase;
            font-weight: 600;
        }
        .io-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 4px 6px;
            margin-bottom: 3px;
            background: #1a1a2e;
            border-radius: 2px;
            border: 1px solid #4a4a6a;
            cursor: pointer;
        }
        .io-item:hover { background: #2a2a4a; border-color: #00ff00; }
        .io-item.output { cursor: default; }
        .io-item.output:hover { background: #1a1a2e; border-color: #4a4a6a; }
        .io-name { font-weight: 600; font-size: 9px; font-family: 'SF Mono', 'Consolas', 'Monaco', monospace; color: #00ff00; letter-spacing: 0.5px; }
        .io-value {
            padding: 1px 5px;
            border-radius: 2px;
            font-size: 9px;
            font-weight: 600;
            font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
        }
        .io-value.true { background: #004400; color: #00ff00; }
        .io-value.false { background: #333; color: #888; }
        .io-value.numeric { background: #003366; color: #66aaff; }
        .hint {
            font-size: 8px;
            color: #666;
            margin-bottom: 6px;
            font-style: italic;
        }
        .scan-info {
            font-size: 9px;
            color: #888;
            margin-top: 8px;
            padding-top: 6px;
            border-top: 1px solid #4a4a6a;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>LADDER LOGIC</h1>
        <div class="controls">
            <button class="btn btn-start" onclick="startSim()">START</button>
            <button class="btn btn-stop" onclick="stopSim()">STOP</button>
            <button class="btn btn-reset" onclick="resetSim()">RESET</button>
            <span id="status" class="status status-stopped">STOPPED</span>
        </div>
    </div>
    <div class="main">
        <div class="diagram-panel">
            <div id="ladder-svg"></div>
        </div>
        <div class="side-panel">
            <div class="section">
                <div class="section-title">OUTPUTS</div>
                <div id="output-list"></div>
            </div>

            <div class="scan-info">
                <div>Scan Count: <span id="scan-count">0</span></div>
            </div>
        </div>
    </div>

    <script>
        const LADDER_API = '/api/plcopen/simulate/ladder';
        let updateInterval = null;
        let isRunning = false;

        async function fetchJSON(url, method = 'GET') {
            const resp = await fetch(url, { method });
            return resp.json();
        }

        async function startSim() {
            await fetch(LADDER_API + '/start', { method: 'POST' });
            await fetch(LADDER_API + '/auto-sim/start', { method: 'POST' });
            isRunning = true;
            document.getElementById('status').className = 'status status-running';
            document.getElementById('status').textContent = 'RUNNING';
        }

        async function stopSim() {
            await fetch(LADDER_API + '/auto-sim/stop', { method: 'POST' });
            await fetch(LADDER_API + '/stop', { method: 'POST' });
            isRunning = false;
            document.getElementById('status').className = 'status status-stopped';
            document.getElementById('status').textContent = 'STOPPED';
        }

        async function resetSim() {
            await fetch(LADDER_API + '/reset', { method: 'POST' });
            updateDiagram();
        }

        async function updateDiagram() {
            try {
                // Fetch SVG (without TAG MONITOR - include_io_table=false)
                const svgResp = await fetch(LADDER_API + '/render/svg?include_io_table=false');
                const svgText = await svgResp.text();
                document.getElementById('ladder-svg').innerHTML = svgText;

                // Fetch status and I/O
                const status = await fetchJSON(LADDER_API + '/status');
                const io = await fetchJSON(LADDER_API + '/io');

                // Update scan count
                document.getElementById('scan-count').textContent = status.stats.scan_count || 0;

                // Update running status
                if (status.running !== isRunning) {
                    isRunning = status.running;
                    document.getElementById('status').className = 'status ' + (isRunning ? 'status-running' : 'status-stopped');
                    document.getElementById('status').textContent = isRunning ? 'RUNNING' : 'STOPPED';
                }

                // Update outputs list
                const outputList = document.getElementById('output-list');
                const outputs = io.outputs || {};
                let outputHtml = '';
                for (const [name, value] of Object.entries(outputs)) {
                    // Handle different value types: boolean, number, or other
                    let displayValue, cssClass;
                    if (typeof value === 'boolean') {
                        displayValue = value ? 'TRUE' : 'FALSE';
                        cssClass = value ? 'true' : 'false';
                    } else if (typeof value === 'number') {
                        displayValue = value.toFixed(2);
                        cssClass = 'numeric';
                    } else {
                        displayValue = String(value);
                        cssClass = 'numeric';
                    }
                    outputHtml += `
                        <div class="io-item output">
                            <span class="io-name">${name}</span>
                            <span class="io-value ${cssClass}">${displayValue}</span>
                        </div>
                    `;
                }
                outputList.innerHTML = outputHtml || '<div class="io-item output"><span class="io-name" style="color:#666">No outputs</span></div>';
            } catch (e) {
                console.error('Update error:', e);
            }
            // Send height to parent for iframe resizing
            sendHeightToParent();
        }

        // Send content height to parent for iframe resizing
        function sendHeightToParent() {
            const height = document.body.scrollHeight;
            window.parent.postMessage({ type: 'resize-iframe', height: height }, '*');
        }

        // Start update loop
        updateInterval = setInterval(updateDiagram, 100);
        updateDiagram();
        window.addEventListener('load', sendHeightToParent);
    </script>
</body>
</html>'''

    return HTMLResponse(content=html)
