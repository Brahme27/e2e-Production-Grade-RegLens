"""CI tools: the retrieval quality gate and the stack smoke test (mocked HTTP)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from reglens import smoke
from reglens.config import Settings
from reglens.evals import gate

BASE = {"recall@10": 0.87, "ndcg@10": 0.77, "mrr": 0.77, "stale_in_top5_rate": 0.0, "n": 145}


def test_compare_allows_noise_but_not_regressions() -> None:
    assert gate.compare({**BASE, "recall@10": 0.85}, BASE) == []
    failures = gate.compare({**BASE, "mrr": 0.70, "stale_in_top5_rate": 0.1}, BASE)
    assert len(failures) == 2 and "mrr" in failures[0]


def test_gate_main_writes_then_checks_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(artifacts_dir=tmp_path / "art", evals_dir=tmp_path / "evals")
    settings.reports_dir.mkdir(parents=True)
    settings.evals_dir.mkdir()
    report = [{"key": "G", "overall": BASE}]
    (settings.reports_dir / "ablation.json").write_text(json.dumps(report))
    monkeypatch.setattr(gate, "get_settings", lambda: settings)
    assert gate.main([]) == 0  # no baseline yet: written
    assert json.loads((settings.evals_dir / "baseline.json").read_text())["row"] == "G"
    assert gate.main([]) == 0
    worse = [{"key": "G", "overall": {**BASE, "recall@10": 0.70}}]
    (settings.reports_dir / "ablation.json").write_text(json.dumps(worse))
    assert gate.main([]) == 1
    with pytest.raises(KeyError):
        gate.row(report, "Z")


def _stack(request: httpx.Request) -> httpx.Response:  # noqa: PLR0911 - a tiny fake server
    path, key = request.url.path, request.headers.get("x-api-key")
    if path == "/health":
        return httpx.Response(200, json={"status": "ok"})
    if path.startswith("/v1/") and key is None and request.url.host == "api":
        return httpx.Response(401)
    if path in ("/v1/meta", "/api/proxy/v1/meta"):
        return httpx.Response(200, json={"documents": 37, "versions": 48})
    if path == "/v1/ask" and request.url.params.get("stream") == "false":
        question = json.loads(request.content)["question"]
        if question.startswith("Ignore"):
            return httpx.Response(
                200, json={"route": "refused", "abstained": True, "citations": []}
            )
        return httpx.Response(
            200, json={"route": "lookup", "abstained": False, "citations": [{"n": 1}]}
        )
    if path == "/v1/ask":
        body = "event: meta\ndata: {}\n\nevent: final\ndata: {}\n\nevent: done\ndata: {}\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    if path.startswith("/v1/documents/"):
        return httpx.Response(200, json={"versions": [{"status": "superseded"}]})
    if path == "/":
        return httpx.Response(200, text="<html></html>")
    return httpx.Response(404)


def test_smoke_checks_pass_against_a_healthy_stack() -> None:
    with httpx.Client(transport=httpx.MockTransport(_stack)) as client:
        results = {name: fn(client) for name, fn in smoke.checks("http://api", "http://web", "k")}
    assert results["corpus loaded"] == "37 documents, 48 versions"
    assert results["question answered with citations"] == "1 citations"
    assert len(results) == 8


def test_smoke_main_reports_failures(capsys: pytest.CaptureFixture[str]) -> None:
    assert smoke.main(["--api", "http://127.0.0.1:9"]) == 1  # nothing listening
    assert "FAIL  api health" in capsys.readouterr().out
