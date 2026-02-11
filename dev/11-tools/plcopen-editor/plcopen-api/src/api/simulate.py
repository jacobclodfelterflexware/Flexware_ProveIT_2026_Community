"""Simulation API endpoints for OpenPLC Runtime integration."""
import logging
from typing import Optional, Dict, List, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.project_store import get_project_store
from services.plcopen_converter import convert_plcopen_to_st
from services.openplc_client import get_openplc_client
from services.modbus_client import get_modbus_client

router = APIRouter(prefix="/plcopen/simulate", tags=["Simulation"])
logger = logging.getLogger(__name__)


# Request/Response schemas
class LoadProgramRequest(BaseModel):
    """Request to load a program into the simulator."""

    project_id: str
    program_name: Optional[str] = None


class LoadProgramResponse(BaseModel):
    """Response for load program request."""

    success: bool
    message: str
    st_code: Optional[str] = None


class SimulationStatusResponse(BaseModel):
    """Response for simulation status."""

    success: bool
    status: str
    message: Optional[str] = None


class IOValue(BaseModel):
    """Single I/O value."""

    name: str
    value: Any
    address: Optional[str] = None


class IOReadResponse(BaseModel):
    """Response for I/O read."""

    success: bool
    digital_inputs: List[bool] = []
    digital_outputs: List[bool] = []
    analog_inputs: List[int] = []
    analog_outputs: List[int] = []
    memory_words: List[int] = []
    message: Optional[str] = None


class IOWriteRequest(BaseModel):
    """Request to write I/O values."""

    digital_outputs: Optional[Dict[int, bool]] = None
    analog_outputs: Optional[Dict[int, int]] = None
    memory_words: Optional[Dict[int, int]] = None


class IOWriteResponse(BaseModel):
    """Response for I/O write."""

    success: bool
    message: str


class ConvertRequest(BaseModel):
    """Request to convert XML to ST without loading."""

    xml_content: str


class ConvertResponse(BaseModel):
    """Response for XML to ST conversion."""

    success: bool
    st_code: Optional[str] = None
    message: Optional[str] = None


class LoadSTRequest(BaseModel):
    """Request to load raw ST code directly."""

    st_code: str
    program_name: Optional[str] = "DirectSTProgram"
    description: Optional[str] = "Program uploaded directly as ST"


