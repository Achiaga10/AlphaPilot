from fastapi import APIRouter

from alphapilot.api.routes.health import router as health_router

router = APIRouter(prefix="/api/v1")

router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)
