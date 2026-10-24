"""FastAPI app factory with the production basics: health, readiness, metrics, API key."""

from __future__ import annotations

import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest
from pydantic import BaseModel

from reglens import __version__
from reglens.config import Settings, get_settings
from reglens.log import configure_logging, get_logger

log = get_logger(__name__)
REQUESTS = Counter("reglens_requests_total", "Handled /v1 requests", ["endpoint"])


def require_api_key(request: Request, x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = request.app.state.settings.api_key
    if expected is None:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected.get_secret_value()):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


ops = APIRouter(tags=["ops"])
v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)])


@ops.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@ops.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready", "version": __version__}


@ops.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


class EchoIn(BaseModel):
    text: str


@v1.post("/echo")
def echo(body: EchoIn) -> dict[str, str]:
    """Replace with the project's real endpoints."""
    REQUESTS.labels("echo").inc()
    return {"echo": body.text}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(settings.log_level, settings.log_json)
        app.state.settings = settings
        log.info("api_started", version=__version__)
        yield

    app = FastAPI(title="RegLens API", version=__version__, lifespan=lifespan)
    app.include_router(ops)
    app.include_router(v1)
    return app
