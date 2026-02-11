"""Machine CRUD API endpoints."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..models import (
    MachineDefinition,
    MachineStatus,
    CreateMachineRequest,
    MachineListResponse,
    MachineStatusResponse,
    FieldDefinition,
    GenerateRandomRequest,
    GeneratePromptedRequest,
    GeneratedMachineResponse,
    GenerateSMProfileRequest,
    GenerateSMProfileResponse,
    GenerateLadderRequest,
    GenerateLadderResponse,
    LadderProgram,
    LadderRung,
    LadderElement,
    IOMapping,
)
from ..services import machine_store, llm_generator

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/machines", tags=["machines"])


# ============== Generation Endpoints ==============

@router.post("/generate/random", response_model=GeneratedMachineResponse)
async def generate_random_machine(request: GenerateRandomRequest = None):
    """Generate a random machine definition using LLM."""
    try:
        return await llm_generator.generate_random()
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating random machine: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate machine")


@router.post("/generate/prompted", response_model=GeneratedMachineResponse)
async def generate_prompted_machine(request: GeneratePromptedRequest):
    """Generate a machine definition from user's description."""
    if not request.prompt:
        raise HTTPException(status_code=400, detail="prompt is required")

    try:
        return await llm_generator.generate_from_prompt(request.prompt)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating machine from prompt: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate machine")


@router.post("/generate/ladder", response_model=GenerateLadderResponse)
async def generate_ladder_logic(request: GenerateLadderRequest):
    """Generate ladder logic for a machine based on its type and fields.

    This endpoint uses LLM to generate plausible ladder logic rungs where:
    - Machine fields become exposed I/O (inputs and outputs)
    - Intermediary logic (latches, interlocks, timers) is added
    - The logic follows standard industrial automation patterns
    """
    if not request.fields:
        raise HTTPException(status_code=400, detail="fields are required")

    try:
        result = await llm_generator.generate_ladder(
            machine_type=request.machine_type,
            fields=request.fields,
            description=request.description,
        )

        # Parse the LLM response into our typed models
        ladder_program = result.get("ladder_program", {})
        io_mapping = result.get("io_mapping", {})

        # Convert rungs to typed model
        rungs = []
        for rung_data in ladder_program.get("rungs", []):
            elements = []
            for elem_data in rung_data.get("elements", []):
                elements.append(LadderElement(
                    type=elem_data.get("type"),
                    name=elem_data.get("name"),
                    preset_ms=elem_data.get("preset_ms"),
                    timer_type=elem_data.get("timer_type"),
                    preset=elem_data.get("preset"),
                    counter_type=elem_data.get("counter_type"),
                ))
            rungs.append(LadderRung(
                description=rung_data.get("description", ""),
                elements=elements,
            ))

        return GenerateLadderResponse(
            ladder_program=LadderProgram(rungs=rungs),
            io_mapping=IOMapping(
                inputs=io_mapping.get("inputs", []),
                outputs=io_mapping.get("outputs", []),
                internal=io_mapping.get("internal", []),
            ),
            rationale=result.get("rationale"),
        )

    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing LLM response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse ladder logic response")
    except Exception as e:
        logger.error(f"Error generating ladder logic: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate ladder logic")


@router.post("/generate/smprofile", response_model=GenerateSMProfileResponse)
async def generate_smprofile(request: GenerateSMProfileRequest):
    """Generate a CESMII SM Profile (Machine Identification) for a machine.

    Uses LLM to generate plausible OPC UA Machine Identification values
    based on the machine type, name, and description.
    """
    try:
        smprofile = await llm_generator.generate_smprofile(
            machine_type=request.machine_type,
            machine_name=request.machine_name,
            description=request.description,
        )
        return GenerateSMProfileResponse(smprofile=smprofile)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing SM Profile response: {e}")
        raise HTTPException(status_code=500, detail="Failed to parse SM Profile response")
    except Exception as e:
        logger.error(f"Error generating SM Profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate SM Profile")


# ============== CRUD Endpoints ==============


@router.get("", response_model=MachineListResponse)
async def list_machines(
    status: Optional[MachineStatus] = Query(None, description="Filter by status")
):
    """List all simulated machines."""
    machines = await machine_store.list_all(status=status)
    return MachineListResponse(machines=machines, total=len(machines))


@router.get("/by-creator/{creator_name}", response_model=MachineDefinition)
async def get_machine_by_creator(creator_name: str):
    """Get the most recent machine created by a specific person."""
    machine = await machine_store.get_by_creator(creator_name)
    if not machine:
        raise HTTPException(status_code=404, detail=f"No machine found for creator: {creator_name}")
    return machine


@router.get("/{machine_id}", response_model=MachineDefinition)
async def get_machine(machine_id: str):
    """Get a specific machine by ID."""
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    return machine


