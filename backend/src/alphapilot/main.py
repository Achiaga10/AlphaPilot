from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from alphapilot.api.router import router
from alphapilot.core.config import settings
from alphapilot.core.lifespan import lifespan

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

app.include_router(router)
