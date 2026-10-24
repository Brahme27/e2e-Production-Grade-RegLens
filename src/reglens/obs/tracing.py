"""Request tracing: one trace per question, one span per pipeline step.

Traces always go to ``artifacts/traces.jsonl`` (searchable locally) and, when keys are set,
to **Langfuse** through its public ingestion API, so you get the trace tree, latency per
step, token counts and user feedback scores in the Langfuse UI. Sending happens in a
background thread and never slows or breaks a request.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from reglens.log import get_logger

log = get_logger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class Span:
    name: str
    start: str
    end: str = ""
    duration_ms: float = 0.0
    input: Any = None
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
    kind: str = "span"  # span | generation
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


@dataclass
class Trace:
    name: str
    input: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    start: str = field(default_factory=_now)
    output: Any = None
    spans: list[Span] = field(default_factory=list)

    @contextmanager
    def span(self, name: str, input: Any = None, kind: str = "span") -> Iterator[Span]:
        span = Span(name=name, start=_now(), input=input, kind=kind)
        started = time.perf_counter()
        try:
            yield span
        finally:
            span.duration_ms = round((time.perf_counter() - started) * 1000, 1)
            span.end = _now()
            self.spans.append(span)

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "start": self.start,
            "input": self.input,
            "output": self.output,
            "metadata": self.metadata,
            "spans": [s.__dict__ for s in self.spans],
        }


class LangfuseExporter:
    """Minimal client for Langfuse's batch ingestion endpoint (no SDK dependency)."""

    def __init__(
        self,
        host: str,
        public_key: str,
        secret_key: str,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=host.rstrip("/"),
            auth=(public_key, secret_key),
            timeout=10,
            transport=transport,
        )

    @staticmethod
    def events(trace: Trace) -> list[dict[str, Any]]:
        batch: list[dict[str, Any]] = [
            {
                "id": uuid.uuid4().hex,
                "type": "trace-create",
                "timestamp": trace.start,
                "body": {
                    "id": trace.id,
                    "name": trace.name,
                    "input": trace.input,
                    "output": trace.output,
                    "metadata": trace.metadata,
                    "timestamp": trace.start,
                },
            }
        ]
        for span in trace.spans:
            body: dict[str, Any] = {
                "id": span.id,
                "traceId": trace.id,
                "name": span.name,
                "startTime": span.start,
                "endTime": span.end,
                "input": span.input,
                "output": span.output,
                "metadata": span.metadata,
            }
            if span.kind == "generation":
                body["model"] = span.metadata.get("model")
                body["usage"] = {
                    "input": span.metadata.get("prompt_tokens", 0),
                    "output": span.metadata.get("completion_tokens", 0),
                }
            batch.append(
                {
                    "id": uuid.uuid4().hex,
                    "type": f"{span.kind}-create",
                    "timestamp": span.start,
                    "body": body,
                }
            )
        return batch

    def send(self, batch: list[dict[str, Any]]) -> None:
        response = self._client.post("/api/public/ingestion", json={"batch": batch})
        if response.status_code >= 400:  # noqa: PLR2004
            log.warning("langfuse_rejected", status=response.status_code, body=response.text[:200])

    def score(self, trace_id: str, name: str, value: float, comment: str = "") -> None:
        self.send(
            [
                {
                    "id": uuid.uuid4().hex,
                    "type": "score-create",
                    "timestamp": _now(),
                    "body": {
                        "id": uuid.uuid4().hex,
                        "traceId": trace_id,
                        "name": name,
                        "value": value,
                        "comment": comment,
                    },
                }
            ]
        )


class Tracer:
    def __init__(
        self, path: Path | None, exporter: LangfuseExporter | None = None, background: bool = True
    ) -> None:
        self.path = path
        self.exporter = exporter
        self.background = background
        self._lock = threading.Lock()

    def start(self, name: str, input: Any, **metadata: Any) -> Trace:
        return Trace(name=name, input=input, metadata=metadata)

    def _export(self, trace: Trace) -> None:
        if self.exporter is None:
            return
        try:
            self.exporter.send(LangfuseExporter.events(trace))
        except httpx.HTTPError as exc:  # observability must never break the product
            log.warning("langfuse_unreachable", error=str(exc))

    def finish(self, trace: Trace, output: Any = None) -> None:
        trace.output = output
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self._lock, self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(trace.to_json(), default=str, ensure_ascii=False) + "\n")
        if self.background:
            threading.Thread(target=self._export, args=(trace,), daemon=True).start()
        else:
            self._export(trace)

    def score(self, trace_id: str, name: str, value: float, comment: str = "") -> None:
        if self.exporter is None:
            return
        try:
            self.exporter.score(trace_id, name, value, comment)
        except httpx.HTTPError as exc:
            log.warning("langfuse_unreachable", error=str(exc))


def build_tracer(settings: Any) -> Tracer:
    exporter = None
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        exporter = LangfuseExporter(
            settings.langfuse_host,
            settings.langfuse_public_key.get_secret_value(),
            settings.langfuse_secret_key.get_secret_value(),
        )
    return Tracer(settings.artifacts_dir / "traces.jsonl", exporter)