@router.post("", response_model=MachineDefinition)
async def create_machine(request: CreateMachineRequest):
    """Create a new machine in draft state."""
    logger.info(f"CREATE machine request: name={request.name}, topic_path={request.topic_path}")
    logger.info(f"  fields count: {len(request.fields) if request.fields else 0}")
    logger.info(f"  topics count: {len(request.topics) if request.topics else 0}")
    if request.topics:
        for i, t in enumerate(request.topics):
            logger.info(f"    topic[{i}]: path={t.topic_path}, fields={len(t.fields)}")

    # Reject duplicate machine names
    existing = await machine_store.find_by_name(request.name)
    if existing:
        logger.warning(f"Duplicate machine name rejected: '{request.name}' (existing id: {existing['id']})")
        raise HTTPException(
            status_code=409,
            detail=f"A machine with name '{request.name}' already exists (id: {existing['id']})"
        )

    machine = MachineDefinition(
        name=request.name,
        description=request.description,
        machine_type=request.machine_type,
        topic_path=request.topic_path,
        schema_proposal_id=request.schema_proposal_id,
        fields=request.fields,
        topics=request.topics,
        publish_interval_ms=request.publish_interval_ms,
        image_base64=request.image_base64,
        status=MachineStatus.DRAFT,
        similarity_results=request.similarity_results,
        sparkmes_enabled=request.sparkmes_enabled,
        sparkmes=request.sparkmes,
        smprofile=request.smprofile,
        created_by=request.created_by,
    )
    created = await machine_store.create(machine)
    logger.info(f"CREATED machine id={created.id}, topics={len(created.topics) if created.topics else 0}")
    return created


