"""Change impact: policies, obligation extraction, gap judge, LangGraph workflow with review."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from qdrant_client import QdrantClient

from reglens.config import PROJECT_ROOT
from reglens.impact.obligations import Obligation, extract_obligations, judge_gap
from reglens.impact.policies import (
    PolicySearch,
    clause_chunk,
    index_policies,
    load_policies,
    parse_policy,
)
from reglens.impact.workflow import ImpactWorkflow, csv_safe, load_entities
from reglens.index.store import Hit, VectorStore
from reglens.llm.client import LLMClient, LLMResponse
from reglens.parse.model import Paragraph, ParsedDocument
from tests.fakes import FakeEmbedder, FakeReranker, make_chunk

POLICIES = PROJECT_ROOT / "data" / "policies"


def test_parse_real_policies() -> None:
    clauses = parse_policy(
        POLICIES / "sahyadri-bank" / "grievance-and-internal-ombudsman-policy.md"
    )
    by_number = {c.clause: c for c in clauses}
    assert by_number["5.3"].text.startswith("The CMS shall automatically escalate")
    assert "25 days" in by_number["5.3"].text  # wrapped lines are joined
    assert by_number["5.3"].section == "5. Handling and escalation of complaints"
    assert by_number["5.3"].label == "SB-POL-CS-007 §5.3"
    assert {c.entity for c in load_policies(POLICIES)} == {"sahyadri-bank", "northbridge-bank"}
    assert {c.entity for c in load_policies(POLICIES, "northbridge-bank")} == {"northbridge-bank"}
    chunk = clause_chunk(clauses[0])
    assert chunk.applies_to == ("sahyadri-bank",) and chunk.regulator == "INTERNAL"


class Scripted:
    """Answers by prompt type: obligation extraction or gap judgement."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(
        self, alias: str, messages: list[dict[str, str]], *, json_mode: bool, max_tokens: int
    ) -> LLMResponse:
        system = messages[0]["content"]
        if "extract regulatory obligations" in system:
            self.calls.append("extract")
            return LLMResponse(
                json.dumps(
                    {
                        "obligations": [
                            {
                                "text": "The bank must escalate rejected complaints to the IO within 20 days.",
                                "actor": "bank",
                                "action": "escalate",
                                "deadline": "20 days",
                                "source_ref": "14",
                                "severity": "high",
                            },
                            {
                                "text": "Invented obligation from a paragraph we never gave.",
                                "source_ref": "99",
                            },
                        ]
                    }
                ),
                model="fake",
            )
        self.calls.append("judge")
        return LLMResponse(
            json.dumps(
                {
                    "status": "partially_covered",
                    "rationale": "Policy says 25 days.",
                    "policy_refs": ["SB-POL-CS-007 §5.3", "made-up"],
                    "confidence": 1.7,
                }
            ),
            model="fake",
        )


def _search(entity_clauses: list[str]) -> PolicySearch:
    store = VectorStore(QdrantClient(":memory:"))
    clauses = [c for c in load_policies(POLICIES) if c.entity in entity_clauses]
    index_policies(store, FakeEmbedder(), clauses)  # type: ignore[arg-type]
    return PolicySearch(store, FakeEmbedder(), FakeReranker())  # type: ignore[arg-type]


def test_policy_search_is_filtered_by_entity() -> None:
    search = _search(["sahyadri-bank", "northbridge-bank"])
    hits = search.search(
        "escalate rejected complaints to the internal ombudsman within days", "sahyadri-bank"
    )
    assert hits and {h.chunk.applies_to for h in hits} == {("sahyadri-bank",)}
    assert any(h.chunk.ref == "5.3" for h in hits)


