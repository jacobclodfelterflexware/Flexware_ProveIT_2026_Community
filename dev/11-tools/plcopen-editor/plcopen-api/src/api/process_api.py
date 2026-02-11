"""REST API endpoints for process simulation."""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from services.process_simulator import (
    ProcessSimulator,
    ProcessMachine,
    ConveyorMachine,
    TankMachine,
    TrafficLightMachine,
    StartStopMachine,
    get_process_simulator,
    reset_process_simulator,
    PROCESS_SCENARIOS,
    get_scenario,
)
from services.ladder_simulator import get_ladder_simulator
from services.ladder_parser import parse_ladder

router = APIRouter(prefix="/plcopen/simulate/process", tags=["Process Simulator"])
logger = logging.getLogger(__name__)

# Background task reference
_process_task: Optional[asyncio.Task] = None


# Request/Response Models
class SimpleResponse(BaseModel):
    success: bool
    message: str


class ProcessStatusResponse(BaseModel):
    success: bool
    running: bool
    machine_count: int
    machines: Dict[str, Any] = {}


class ScenarioResponse(BaseModel):
    success: bool
    message: str
    scenario_name: str
    ladder_rungs: int = 0
    machines: List[str] = []


class ScenarioListResponse(BaseModel):
    scenarios: List[str]
    descriptions: Dict[str, str] = {}


# Endpoints


@router.get("/scenarios", response_model=ScenarioListResponse, summary="List available scenarios")
async def list_scenarios():
    """Get list of available process simulation scenarios.

    Each scenario includes:
    - Pre-configured physical machines
    - Matching ladder logic program
    - Automatic I/O simulation
    """
    return ScenarioListResponse(
        scenarios=list(PROCESS_SCENARIOS.keys()),
        descriptions={
            "conveyor": "Conveyor belt with entry/exit sensors and auto-cycling start/stop",
            "tank": "Tank level control with fill/drain valves and level sensors",
            "motor_control": "Simple motor start/stop with automatic button cycling",
        },
    )


@router.post("/scenarios/{name}/load", response_model=ScenarioResponse, summary="Load a scenario")
async def load_scenario(name: str):
    """Load a complete process simulation scenario.

    This will:
    1. Load the corresponding ladder program
    2. Set up process simulation machines
    3. Attach machines to the ladder simulator

    After loading, call /start to begin both simulations.
    """
    global _process_task

    try:
        scenario = get_scenario(name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    # Stop any running simulations
    ladder_sim = get_ladder_simulator()
    process_sim = get_process_simulator()

    if ladder_sim.running:
        ladder_sim.stop()
    if process_sim.running:
        process_sim.stop()

    # Reset process simulator
    reset_process_simulator()
    process_sim = get_process_simulator()

    # Load ladder program
    ladder_program = scenario.get("ladder_program", {"rungs": []})
    rungs = parse_ladder(ladder_program)
    ladder_sim.load_program(rungs)

    # Attach process simulator to ladder simulator
    process_sim.attach_simulator(ladder_sim)

    # Add machines from scenario
    machines = scenario.get("machines", [])
    for machine in machines:
        process_sim.add_machine(machine)

    # Initialize any special I/O values for scenarios
    if name == "tank":
        # Enable drain for tank demo
        ladder_sim.write_io("Drain_Enable", True)

    return ScenarioResponse(
        success=True,
        message=f"Loaded scenario '{name}'",
        scenario_name=scenario["name"],
        ladder_rungs=len(rungs),
        machines=[m.name for m in machines],
    )


@router.post("/start", response_model=SimpleResponse, summary="Start process simulation")
async def start_process_simulation():
    """Start both process and ladder simulations."""
    global _process_task

    process_sim = get_process_simulator()
    ladder_sim = get_ladder_simulator()

    if process_sim.running and ladder_sim.running:
        return SimpleResponse(success=True, message="Simulation already running")

    if not ladder_sim.rungs:
        raise HTTPException(status_code=400, detail="No ladder program loaded. Load a scenario first.")

    # Start ladder simulator
    if not ladder_sim.running:
        asyncio.create_task(ladder_sim.start())

    # Start process simulator
    if not process_sim.running:
        _process_task = asyncio.create_task(process_sim.start())

    return SimpleResponse(success=True, message="Process and ladder simulation started")


@router.post("/stop", response_model=SimpleResponse, summary="Stop process simulation")
async def stop_process_simulation():
    """Stop both process and ladder simulations."""
    global _process_task

    process_sim = get_process_simulator()
    ladder_sim = get_ladder_simulator()

    # Stop both
    process_sim.stop()
    ladder_sim.stop()

    if _process_task and not _process_task.done():
        _process_task.cancel()
        try:
            await _process_task
        except asyncio.CancelledError:
            pass

    return SimpleResponse(
        success=True,
        message=f"Simulation stopped after {ladder_sim.stats.scan_count} scans",
    )


@router.post("/reset", response_model=SimpleResponse, summary="Reset process simulation")
async def reset_process_simulation():
    """Reset both process and ladder simulations."""
    process_sim = get_process_simulator()
    ladder_sim = get_ladder_simulator()

    # Stop if running
    if process_sim.running:
        process_sim.stop()
    if ladder_sim.running:
        ladder_sim.stop()

    # Reset ladder simulator I/O
    ladder_sim.reset()

    # Clear and reset process simulator
    reset_process_simulator()

    return SimpleResponse(success=True, message="Simulation reset")


@router.get("/status", response_model=ProcessStatusResponse, summary="Get process simulation status")
async def get_process_status():
    """Get current status of process simulation including all machines."""
    process_sim = get_process_simulator()
    status = process_sim.get_status()

    return ProcessStatusResponse(
        success=True,
        running=status["running"],
        machine_count=status["machine_count"],
        machines=status["machines"],
    )


@router.get("/machines", summary="List active machines")
async def list_machines():
    """Get list of currently active machines in the process simulation."""
    process_sim = get_process_simulator()
    return {
        "machines": [
            {
                "name": m.name,
                "type": type(m).__name__,
                "enabled": m.enabled,
            }
            for m in process_sim.machines.values()
        ]
    }


@router.post("/machines/{name}/enable", response_model=SimpleResponse, summary="Enable a machine")
async def enable_machine(name: str):
    """Enable a specific machine."""
    process_sim = get_process_simulator()

    if name not in process_sim.machines:
        raise HTTPException(status_code=404, detail=f"Machine '{name}' not found")

    process_sim.machines[name].enabled = True
    return SimpleResponse(success=True, message=f"Machine '{name}' enabled")


@router.post("/machines/{name}/disable", response_model=SimpleResponse, summary="Disable a machine")
async def disable_machine(name: str):
    """Disable a specific machine (pauses its simulation)."""
    process_sim = get_process_simulator()

    if name not in process_sim.machines:
        raise HTTPException(status_code=404, detail=f"Machine '{name}' not found")

    process_sim.machines[name].enabled = False
    return SimpleResponse(success=True, message=f"Machine '{name}' disabled")