@router.post(
    "/load",
    response_model=LoadProgramResponse,
    summary="Load program into simulator",
    description="Convert PLCopen XML project to Structured Text and upload to OpenPLC Runtime.",
)
async def load_program(request: LoadProgramRequest):
    """Load a saved project into the OpenPLC Runtime simulator."""
    # Get project from storage
    store = get_project_store()
    xml_content = store.get_project(request.project_id)

    if xml_content is None:
        raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")

    try:
        # Convert PLCopen XML to Structured Text
        st_code = convert_plcopen_to_st(xml_content)
        logger.info(f"Converted project {request.project_id} to ST")

        # Upload to OpenPLC Runtime
        client = get_openplc_client()
        program_name = request.program_name or f"Project_{request.project_id}"

        result = client.upload_program(
            st_code=st_code,
            program_name=program_name,
            description=f"Project {request.project_id} loaded via API",
        )

        if result["success"]:
            return LoadProgramResponse(
                success=True,
                message="Program loaded and compiled successfully",
                st_code=st_code,
            )
        else:
            return LoadProgramResponse(
                success=False,
                message=result.get("message", "Upload failed"),
                st_code=st_code,
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Conversion error: {e}")
    except Exception as e:
        logger.error(f"Error loading program: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/convert",
    response_model=ConvertResponse,
    summary="Convert XML to Structured Text",
    description="Convert PLCopen XML to IEC 61131-3 Structured Text without loading into simulator.",
)
async def convert_xml_to_st(request: ConvertRequest):
    """Convert PLCopen XML to Structured Text."""
    try:
        st_code = convert_plcopen_to_st(request.xml_content)
        return ConvertResponse(
            success=True,
            st_code=st_code,
            message="Conversion successful",
        )
    except ValueError as e:
        return ConvertResponse(
            success=False,
            message=f"Conversion error: {e}",
        )
    except Exception as e:
        logger.error(f"Error converting XML: {e}")
        return ConvertResponse(
            success=False,
            message=str(e),
        )


@router.post(
    "/load-st",
    response_model=LoadProgramResponse,
    summary="Load ST code directly",
    description="Upload IEC 61131-3 Structured Text code directly to OpenPLC Runtime (bypasses XML conversion).",
)
async def load_st_directly(request: LoadSTRequest):
    """Load ST code directly into OpenPLC Runtime.

    This endpoint bypasses PLCopen XML conversion and uploads
    raw Structured Text code directly to the runtime.
    """
    try:
        client = get_openplc_client()

        result = client.upload_program(
            st_code=request.st_code,
            program_name=request.program_name,
            description=request.description,
        )

        if result["success"]:
            return LoadProgramResponse(
                success=True,
                message="ST program uploaded and compiled successfully",
                st_code=request.st_code,
            )
        else:
            return LoadProgramResponse(
                success=False,
                message=result.get("message", "Upload failed"),
                st_code=request.st_code,
            )
    except Exception as e:
        logger.error(f"Error loading ST program: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/start",
    response_model=SimulationStatusResponse,
    summary="Start PLC simulation",
    description="Start the PLC program execution in OpenPLC Runtime.",
)
async def start_simulation():
    """Start the PLC simulation."""
    client = get_openplc_client()
    result = client.start_plc()

    return SimulationStatusResponse(
        success=result["success"],
        status="running" if result["success"] else "error",
        message=result.get("message"),
    )


@router.post(
    "/stop",
    response_model=SimulationStatusResponse,
    summary="Stop PLC simulation",
    description="Stop the PLC program execution in OpenPLC Runtime.",
)
async def stop_simulation():
    """Stop the PLC simulation."""
    client = get_openplc_client()
    result = client.stop_plc()

    return SimulationStatusResponse(
        success=result["success"],
        status="stopped" if result["success"] else "error",
        message=result.get("message"),
    )


@router.get(
    "/status",
    response_model=SimulationStatusResponse,
    summary="Get simulation status",
    description="Get the current status of the PLC simulation.",
)
async def get_simulation_status():
    """Get current simulation status."""
    client = get_openplc_client()
    result = client.get_status()

    return SimulationStatusResponse(
        success=result["success"],
        status=result.get("status", "unknown"),
        message=result.get("message"),
    )


@router.get(
    "/io",
    response_model=IOReadResponse,
    summary="Read I/O values",
    description="Read current I/O values from the running PLC simulation via Modbus.",
)
async def read_io(
    digital_inputs: int = 8,
    digital_outputs: int = 8,
    analog_inputs: int = 0,
    analog_outputs: int = 0,
    memory_words: int = 0,
):
    """Read I/O values from the PLC simulation."""
    client = get_modbus_client()
    result = client.read_all_io(
        digital_inputs=digital_inputs,
        digital_outputs=digital_outputs,
        analog_inputs=analog_inputs,
        analog_outputs=analog_outputs,
        memory_words=memory_words,
    )

    if result["success"]:
        io_data = result["io"]
        return IOReadResponse(
            success=True,
            digital_inputs=io_data.get("digital_inputs", []),
            digital_outputs=io_data.get("digital_outputs", []),
            analog_inputs=io_data.get("analog_inputs", []),
            analog_outputs=io_data.get("analog_outputs", []),
            memory_words=io_data.get("memory_words", []),
        )
    else:
        return IOReadResponse(
            success=False,
            message=result.get("message", "Failed to read I/O"),
        )


@router.post(
    "/io",
    response_model=IOWriteResponse,
    summary="Write I/O values",
    description="Write I/O values to the running PLC simulation via Modbus.",
)
async def write_io(request: IOWriteRequest):
    """Write I/O values to the PLC simulation."""
    client = get_modbus_client()

    io_values = {}

    # Convert request format to client format
    if request.digital_outputs:
        io_values["digital_outputs"] = list(request.digital_outputs.items())

    if request.analog_outputs:
        io_values["analog_outputs"] = list(request.analog_outputs.items())

    if request.memory_words:
        io_values["memory_words"] = list(request.memory_words.items())

    result = client.write_io(io_values)

    return IOWriteResponse(
        success=result["success"],
        message=result.get("message", ""),
    )


@router.post(
    "/io/coil/{address}",
    response_model=IOWriteResponse,
    summary="Write single coil",
    description="Write a single digital output (coil) value.",
)
async def write_single_coil(address: int, value: bool):
    """Write a single coil value."""
    client = get_modbus_client()
    result = client.write_coil(address, value)

    return IOWriteResponse(
        success=result["success"],
        message=result.get("message", ""),
    )


@router.post(
    "/io/register/{address}",
    response_model=IOWriteResponse,
    summary="Write single register",
    description="Write a single holding register value.",
)
async def write_single_register(address: int, value: int):
    """Write a single register value."""
    client = get_modbus_client()
    result = client.write_register(address, value)

    return IOWriteResponse(
        success=result["success"],
        message=result.get("message", ""),
    )
