from fastapi import APIRouter

from alphapilot.api.routes.admin_data import router as admin_data_router
from alphapilot.api.routes.companies import (
    router as companies_router,
)
from alphapilot.api.routes.copilot import router as copilot_router
from alphapilot.api.routes.daily_candles import (
    router as daily_candles_router,
)
from alphapilot.api.routes.health import (
    router as health_router,
)
from alphapilot.api.routes.market import (
    router as market_router,
)
from alphapilot.api.routes.portfolio import router as portfolio_router
from alphapilot.api.routes.research_datasets import router as research_datasets_router
from alphapilot.api.routes.scanner import (
    router as scanner_router,
)
from alphapilot.api.routes.universe import (
    router as universe_router,
)

router = APIRouter(
    prefix="/api/v1",
)


router.include_router(
    health_router,
    prefix="/health",
    tags=["Health"],
)

router.include_router(
    companies_router,
)

router.include_router(
    daily_candles_router,
)

router.include_router(
    market_router,
)

router.include_router(
    scanner_router,
)

router.include_router(
    universe_router,
)

router.include_router(portfolio_router)

router.include_router(copilot_router)

router.include_router(admin_data_router)

router.include_router(research_datasets_router)
