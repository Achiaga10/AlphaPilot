from fastapi import APIRouter

from alphapilot.api.routes import health

router = APIRouter(prefix="/api/v1")

router.include_router(
    health.router,
    prefix="/health",
    tags=["Health"],
)
