"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from reglens import __version__
from reglens.api.deps import RateLimiter
from reglens.api.routes import ask, documents, impact
from reglens.config import Settings, get_settings
from reglens.log import configure_logging, get_logger
from reglens.services import Services

log = get_logger(__name__)
ops = APIRouter(tags=["ops"])


@ops.get("/health")
def health() -> dict[str, str]:
    """Liveness: the process is up."""
    return {"status": "ok"}


@ops.get("/ready")
def ready() -> dict[str, str]:
    """Readiness: the process can serve (models load lazily on first question)."""
    return {"status": "ready", "version": __version__}


@ops.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


def create_app(settings: Settings | None = None, services: Services | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level, settings.log_json)
        log.info("api_started", version=__version__, serving=settings.serving_variant)
        yield

    app = FastAPI(
        title="RegLens API",
        version=__version__,
        description="Cited, time-aware answers over RBI, SEBI, FCA and PRA regulation.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.services = services or Services(settings)
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["*"],
    )
    app.include_router(ops)
    app.include_router(ask.router)
    app.include_router(documents.router)
    app.include_router(impact.router)
    return app