def test_extraction_keeps_only_valid_refs_and_judge_is_sanitised(tmp_path: Path) -> None:
    llm = LLMClient(Scripted(), tmp_path)
    obligations = extract_obligations(
        "rbi-io@current", [Paragraph("14", "14. Procedure ... within 20 days.")], llm
    )
    assert (
        len(obligations) == 2 and obligations[0].source_ref == "14"
    )  # single paragraph: ref repaired
    hit = Hit(
        make_chunk(
            "p", "The CMS shall escalate within 25 days.", doc_id="SB-POL-CS-007", ref="5.3"
        ),
        1.0,
    )
    hit = Hit(hit.chunk.__class__(**{**hit.chunk.__dict__, "doc_number": "SB-POL-CS-007"}), 1.0)
    verdict = judge_gap(Obligation("o1", "escalate within 20 days", "14"), [hit], llm)
    assert verdict.status == "partially_covered"
    assert verdict.policy_refs == ("SB-POL-CS-007 §5.3",)  # refs not shown to the judge are dropped
    assert verdict.confidence == 1.0


def _doc(
    version: str, effective: date, texts: dict[str, str], applies: list[str]
) -> ParsedDocument:
    return ParsedDocument(
        doc_id="rbi-io",
        version=version,
        regulator="RBI",
        doc_type="directions",
        title="IO Directions",
        url="u",
        topics=["grievance_redressal"],
        applies_to=applies,
        doc_number="RBI/IO",
        effective_from=effective,
        paragraphs=[Paragraph(r, t) for r, t in texts.items()],
    )


def test_workflow_pauses_for_review_then_creates_tickets(tmp_path: Path) -> None:
    old = _doc(
        "v1",
        date(2023, 1, 1),
        {"14": "14. Escalate within 30 days.", "15": "15. Unchanged rule text."},
        ["commercial_banks"],
    )
    new = _doc(
        "current",
        date(2026, 1, 14),
        {
            "14": "14. Escalate rejected complaints to the IO within 20 days of receipt.",
            "15": "15. Unchanged rule text.",
        },
        ["commercial_banks"],
    )
    backend = Scripted()
    workflow = ImpactWorkflow(
        {d.key: d for d in (old, new)},
        load_entities(PROJECT_ROOT / "configs" / "entities.yaml"),
        _search(["sahyadri-bank"]),
        LLMClient(backend, tmp_path / "llm"),
        tmp_path / "tickets",
        today=date(2026, 10, 24),
    )
    paused = workflow.start("rbi-io@current", "sahyadri-bank")
    assert paused["status"] == "awaiting_review"
    assert paused["previous_key"] == "rbi-io@v1"
    assert [p["ref"] for p in paused["paragraphs"]] == ["14"]  # only the changed paragraph
    assert len(paused["gaps"]) == len(paused["obligations"]) == 2
    assert "tickets" not in paused  # nothing actioned before a human decides

    first = paused["obligations"][0]["id"]
    done = workflow.resume(
        paused["run_id"], {first: {"status": "covered", "note": "Fixed in v3.3 draft"}}
    )
    assert done["status"] == "tickets_created"
    assert len(done["tickets"]) == 1  # the overridden gap no longer needs a ticket
    assert (tmp_path / "tickets" / f"{paused['run_id']}.csv").exists()
    assert done["tickets"][0]["due"] == "2026-12-23"  # medium severity: 60 days


def test_workflow_stops_when_not_applicable(tmp_path: Path) -> None:
    doc = _doc("current", date(2026, 1, 1), {"1": "1. NBFC rule."}, ["nbfcs"])
    workflow = ImpactWorkflow(
        {doc.key: doc},
        load_entities(PROJECT_ROOT / "configs" / "entities.yaml"),
        _search(["sahyadri-bank"]),
        LLMClient(Scripted(), tmp_path),
        tmp_path / "t",
    )
    state = workflow.start(doc.key, "sahyadri-bank")
    assert state["status"] == "not_applicable" and "obligations" not in state
    with pytest.raises(KeyError):
        workflow.start("missing@x", "sahyadri-bank")
    with pytest.raises(KeyError):
        workflow.start(doc.key, "nobody")


