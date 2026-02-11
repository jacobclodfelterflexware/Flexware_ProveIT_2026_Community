import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from .models import (
    ChartGenerateRequest,
    ChartGenerateResponse,
    ChartValidateRequest,
    ChartValidateResponse,
    SkillListResponse,
    SkillInfo,
    ErrorResponse,
)

router = APIRouter()


@router.post("/chart/generate", response_model=ChartGenerateResponse)
async def generate_chart(request: ChartGenerateRequest, req: Request):
    """
    Generate a chart from natural language.

    1. Uses RAG to find relevant topics/fields
    2. LLM selects skill and generates parameters
    3. Validates parameters against skill schema
    4. Executes skill to generate chart config
    """
    try:
        rag_service = req.app.state.rag_service
        llm_service = req.app.state.llm_service
        skill_executor = req.app.state.skill_executor
        skill_registry = req.app.state.skill_registry
        stream_manager = req.app.state.stream_manager

        # Step 1: RAG retrieval
        rag_context = await rag_service.retrieve_context(
            query=request.query,
            preferences=request.preferences
        )

        if not rag_context.matching_topics:
            raise HTTPException(
                status_code=404,
                detail="No matching topics found for your query. Try being more specific about the data you want to visualize."
            )

        # Step 2: LLM skill selection and parameter generation
        skill_selection = await llm_service.select_skill_and_params(
            query=request.query,
            rag_context=rag_context,
            available_skills=skill_registry.get_skill_summaries(),
            preferences=request.preferences
        )

        # Step 3: Validate parameters
        validation_result = skill_executor.validate_parameters(
            skill_id=skill_selection.skill_id,
            parameters=skill_selection.parameters,
            rag_context=rag_context
        )

        if not validation_result.valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid parameters: {', '.join(validation_result.errors)}"
            )

        # Step 4: Execute skill
        chart_id = str(uuid.uuid4())
        chart_result = await skill_executor.execute(
            skill_id=skill_selection.skill_id,
            parameters=validation_result.sanitized_parameters,
            chart_id=chart_id
        )

        # Step 5: Set up streaming if supported
        skill = skill_registry.get_skill(skill_selection.skill_id)
        stream_url = ""
        if skill.supports_streaming:
            subscriptions = skill.build_subscriptions(validation_result.sanitized_parameters)
            stream_manager.register_chart(chart_id, subscriptions, skill)
            stream_url = f"/api/chart/stream/{chart_id}"

        return ChartGenerateResponse(
            chart_id=chart_id,
            skill_used=skill_selection.skill_id,
            chart_config=chart_result.chart_config,
            initial_data=chart_result.initial_data,
            stream_url=stream_url,
            parameters_used=validation_result.sanitized_parameters,
            reasoning=skill_selection.reasoning or "Selected based on query analysis.",
            rag_context=rag_context
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/chart/stream/{chart_id}")
async def stream_chart_updates(chart_id: str, req: Request):
    """
    SSE stream for real-time chart updates.
    """
    stream_manager = req.app.state.stream_manager

    if not stream_manager.has_chart(chart_id):
        raise HTTPException(status_code=404, detail="Chart not found or streaming not enabled")

    async def event_generator():
        async for message in stream_manager.subscribe(chart_id):
            yield {
                "event": message.type,
                "data": message.model_dump_json()
            }

    return EventSourceResponse(event_generator())


@router.post("/chart/validate", response_model=ChartValidateResponse)
async def validate_chart_params(request: ChartValidateRequest, req: Request):
    """
    Validate skill parameters without executing.
    Useful for LLM self-checking before final submission.
    """
    skill_executor = req.app.state.skill_executor

    try:
        # Create a minimal RAG context for validation
        # In real usage, this would come from the generate flow
        result = skill_executor.validate_parameters(
            skill_id=request.skill_id,
            parameters=request.parameters,
            rag_context=None  # Skip semantic validation
        )

        return ChartValidateResponse(
            valid=result.valid,
            errors=result.errors,
            sanitized_parameters=result.sanitized_parameters
        )
    except Exception as e:
        return ChartValidateResponse(
            valid=False,
            errors=[str(e)]
        )


@router.get("/skills", response_model=SkillListResponse)
async def list_skills(req: Request):
    """
    List all available chart skills with their schemas.
    """
    skill_registry = req.app.state.skill_registry

    skills = [
        SkillInfo(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            category=skill.category,
            parameters_schema=skill.parameters_schema,
            chart_type=skill.chart_type,
            supports_streaming=skill.supports_streaming
        )
        for skill in skill_registry.skills.values()
    ]

    return SkillListResponse(skills=skills)


@router.get("/skills/{skill_id}")
async def get_skill(skill_id: str, req: Request):
    """
    Get details for a specific skill.
    """
    skill_registry = req.app.state.skill_registry
    skill = skill_registry.get_skill(skill_id)

    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found")

    return SkillInfo(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        category=skill.category,
        parameters_schema=skill.parameters_schema,
        chart_type=skill.chart_type,
        supports_streaming=skill.supports_streaming
    )


@router.delete("/chart/{chart_id}")
async def stop_chart_stream(chart_id: str, req: Request):
    """
    Stop streaming for a chart and clean up resources.
    """
    stream_manager = req.app.state.stream_manager

    if stream_manager.has_chart(chart_id):
        await stream_manager.unregister_chart(chart_id)
        return {"status": "stopped", "chart_id": chart_id}

    return {"status": "not_found", "chart_id": chart_id}