@router.put("/{machine_id}", response_model=MachineDefinition)
async def update_machine(machine_id: str, request: CreateMachineRequest):
    """Update an existing machine."""
    logger.info(f"UPDATE machine {machine_id}: name={request.name}")
    logger.info(f"  request.fields count: {len(request.fields) if request.fields else 0}")
    logger.info(f"  request.topics count: {len(request.topics) if request.topics else 0}")
    if request.topics:
        for i, t in enumerate(request.topics):
            logger.info(f"    topic[{i}]: path={t.topic_path}, fields={len(t.fields)}")

    existing = await machine_store.get(machine_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Machine not found")

    logger.info(f"  existing.topics count before update: {len(existing.topics) if existing.topics else 0}")

    existing.name = request.name
    existing.description = request.description
    existing.machine_type = request.machine_type
    existing.topic_path = request.topic_path
    existing.schema_proposal_id = request.schema_proposal_id
    existing.fields = request.fields
    existing.topics = request.topics  # Fix: copy multi-topic definitions
    existing.publish_interval_ms = request.publish_interval_ms
    existing.sparkmes_enabled = request.sparkmes_enabled
    existing.sparkmes = request.sparkmes
    existing.smprofile = request.smprofile

    logger.info(f"  existing.topics count after update: {len(existing.topics) if existing.topics else 0}")
    logger.info(f"  sparkmes_enabled: {existing.sparkmes_enabled}")

    updated = await machine_store.update(existing)
    logger.info(f"UPDATED machine {machine_id}, final topics={len(updated.topics) if updated.topics else 0}")
    return updated


@router.delete("/{machine_id}")
async def delete_machine(machine_id: str):
    """Delete a machine."""
    # First stop if running
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if machine.status == MachineStatus.RUNNING:
        # Import here to avoid circular imports
        from ..services.publisher import publisher
        await publisher.stop_machine(machine_id)

    deleted = await machine_store.delete(machine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Machine not found")

    return {"success": True}


@router.post("/{machine_id}/start")
async def start_machine(machine_id: str):
    """Start publishing for a machine."""
    logger.info(f"START machine {machine_id}")
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    logger.info(f"  machine.name: {machine.name}")
    logger.info(f"  machine.topic_path: {machine.topic_path}")
    logger.info(f"  machine.fields count: {len(machine.fields) if machine.fields else 0}")
    logger.info(f"  machine.topics count: {len(machine.topics) if machine.topics else 0}")
    if machine.topics:
        for i, t in enumerate(machine.topics):
            logger.info(f"    topic[{i}]: path={t.topic_path}, fields={len(t.fields)}")
            for f in t.fields:
                logger.info(f"      field: {f.name} type={f.type}")

    # Check get_all_topics() result
    all_topics = machine.get_all_topics()
    logger.info(f"  get_all_topics() returned {len(all_topics)} topics")
    for i, t in enumerate(all_topics):
        logger.info(f"    all_topics[{i}]: path={t.topic_path}, fields={len(t.fields)}")

    if machine.status == MachineStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Machine is already running")

    # Import here to avoid circular imports
    from ..services.publisher import publisher
    await publisher.start_machine(machine)

    await machine_store.update_status(machine_id, MachineStatus.RUNNING)

    logger.info(f"STARTED machine {machine_id} successfully")
    return {"success": True, "status": "running"}


@router.post("/{machine_id}/stop")
async def stop_machine(machine_id: str):
    """Stop publishing for a machine."""
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if machine.status != MachineStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Machine is not running")

    # Import here to avoid circular imports
    from ..services.publisher import publisher
    await publisher.stop_machine(machine_id)

    await machine_store.update_status(machine_id, MachineStatus.DRAFT)

    return {"success": True, "status": "draft"}


@router.get("/{machine_id}/status", response_model=MachineStatusResponse)
async def get_machine_status(machine_id: str):
    """Get the current status of a machine."""
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    # Import here to avoid circular imports
    from ..services.publisher import publisher
    stats = publisher.get_machine_stats(machine_id)

    return MachineStatusResponse(
        id=machine.id,
        name=machine.name,
        status=machine.status,
        is_running=machine.status == MachineStatus.RUNNING,
        last_published_at=machine.last_published_at,
        messages_published=stats.get("messages_published", 0) if stats else 0
    )


@router.get("/{machine_id}/stream")
async def stream_machine_payloads(machine_id: str):
    """Stream realtime payloads for a machine via SSE."""
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    if machine.status != MachineStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Machine is not running")

    # Import here to avoid circular imports
    from ..services.publisher import publisher

    async def event_generator():
        """Generate SSE events with payload data."""
        last_payloads = {}
        last_sparkmes = None
        interval_seconds = machine.publish_interval_ms / 1000.0

        while True:
            stats = publisher.get_machine_stats(machine_id)
            if not stats:
                # Machine may have stopped
                yield f"event: stopped\ndata: {json.dumps({'message': 'Machine stopped'})}\n\n"
                break

            current_payloads = stats.get("last_payloads", {})

            # Send any new/changed payloads
            for topic_path, payload in current_payloads.items():
                if payload != last_payloads.get(topic_path):
                    event_data = {
                        "type": "telemetry",
                        "topic": topic_path,
                        "payload": payload,
                        "timestamp": datetime.utcnow().isoformat(),
                        "messages_published": stats.get("messages_published", 0)
                    }
                    yield f"data: {json.dumps(event_data)}\n\n"
                    last_payloads[topic_path] = payload

            # Send SparkMES payload if changed
            sparkmes_payload = stats.get("last_sparkmes_payload")
            if sparkmes_payload and sparkmes_payload != last_sparkmes:
                sparkmes_event = {
                    "type": "sparkmes",
                    "payload": sparkmes_payload,
                    "timestamp": datetime.utcnow().isoformat(),
                    "sparkmes_published": stats.get("sparkmes_published", 0)
                }
                yield f"data: {json.dumps(sparkmes_event)}\n\n"
                last_sparkmes = sparkmes_payload

            await asyncio.sleep(interval_seconds * 0.5)  # Poll at 2x publish rate

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ============== Ladder Logic Storage Endpoints ==============

from pydantic import BaseModel


class SaveLadderLogicRequest(BaseModel):
    """Request to save ladder logic for a machine."""
    rungs: list[dict]
    io_mapping: dict
    rationale: Optional[str] = None


class LadderLogicResponse(BaseModel):
    """Response containing ladder logic data."""
    rungs: list[dict]
    io_mapping: dict
    rationale: Optional[str] = None
    created_at: Optional[str] = None


@router.post("/{machine_id}/ladder", response_model=LadderLogicResponse)
async def save_machine_ladder_logic(machine_id: str, request: SaveLadderLogicRequest):
    """Save ladder logic for a machine.

    Stores the ladder logic configuration in Neo4j, associated with the machine.
    If ladder logic already exists for this machine, it will be replaced.
    """
    # Verify machine exists
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    try:
        result = await machine_store.save_ladder_logic(
            machine_id=machine_id,
            rungs=request.rungs,
            io_mapping=request.io_mapping,
            rationale=request.rationale
        )

        return LadderLogicResponse(
            rungs=result["rungs"],
            io_mapping=result["io_mapping"],
            rationale=result["rationale"],
            created_at=result["created_at"]
        )
    except Exception as e:
        logger.error(f"Error saving ladder logic for machine {machine_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save ladder logic")


@router.get("/{machine_id}/ladder", response_model=LadderLogicResponse)
async def get_machine_ladder_logic(machine_id: str):
    """Get ladder logic for a machine.

    Returns the stored ladder logic configuration, or 404 if none exists.
    """
    # Verify machine exists
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    result = await machine_store.get_ladder_logic(machine_id)
    if not result:
        raise HTTPException(status_code=404, detail="No ladder logic found for this machine")

    return LadderLogicResponse(
        rungs=result["rungs"],
        io_mapping=result["io_mapping"],
        rationale=result["rationale"],
        created_at=result["created_at"]
    )


@router.delete("/{machine_id}/ladder")
async def delete_machine_ladder_logic(machine_id: str):
    """Delete ladder logic for a machine."""
    # Verify machine exists
    machine = await machine_store.get(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")

    deleted = await machine_store.delete_ladder_logic(machine_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="No ladder logic found for this machine")

    return {"success": True}
