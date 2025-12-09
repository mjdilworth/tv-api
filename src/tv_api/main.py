"""Application entrypoint."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from tv_api.api.routers import auth, content, health, privacy, shopify, users
from tv_api.config import get_settings
from tv_api.database import db
from tv_api.logging import configure_logging
from tv_api.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events."""
    # Startup
    await db.connect()
    yield
    # Shutdown
    await db.disconnect()


def create_application() -> FastAPI:
    """Build and configure a FastAPI instance."""

    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(content.router)
    app.include_router(privacy.router)
    app.include_router(shopify.router)
    app.include_router(users.router)
    return app


app = create_application()
