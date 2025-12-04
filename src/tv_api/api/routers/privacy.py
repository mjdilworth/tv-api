"""Static informational endpoints."""

from fastapi import APIRouter

from tv_api.config import get_settings

router = APIRouter(tags=["info"])


@router.get("/privacy", summary="Privacy policy")
async def privacy_policy() -> dict[str, str]:
    """Return a minimal privacy statement suitable for store listings."""

    settings = get_settings()
    policy = (
        "Dilworth Creative LLC only processes the information required to deliver"
        " purchased art shows. Email addresses are used strictly to authenticate"
        " purchases, and any media streaming activity stays on your device. No"
        " personal data is sold or shared with third parties."
    )
    return {
        "application": settings.app_name,
        "owner": "Dilworth Creative LLC",
        "contact": "support@pickletv.local",
        "policy": policy,
    }
