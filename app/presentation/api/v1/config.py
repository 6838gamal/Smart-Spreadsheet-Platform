"""Public configuration endpoint — exposes non-secret values the mobile app needs."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import settings

router = APIRouter()


@router.get("/api/v1/config/public")
async def public_config():
    """Return client-safe configuration values.

    GOOGLE_CLIENT_ID is a public OAuth identifier — safe to expose.
    Never include SECRET_KEY, SESSION_SECRET, or database URLs here.
    """
    return JSONResponse({
        "google_client_id":  settings.GOOGLE_CLIENT_ID,
        "google_enabled":    bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
        "app_name":          settings.APP_NAME,
        "app_version":       settings.APP_VERSION,
    })
