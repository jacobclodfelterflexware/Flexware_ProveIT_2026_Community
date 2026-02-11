"""API router aggregation."""
from fastapi import APIRouter

from .import_export import router as plcopen_router
from .simulate import router as simulate_router
from .ladder_api import router as ladder_router
from .process_api import router as process_router

api_router = APIRouter()
api_router.include_router(plcopen_router)
api_router.include_router(simulate_router)
api_router.include_router(ladder_router)
api_router.include_router(process_router)
