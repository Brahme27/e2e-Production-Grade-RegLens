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
    report = [{"key": "F", "overall": BASE}]
    (settings.reports_dir / "ablation.json").write_text(json.dumps(report))
    monkeypatch.setattr(gate, "get_settings", lambda: settings)
    assert gate.main([]) == 0  # no baseline yet: written
    assert json.loads((settings.evals_dir / "baseline.json").read_text())["row"] == "F"
    assert gate.main([]) == 0
    worse = [{"key": "F", "overall": {**BASE, "recall@10": 0.70}}]
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


def test_results_markdown_from_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from reglens import results  # noqa: PLC0415

    settings = Settings(
        artifacts_dir=tmp_path / "art", data_dir=tmp_path / "data", evals_dir=tmp_path / "evals"
    )
    reports = settings.reports_dir
    reports.mkdir(parents=True)
    overall = {**BASE, "recall@5": 0.8, "temporal_precision": 1.0}
    row = {
        "key": "G",
        "label": "prod",
        "overall": overall,
        "latency_ms": {"p50": 1, "p95": 3149},
        "by_category": {"lookup": overall},
    }
    (reports / "ablation.json").write_text(json.dumps([row]))
    summary = {"faithfulness": 0.9, "citation_precision": 0.85, "n": 60, "latency_p95_ms": 4000}
    (reports / "generation_eval.json").write_text(json.dumps({"final": {"summary": summary}}))
    (reports / "abstention.json").write_text(
        json.dumps({"threshold": -2.1, "balanced_accuracy": 0.9, "n": 139})
    )
    scores = {"precision": 1.0, "recall": 0.9, "f1": 0.95}
    (reports / "supersession_eval.json").write_text(
        json.dumps(
            {
                "gold_edges": 57,
                "rules": scores,
                "rules_plus_llm": scores,
                "rules_internal": scores,
                "rules_plus_llm_internal": scores,
            }
        )
    )
    (reports / "router_eval.json").write_text(
        json.dumps({"golden_accuracy": 0.903, "golden_n": 175})
    )
    confusion = {
        g: {"covered": 1, "partially_covered": 0, "not_covered": 0}
        for g in ("covered", "partially_covered", "not_covered")
    }
    (reports / "impact_eval.json").write_text(
        json.dumps(
            {
                "extraction": scores,
                "gaps": {
                    "n": 41,
                    "accuracy": 0.8,
                    "gap_detection_accuracy": 0.9,
                    "cohen_kappa": 0.7,
                    "confusion": confusion,
                },
            }
        )
    )
    (settings.artifacts_dir / "llm-usage.jsonl").write_text(
        json.dumps({"purpose": "answer", "prompt_tokens": 10, "completion_tokens": 2}) + "\n"
    )
    monkeypatch.setattr(results, "get_settings", lambda: settings)
    results.main()
    text = (tmp_path / "docs" / "RESULTS.md").read_text(encoding="utf-8")
    assert "| G | prod | 0.870" in text and "3,149 ms" in text
    assert "Faithfulness" in text and "Cohen's κ" in text and "| **total** | **1** |" in text
