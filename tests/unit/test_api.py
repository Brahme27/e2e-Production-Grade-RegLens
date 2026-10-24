"""API: auth, rate limiting, ask (SSE + JSON), feedback, documents, diff, graph, changes."""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from reglens.api.app import create_app
from reglens.api.deps import RateLimiter, client_id
from reglens.config import Settings
from reglens.obs.tracing import Tracer
from reglens.parse.model import Paragraph, ParsedDocument
from reglens.qa import AskRequest
from reglens.services import Services
from reglens.temporal.run import build_temporal, save_temporal

KEY = {"X-API-Key": "k"}


def _doc(
    doc_id: str, version: str, effective: date, texts: dict[str, str], title: str
) -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        version=version,
        regulator="PRA",
        doc_type="rulebook_part",
        title=title,
        url="u",
        topics=["outsourcing"],
        applies_to=["uk_banks"],
        effective_from=effective,
        paragraphs=[Paragraph(ref, text) for ref, text in texts.items()],
    )


OLD = _doc(
    "pra-out",
    "asof2025",
    date(2020, 12, 31),
    {"2.1": "A firm must avoid undue operational risk.", "2.2": "Old rule to be deleted."},
    "Outsourcing",
)
NEW = _doc(
    "pra-out",
    "asof2026",
    date(2025, 10, 23),
    {"2.1": "A firm must avoid undue additional operational risk.", "2.3": "A brand new rule."},
    "Outsourcing",
)
REPEALER = _doc(
    "pra-new",
    "current",
    date(2026, 1, 1),
    {"1": "1. This part repeals the Master Circular on outsourcing of payments."},
    "New Part",
)


class FakeQA:
    def __init__(self) -> None:
        self.requests: list[AskRequest] = []

    def ask_stream(self, request: AskRequest) -> Iterator[dict[str, Any]]:
        self.requests.append(request)
        yield {"type": "meta", "trace_id": "trace-123456"}
        yield {"type": "delta", "text": "A firm must avoid undue risk [1]."}
        yield {
            "type": "final",
            "answer": {
                "text": "A firm must avoid undue risk [1].",
                "abstained": False,
                "route": "lookup",
                "cached": False,
            },
        }

    def ask(self, request: AskRequest) -> dict[str, Any]:
        return next(e for e in self.ask_stream(request) if e["type"] == "final")["answer"]


@pytest.fixture
def client(tmp_path: Path) -> Iterator[tuple[TestClient, FakeQA]]:
    settings = Settings(
        api_key="k",
        data_dir=tmp_path / "data",
        artifacts_dir=tmp_path / "art",
        rate_limit_per_minute=1000,
    )
    settings.artifacts_dir.mkdir()
    documents = [OLD, NEW, REPEALER]
    _, edges, validity = build_temporal(documents, None, date(2026, 10, 24))
    save_temporal(documents, edges, validity, settings)
    services = Services(settings)
    qa = FakeQA()
    services.override("qa", qa)
    services.override("documents", {d.key: d for d in documents})
    services.override("tracer", Tracer(tmp_path / "traces.jsonl"))
    with TestClient(create_app(settings, services)) as c:
        yield c, qa


def test_ops_and_auth(client: tuple[TestClient, FakeQA]) -> None:
    c, _ = client
    assert c.get("/health").json() == {"status": "ok"}
    assert c.get("/ready").json()["status"] == "ready"
    assert c.get("/v1/documents").status_code == 401
    assert c.get("/v1/documents", headers={"X-API-Key": "wrong"}).status_code == 401
    assert c.get("/v1/documents", headers=KEY).status_code == 200


def test_ask_streams_server_sent_events(client: tuple[TestClient, FakeQA]) -> None:
    c, qa = client
    with c.stream(
        "POST",
        "/v1/ask",
        json={"question": "What must firms do?", "as_of": "2024-03-01", "regulators": ["PRA"]},
        headers=KEY,
    ) as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        body = "".join(response.iter_text())
    events = [
        line.removeprefix("event: ") for line in body.splitlines() if line.startswith("event: ")
    ]
    assert events == ["meta", "delta", "final", "done"]
    assert qa.requests[0] == AskRequest("What must firms do?", date(2024, 3, 1), ("PRA",))
    assert "reglens_ask_outcomes_total" in c.get("/metrics").text


def test_ask_json_and_validation(client: tuple[TestClient, FakeQA]) -> None:
    c, _ = client
    answer = c.post(
        "/v1/ask?stream=false", json={"question": "What must firms do?"}, headers=KEY
    ).json()
    assert answer["route"] == "lookup"
    assert c.post("/v1/ask", json={"question": "x"}, headers=KEY).status_code == 422
    assert (
        c.post(
            "/v1/ask", json={"question": "valid?", "regulators": ["ECB"]}, headers=KEY
        ).status_code
        == 422
    )


