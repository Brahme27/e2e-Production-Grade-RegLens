"""Shared API plumbing: auth, rate limiting, metrics, access to services."""

from __future__ import annotations

import secrets
import threading
import time
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request
from prometheus_client import Counter, Histogram

REQUESTS = Counter("reglens_requests_total", "Handled /v1 requests", ["endpoint"])
ASK_OUTCOMES = Counter("reglens_ask_outcomes_total", "Answers by outcome", ["outcome"])
ASK_LATENCY = Histogram(
    "reglens_ask_seconds", "End-to-end /v1/ask latency", buckets=(0.1, 0.3, 0.5, 1, 2, 4, 6, 10, 20)
)
FEEDBACK = Counter("reglens_feedback_total", "User feedback", ["score"])
MAX_TRACKED_CLIENTS = 10_000


def require_api_key(request: Request, x_api_key: Annotated[str | None, Header()] = None) -> None:
    expected = request.app.state.settings.api_key
    if expected is None:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected.get_secret_value()):
        raise HTTPException(status_code=401, detail="invalid or missing API key")


class RateLimiter:
    """Token bucket per client: ``rate`` requests per minute, bursts up to ``rate``."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(client, (float(self.per_minute), now))
            tokens = min(float(self.per_minute), tokens + (now - last) * self.per_minute / 60)
            if tokens < 1:
                self._buckets[client] = (tokens, now)
                return False
            self._buckets[client] = (tokens - 1, now)
            if len(self._buckets) > MAX_TRACKED_CLIENTS:  # bounded memory: forget the idlest
                idlest = sorted(self._buckets, key=lambda k: self._buckets[k][1])
                for key in idlest[: len(idlest) // 2]:
                    del self._buckets[key]
            return True


def client_id(request: Request) -> str:
    """Who is calling, for rate limiting. Not the API key: every console user shares the proxy's
    key. The rightmost X-Forwarded-For hop is the one written by the nearest trusted proxy (the
    console's BFF or the AWS load balancer); hops to its left are whatever the client claimed."""
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    if hops:
        return hops[-1]
    return request.client.host if request.client else "anonymous"


def rate_limited(request: Request) -> None:
    limiter: RateLimiter = request.app.state.rate_limiter
    if not limiter.allow(client_id(request)):
        raise HTTPException(status_code=429, detail="too many requests, slow down")


def services(request: Request) -> Any:
    return request.app.state.services


AUTH = [Depends(require_api_key)]
