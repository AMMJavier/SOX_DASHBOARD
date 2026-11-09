from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .inventory import router as inventory_router
from .locations import router as locations_router
from .upload import router as upload_router
from .logs import router as logs_router

router = APIRouter(prefix="/assets", tags=["Assets"])

router.include_router(dashboard_router)
router.include_router(inventory_router)
router.include_router(locations_router)
router.include_router(upload_router)
router.include_router(logs_router)