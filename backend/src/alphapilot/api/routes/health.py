from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "application": "AlphaPilot",
    }
