"""Change-impact endpoints: start a run, review gap judgements, approve, download tickets."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from reglens.api.deps import AUTH, REQUESTS, services
from reglens.store.db import GapJudgement, Obligation, session_scope

router = APIRouter(prefix="/v1", dependencies=AUTH, tags=["impact"])
GapStatus = Literal["covered", "partially_covered", "not_covered"]


class ImpactIn(BaseModel):
    doc_key: str = Field(examples=["rbi-cb-internal-ombudsman-2026@current"])
    entity: str = Field(examples=["sahyadri-bank"])
    refs: list[str] = Field(default_factory=list, description="optional: only these paragraphs")


class GapPatch(BaseModel):
    review_status: Literal["approved", "overridden"]
    status: GapStatus | None = None
    note: str = Field(default="", max_length=2000)


def _save(engine: Any, state: dict[str, Any]) -> None:
    gaps = {g["obligation_id"]: g for g in state.get("gaps", [])}
    with session_scope(engine) as session:
        for o in state.get("obligations", []):
            session.merge(
                Obligation(
                    id=o["id"],
                    impact_run=state["run_id"],
                    doc_key=state["doc_key"],
                    source_ref=o["source_ref"],
                    text=o["text"],
                    actor=o["actor"],
                    action=o["action"],
                    condition=o["condition"],
                    deadline=o["deadline"],
                    severity=o["severity"],
                )
            )
            gap = gaps.get(o["id"])
            if gap:
                session.add(
                    GapJudgement(
                        obligation_id=o["id"],
                        entity=state["entity"],
                        status=gap["status"],
                        rationale=gap["rationale"],
                        policy_refs=list(gap.get("policy_refs") or []),
                        confidence=gap.get("confidence", 0.0),
                    )
                )


def _rows(
    engine: Any, run_id: str | None = None, entity: str | None = None
) -> list[dict[str, Any]]:
    with session_scope(engine) as session:
        query = select(Obligation, GapJudgement).join(
            GapJudgement, GapJudgement.obligation_id == Obligation.id
        )
        if run_id:
            query = query.where(Obligation.impact_run == run_id)
        if entity:
            query = query.where(GapJudgement.entity == entity)
        return [
            {
                "obligation_id": o.id,
                "run_id": o.impact_run,
                "doc_key": o.doc_key,
                "source_ref": o.source_ref,
                "text": o.text,
                "deadline": o.deadline,
                "severity": o.severity,
                "gap_id": g.id,
                "entity": g.entity,
                "status": g.status,
                "rationale": g.rationale,
                "policy_refs": g.policy_refs,
                "confidence": g.confidence,
                "review_status": g.review_status,
                "reviewer_note": g.reviewer_note,
            }
            for o, g in session.execute(query)
        ]


@router.post("/impact", status_code=201)
def start_impact(body: ImpactIn, svc: Annotated[Any, Depends(services)]) -> dict[str, Any]:
    """Run the change-impact workflow up to human review."""
    REQUESTS.labels("impact").inc()
    try:
        state = svc.impact.start(body.doc_key, body.entity, body.refs or None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown {exc}") from exc
    _save(svc.engine, state)
    return state  # type: ignore[no-any-return]


@router.get("/impact/{run_id}")
def get_impact(run_id: str, svc: Annotated[Any, Depends(services)]) -> dict[str, Any]:
    state = svc.impact.state(run_id)
    if not state:
        raise HTTPException(status_code=404, detail="unknown run")
    return state  # type: ignore[no-any-return]


@router.get("/obligations")
def obligations(
    svc: Annotated[Any, Depends(services)], run_id: str | None = None, entity: str | None = None
) -> list[dict[str, Any]]:
    """The obligation register with gap status and review state."""
    return _rows(svc.engine, run_id, entity)


@router.patch("/gaps/{gap_id}")
def review_gap(
    gap_id: int, body: GapPatch, svc: Annotated[Any, Depends(services)]
) -> dict[str, Any]:
    """A reviewer approves a judgement or overrides its status (with a note)."""
    with session_scope(svc.engine) as session:
        gap = session.get(GapJudgement, gap_id)
        if gap is None:
            raise HTTPException(status_code=404, detail="unknown gap")
        gap.review_status = body.review_status
        gap.reviewer_note = body.note
        if body.review_status == "overridden":
            if body.status is None:
                raise HTTPException(status_code=422, detail="an override needs a status")
            gap.status = body.status
        return {"gap_id": gap.id, "status": gap.status, "review_status": gap.review_status}


@router.post("/impact/{run_id}/approve")
def approve(run_id: str, svc: Annotated[Any, Depends(services)]) -> dict[str, Any]:
    """Resume the paused workflow with the reviewers' decisions and create tickets."""
    state = svc.impact.state(run_id)
    if state.get("status") != "awaiting_review":
        raise HTTPException(status_code=409, detail="run is not awaiting review")
    overrides = {
        row["obligation_id"]: {"status": row["status"], "note": row["reviewer_note"]}
        for row in _rows(svc.engine, run_id)
        if row["review_status"] == "overridden"
    }
    return svc.impact.resume(run_id, overrides)  # type: ignore[no-any-return]


@router.get("/impact/{run_id}/tickets.csv")
def tickets_csv(run_id: str, svc: Annotated[Any, Depends(services)]) -> FileResponse:
    if not run_id.isalnum():  # run ids are hex: never let a path through
        raise HTTPException(status_code=404, detail="unknown run")
    path = svc.settings.artifacts_dir / "tickets" / f"{run_id}.csv"
    if not path.exists():
        raise HTTPException(status_code=404, detail="no tickets for this run yet")
    return FileResponse(path, media_type="text/csv", filename=f"reglens-tickets-{run_id[:8]}.csv")