def test_impact_api_review_and_approve(tmp_path: Path) -> None:
    from fastapi.testclient import TestClient  # noqa: PLC0415

    from reglens.api.app import create_app  # noqa: PLC0415
    from reglens.config import Settings  # noqa: PLC0415
    from reglens.services import Services  # noqa: PLC0415

    settings = Settings(api_key="k", artifacts_dir=tmp_path / "art", data_dir=tmp_path / "data")
    settings.artifacts_dir.mkdir()
    old = _doc("v1", date(2023, 1, 1), {"14": "14. Escalate within 30 days."}, ["commercial_banks"])
    new = _doc(
        "current",
        date(2026, 1, 14),
        {"14": "14. Escalate rejected complaints to the IO within 20 days."},
        ["commercial_banks"],
    )
    services = Services(settings)
    workflow = ImpactWorkflow(
        {d.key: d for d in (old, new)},
        load_entities(PROJECT_ROOT / "configs" / "entities.yaml"),
        _search(["sahyadri-bank"]),
        LLMClient(Scripted(), tmp_path / "llm"),
        settings.artifacts_dir / "tickets",
        today=date(2026, 10, 24),
    )
    services.override("impact", workflow)
    key = {"X-API-Key": "k"}
    with TestClient(create_app(settings, services)) as c:
        started = c.post(
            "/v1/impact", json={"doc_key": "rbi-io@current", "entity": "sahyadri-bank"}, headers=key
        )
        assert started.status_code == 201
        run_id = started.json()["run_id"]
        assert (
            c.post(
                "/v1/impact", json={"doc_key": "nope@x", "entity": "sahyadri-bank"}, headers=key
            ).status_code
            == 404
        )
        assert c.get(f"/v1/impact/{run_id}", headers=key).json()["status"] == "awaiting_review"
        rows = c.get(f"/v1/obligations?run_id={run_id}", headers=key).json()
        assert len(rows) == 2 and {r["review_status"] for r in rows} == {"pending"}
        gap_id = rows[0]["gap_id"]
        assert (
            c.patch(
                f"/v1/gaps/{gap_id}", json={"review_status": "overridden"}, headers=key
            ).status_code
            == 422
        )
        patched = c.patch(
            f"/v1/gaps/{gap_id}",
            json={"review_status": "overridden", "status": "covered", "note": "ok"},
            headers=key,
        )
        assert patched.json()["status"] == "covered"
        assert (
            c.patch("/v1/gaps/99999", json={"review_status": "approved"}, headers=key).status_code
            == 404
        )
        assert c.get(f"/v1/impact/{run_id}/tickets.csv", headers=key).status_code == 404
        again = c.post(
            "/v1/impact", json={"doc_key": "rbi-io@current", "entity": "sahyadri-bank"}, headers=key
        )
        assert again.status_code == 201  # same obligations, new run: no id clash
        assert len(c.get("/v1/obligations", headers=key).json()) == 4
        done = c.post(f"/v1/impact/{run_id}/approve", headers=key).json()
        assert done["status"] == "tickets_created" and len(done["tickets"]) == 1
        assert c.post(f"/v1/impact/{run_id}/approve", headers=key).status_code == 409
        late = c.patch(f"/v1/gaps/{gap_id}", json={"review_status": "approved"}, headers=key)
        assert late.status_code == 409  # decisions are frozen once tickets exist
        csv_text = c.get(f"/v1/impact/{run_id}/tickets.csv", headers=key).text
        assert csv_text.startswith("ticket,title,obligation")
        assert c.get("/v1/impact/..%2Fx/tickets.csv", headers=key).status_code == 404


def test_csv_cells_cannot_become_spreadsheet_formulas() -> None:
    assert csv_safe('=HYPERLINK("http://x")') == '\'=HYPERLINK("http://x")'
    assert csv_safe("-1+2") == "'-1+2" and csv_safe("@SUM(A1)") == "'@SUM(A1)"
    assert csv_safe("Escalate within 20 days.") == "Escalate within 20 days."
    assert csv_safe(3) == 3


def test_ticket_due_dates_use_the_day_of_the_run(tmp_path: Path) -> None:
    workflow = ImpactWorkflow(
        {}, {}, _search(["sahyadri-bank"]), LLMClient(Scripted(), tmp_path), tmp_path / "t"
    )
    assert workflow.today() == date.today()
    pinned = ImpactWorkflow(
        {},
        {},
        _search(["sahyadri-bank"]),
        LLMClient(Scripted(), tmp_path),
        tmp_path / "t",
        today=date(2026, 1, 1),
    )
    assert pinned.today() == date(2026, 1, 1)
