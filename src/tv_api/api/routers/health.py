"""Health and readiness endpoints."""

from fastapi import APIRouter

from tv_api.config import get_settings

router = APIRouter(tags=["diagnostics"])


@router.get("/health", summary="Liveness probe")
async def health_check() -> dict[str, str]:
    """Signal that the API process is running."""

    settings = get_settings()
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@router.get("/readiness", summary="Readiness probe")
async def readiness_check() -> dict[str, str]:
    """Signal that the API is ready to accept traffic."""

    return {"status": "ready"}
