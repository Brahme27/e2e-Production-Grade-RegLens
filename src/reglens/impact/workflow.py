"""Change-impact workflow (LangGraph): new rule in, reviewed gap analysis and tickets out.

    load_target ─▶ applicability ─▶ extract_obligations ─▶ judge_gaps ─▶ human_review ─▶ tickets
                         │ not applicable                                  (pauses here)
                         └──────────────▶ END

``human_review`` calls ``interrupt()``: the graph stops, its state is saved by the
checkpointer, and the API returns the draft to a person. When the reviewer approves (with any
overrides), the graph resumes from exactly that point and creates tickets. Nothing is
"actioned" without a human decision.
"""

from __future__ import annotations

import csv
import json
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, TypedDict

import yaml
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from reglens.impact.diff import diff_versions
from reglens.impact.obligations import Obligation, extract_obligations, judge_gap, to_dict
from reglens.impact.policies import PolicySearch
from reglens.llm.client import LLMClient
from reglens.parse.model import ParsedDocument

SEVERITY_DAYS = {"high": 30, "medium": 60, "low": 90}


@dataclass(frozen=True)
class Entity:
    id: str
    name: str
    applies_to: tuple[str, ...]
    jurisdiction: str = ""


def load_entities(path: Path) -> dict[str, Entity]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        e["id"]: Entity(e["id"], e["name"], tuple(e["applies_to"]), e.get("jurisdiction", ""))
        for e in raw["entities"]
    }


class ImpactState(TypedDict, total=False):
    run_id: str
    doc_key: str
    entity: str
    refs: list[str]  # optional: only these paragraphs
    previous_key: str | None
    paragraphs: list[dict[str, Any]]
    applicable: bool
    obligations: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    decisions: dict[str, Any]
    tickets: list[dict[str, Any]]
    status: str


