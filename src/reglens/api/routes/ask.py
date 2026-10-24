"""POST /v1/ask (Server-Sent Events or JSON) and POST /v1/feedback."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from reglens.api.deps import (
    ASK_LATENCY,
    ASK_OUTCOMES,
    AUTH,
    FEEDBACK,
    REQUESTS,
    rate_limited,
    services,
)
from reglens.qa import AskRequest
from reglens.store.db import Feedback, session_scope

router = APIRouter(prefix="/v1", dependencies=AUTH, tags=["ask"])
Regulator = Literal["RBI", "SEBI", "FCA", "PRA"]


class AskIn(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    as_of: date | None = None
    regulators: list[Regulator] = Field(default_factory=list)


class FeedbackIn(BaseModel):
    trace_id: str = Field(min_length=8, max_length=64)
    score: Literal[1, -1]
    comment: str = Field(default="", max_length=2000)


def _outcome(answer: dict[str, Any]) -> str:
    if answer.get("cached"):
        return "cached"
    if answer.get("route") == "refused":
        return "refused"
    return "abstained" if answer.get("abstained") else "answered"


def _sse(events: Iterator[dict[str, Any]]) -> Iterator[str]:
    started = time.perf_counter()
    for event in events:
        if event["type"] == "final":
            ASK_OUTCOMES.labels(_outcome(event["answer"])).inc()
            ASK_LATENCY.observe(time.perf_counter() - started)
        yield f"event: {event['type']}\ndata: {json.dumps(event, default=str)}\n\n"
    yield "event: done\ndata: {}\n\n"


@router.post("/ask", dependencies=[Depends(rate_limited)])
def ask(
    body: AskIn,
    svc: Annotated[Any, Depends(services)],
    stream: Annotated[bool, Query()] = True,
) -> Any:
    """Answer a question with paragraph-level citations, as of a date (default: today)."""
    REQUESTS.labels("ask").inc()
    request = AskRequest(body.question, body.as_of, tuple(body.regulators))
    if stream:
        return StreamingResponse(
            _sse(svc.qa.ask_stream(request)),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
    started = time.perf_counter()
    answer = svc.qa.ask(request)
    ASK_OUTCOMES.labels(_outcome(answer)).inc()
    ASK_LATENCY.observe(time.perf_counter() - started)
    return answer


@router.post("/feedback", status_code=201)
def feedback(body: FeedbackIn, svc: Annotated[Any, Depends(services)]) -> dict[str, str]:
    """Thumbs up/down on an answer: stored, counted, and sent to Langfuse as a score."""
    REQUESTS.labels("feedback").inc()
    FEEDBACK.labels("up" if body.score > 0 else "down").inc()
    with session_scope(svc.engine) as session:
        session.add(Feedback(trace_id=body.trace_id, score=body.score, comment=body.comment))
    svc.tracer.score(body.trace_id, "user_feedback", float(body.score), body.comment)
    return {"status": "recorded"}