def test_rate_limit(client: tuple[TestClient, FakeQA]) -> None:
    c, _ = client
    c.app.state.rate_limiter = RateLimiter(per_minute=2)  # type: ignore[attr-defined]
    codes = [
        c.post(
            "/v1/ask?stream=false", json={"question": "What must firms do?"}, headers=KEY
        ).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]
    other = {**KEY, "X-Forwarded-For": "203.0.113.9"}  # same key, different person: own bucket
    assert (
        c.post("/v1/ask?stream=false", json={"question": "What must firms do?"}, headers=other)
    ).status_code == 200
    c.app.state.rate_limiter = RateLimiter(per_minute=1)  # type: ignore[attr-defined]
    feedback = {"trace_id": "trace-123456", "score": 1}
    assert c.post("/v1/feedback", json=feedback, headers=KEY).status_code == 201
    assert c.post("/v1/feedback", json=feedback, headers=KEY).status_code == 429


def test_client_id_trusts_only_the_nearest_proxy() -> None:
    from starlette.requests import Request  # noqa: PLC0415

    def request(forwarded: str | None) -> Request:
        headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
        return Request({"type": "http", "headers": headers, "client": ("10.0.0.5", 1234)})

    assert client_id(request("1.1.1.1, 198.51.100.7")) == "198.51.100.7"  # spoofed hop ignored
    assert client_id(request(None)) == "10.0.0.5"


def test_rate_limiter_forgets_idle_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("reglens.api.deps.MAX_TRACKED_CLIENTS", 4)
    limiter = RateLimiter(per_minute=10)
    for i in range(5):
        assert limiter.allow(f"client-{i}")
    assert len(limiter._buckets) <= 4 and "client-4" in limiter._buckets


def test_feedback_is_stored(client: tuple[TestClient, FakeQA]) -> None:
    c, _ = client
    assert (
        c.post(
            "/v1/feedback",
            json={"trace_id": "trace-123456", "score": 1, "comment": "good"},
            headers=KEY,
        ).status_code
        == 201
    )
    assert (
        c.post(
            "/v1/feedback", json={"trace_id": "trace-123456", "score": 5}, headers=KEY
        ).status_code
        == 422
    )


def test_documents_versions_and_diff(client: tuple[TestClient, FakeQA]) -> None:
    c, _ = client
    listing = c.get("/v1/documents?regulator=pra", headers=KEY).json()
    assert {v["key"] for v in listing} == {
        "pra-out@asof2025",
        "pra-out@asof2026",
        "pra-new@current",
    }
    superseded = c.get("/v1/documents?status=superseded", headers=KEY).json()
    assert [v["key"] for v in superseded] == ["pra-out@asof2025"]
    doc = c.get("/v1/documents/pra-out", headers=KEY).json()
    assert [v["version"] for v in doc["versions"]] == ["asof2025", "asof2026"]
    assert c.get("/v1/documents/nope", headers=KEY).status_code == 404
    text = c.get("/v1/documents/pra-out/versions/asof2026", headers=KEY).json()
    assert text["paragraphs"][0]["ref"] == "2.1"
    assert c.get("/v1/documents/pra-out/versions/x", headers=KEY).status_code == 404
    diff = c.get("/v1/documents/pra-out/diff?from=asof2025&to=asof2026", headers=KEY).json()
    assert (
        diff["summary"]["changed"] == 1
        and diff["summary"]["added"] == 1
        and diff["summary"]["removed"] == 1
    )
    assert "{+additional+}" in next(ch for ch in diff["changes"] if ch["ref"] == "2.1")["word_diff"]
    assert c.get("/v1/documents/pra-out/diff?from=asof2025&to=zzz", headers=KEY).status_code == 404


def test_graph_and_change_feed(client: tuple[TestClient, FakeQA]) -> None:
    c, _ = client
    graph = c.get("/v1/graph/supersession", headers=KEY).json()
    assert isinstance(graph["nodes"], list) and isinstance(graph["edges"], list)
    feed = c.get("/v1/changes?since=2025-01-01", headers=KEY).json()
    assert feed[0]["date"] >= feed[-1]["date"]
    assert {e["event"] for e in feed} >= {"in_force", "superseded"}
    json.dumps(feed)  # serialisable


def test_meta_entities_and_reports(client: tuple[TestClient, FakeQA]) -> None:
    c, _ = client
    meta = c.get("/v1/meta", headers=KEY).json()
    assert meta["documents"] == 2 and meta["by_regulator"]["PRA"]["current"] == 2
    assert {e["id"] for e in c.get("/v1/entities", headers=KEY).json()} == {
        "sahyadri-bank",
        "northbridge-bank",
    }
    assert c.get("/v1/reports/../../etc", headers=KEY).status_code == 404
    assert (
        c.get("/v1/reports/ablation", headers=KEY).status_code == 404
    )  # not generated in this temp dir
    reports = c.app.state.settings.reports_dir  # type: ignore[attr-defined]
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "ablation.json").write_text('[{"key": "A"}]')
    assert c.get("/v1/reports/ablation", headers=KEY).json() == [{"key": "A"}]