class ImpactWorkflow:
    def __init__(
        self,
        documents: dict[str, ParsedDocument],
        entities: dict[str, Entity],
        policy_search: PolicySearch,
        llm: LLMClient,
        tickets_dir: Path,
        *,
        today: date | None = None,
    ) -> None:
        self.documents = documents
        self.entities = entities
        self.policy_search = policy_search
        self.llm = llm
        self.tickets_dir = tickets_dir
        self.today = today or date.today()
        self.graph = self._build().compile(checkpointer=InMemorySaver())

    # ---------------------------------------------------------------- nodes
    def load_target(self, state: ImpactState) -> ImpactState:
        doc = self.documents[state["doc_key"]]
        older = [
            d
            for d in self.documents.values()
            if d.doc_id == doc.doc_id
            and d.key != doc.key
            and (d.effective_from or date.min) < (doc.effective_from or date.min)
        ]
        previous = max(older, key=lambda d: d.effective_from or date.min) if older else None
        if state.get("refs"):
            wanted = set(state["refs"])
            paragraphs = [p for p in doc.paragraphs if p.ref in wanted]
        elif previous is not None:  # a new version: only what substantively changed
            changed = {
                c.ref.split(" → ")[-1]
                for c in diff_versions(previous, doc)
                if c.substantive and c.kind != "removed"
            }
            paragraphs = [p for p in doc.paragraphs if p.ref in changed]
        else:
            paragraphs = list(doc.paragraphs)
        return {
            "previous_key": previous.key if previous else None,
            "paragraphs": [
                {"ref": p.ref, "text": p.text, "section_path": list(p.section_path)}
                for p in paragraphs
            ],
            "status": "loaded",
        }

    def applicability(self, state: ImpactState) -> ImpactState:
        doc = self.documents[state["doc_key"]]
        entity = self.entities[state["entity"]]
        applicable = bool(set(doc.applies_to) & set(entity.applies_to))
        return {
            "applicable": applicable,
            "status": "applicable" if applicable else "not_applicable",
        }

    def extract(self, state: ImpactState) -> ImpactState:
        from reglens.parse.model import Paragraph  # noqa: PLC0415

        paragraphs = [
            Paragraph(p["ref"], p["text"], tuple(p["section_path"])) for p in state["paragraphs"]
        ]
        obligations = extract_obligations(state["doc_key"], paragraphs, self.llm)
        return {"obligations": [to_dict(o) for o in obligations], "status": "extracted"}

    def judge(self, state: ImpactState) -> ImpactState:
        gaps = []
        for raw in state["obligations"]:
            obligation = Obligation(**raw)
            hits = self.policy_search.search(obligation.text, state["entity"])
            gaps.append(to_dict(judge_gap(obligation, hits, self.llm)))
        return {"gaps": gaps, "status": "awaiting_review"}

    def review(self, state: ImpactState) -> ImpactState:
        decision = interrupt(
            {"run_id": state["run_id"], "obligations": state["obligations"], "gaps": state["gaps"]}
        )
        overrides: dict[str, Any] = (
            decision.get("overrides", {}) if isinstance(decision, dict) else {}
        )
        gaps = []
        for draft in state["gaps"]:
            override = overrides.get(draft["obligation_id"])
            if override:
                gap = {
                    **draft,
                    "status": override.get("status", draft["status"]),
                    "reviewer_note": override.get("note", ""),
                    "reviewed": True,
                }
            else:
                gap = {**draft, "reviewed": True}
            gaps.append(gap)
        return {
            "gaps": gaps,
            "decisions": decision if isinstance(decision, dict) else {},
            "status": "reviewed",
        }

    def tickets(self, state: ImpactState) -> ImpactState:
        by_id = {o["id"]: o for o in state["obligations"]}
        doc = self.documents[state["doc_key"]]
        tickets: list[dict[str, Any]] = []
        for gap in state["gaps"]:
            if gap["status"] == "covered":
                continue
            obligation = by_id[gap["obligation_id"]]
            severity = obligation.get("severity", "medium")
            tickets.append(
                {
                    "ticket": f"RL-{state['run_id'][:6].upper()}-{len(tickets) + 1:03d}",
                    "title": f"[{doc.regulator}] Update policy for {doc.doc_number or doc.title} §{obligation['source_ref']}",
                    "obligation": obligation["text"],
                    "gap": gap["status"],
                    "rationale": gap["rationale"],
                    "policy_refs": ", ".join(gap.get("policy_refs") or gap.get("evidence") or []),
                    "priority": severity,
                    "due": (
                        self.today + timedelta(days=SEVERITY_DAYS.get(severity, 60))
                    ).isoformat(),
                    "entity": state["entity"],
                }
            )
        self._write(state["run_id"], tickets)
        return {"tickets": tickets, "status": "tickets_created"}

    def _write(self, run_id: str, tickets: list[dict[str, Any]]) -> None:
        self.tickets_dir.mkdir(parents=True, exist_ok=True)
        (self.tickets_dir / f"{run_id}.json").write_text(
            json.dumps(tickets, indent=1), encoding="utf-8"
        )
        with (self.tickets_dir / f"{run_id}.csv").open("w", newline="", encoding="utf-8") as handle:
            fields = [
                "ticket",
                "title",
                "obligation",
                "gap",
                "rationale",
                "policy_refs",
                "priority",
                "due",
                "entity",
            ]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(tickets)

    # ---------------------------------------------------------------- graph
    def _build(self) -> StateGraph[ImpactState]:
        graph = StateGraph(ImpactState)
        graph.add_node("load_target", self.load_target)
        graph.add_node("applicability", self.applicability)
        graph.add_node("extract_obligations", self.extract)
        graph.add_node("judge_gaps", self.judge)
        graph.add_node("human_review", self.review)
        graph.add_node("create_tickets", self.tickets)
        graph.add_edge(START, "load_target")
        graph.add_edge("load_target", "applicability")
        graph.add_conditional_edges(
            "applicability", lambda s: "extract_obligations" if s["applicable"] else END
        )
        graph.add_edge("extract_obligations", "judge_gaps")
        graph.add_edge("judge_gaps", "human_review")
        graph.add_edge("human_review", "create_tickets")
        graph.add_edge("create_tickets", END)
        return graph

    def start(self, doc_key: str, entity: str, refs: list[str] | None = None) -> ImpactState:
        if doc_key not in self.documents:
            raise KeyError(doc_key)
        if entity not in self.entities:
            raise KeyError(entity)
        run_id = uuid.uuid4().hex
        state: ImpactState = {
            "run_id": run_id,
            "doc_key": doc_key,
            "entity": entity,
            "refs": refs or [],
        }
        self.graph.invoke(state, {"configurable": {"thread_id": run_id}})
        return self.state(run_id)

    def resume(self, run_id: str, overrides: dict[str, Any] | None = None) -> ImpactState:
        config = {"configurable": {"thread_id": run_id}}
        self.graph.invoke(Command(resume={"approved": True, "overrides": overrides or {}}), config)  # type: ignore[call-overload]
        return self.state(run_id)

    def state(self, run_id: str) -> ImpactState:
        snapshot = self.graph.get_state({"configurable": {"thread_id": run_id}})
        values: ImpactState = dict(snapshot.values)  # type: ignore[assignment]
        if snapshot.next:  # paused (at human_review)
            values["status"] = "awaiting_review"
        return values
