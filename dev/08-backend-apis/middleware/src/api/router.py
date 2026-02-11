"""API router aggregation."""
from fastapi import APIRouter

from .topic_mappings import router as mappings_router
from .key_transforms import router as transforms_router
from .unmapped import router as unmapped_router
from .streams import router as streams_router

api_router = APIRouter()

# Include all routers
api_router.include_router(mappings_router)
api_router.include_router(transforms_router)
api_router.include_router(unmapped_router)
api_router.include_router(streams_router)
