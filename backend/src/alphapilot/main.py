from fastapi import FastAPI

from alphapilot.api.router import router
from alphapilot.core.config import settings
from alphapilot.core.lifespan import lifespan

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.include_router(router)
