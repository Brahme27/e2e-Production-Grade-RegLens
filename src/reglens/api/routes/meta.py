"""Corpus overview, firms (entities) and evaluation reports for the console."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from reglens.api.deps import AUTH, services
from reglens.impact.workflow import load_entities
from reglens.store.db import DocumentVersion, SupersessionEdge, session_scope

router = APIRouter(prefix="/v1", dependencies=AUTH, tags=["meta"])
REPORTS = frozenset(
    {"ablation", "generation_eval", "impact_eval", "supersession_eval", "router_eval", "abstention"}
)


@router.get("/meta")
def meta(svc: Annotated[Any, Depends(services)]) -> dict[str, Any]:
    """What is indexed: documents and versions per regulator and status."""
    with session_scope(svc.engine) as session:
        rows = session.execute(
            select(DocumentVersion.regulator, DocumentVersion.status, func.count()).group_by(
                DocumentVersion.regulator, DocumentVersion.status
            )
        ).all()
        documents = session.scalar(select(func.count(func.distinct(DocumentVersion.doc_id))))
        edges = session.scalar(select(func.count()).select_from(SupersessionEdge))
    by_regulator: dict[str, dict[str, int]] = {}
    for regulator, status, count in rows:
        by_regulator.setdefault(regulator, {})[status] = count
    return {
        "documents": documents,
        "versions": sum(sum(v.values()) for v in by_regulator.values()),
        "by_regulator": by_regulator,
        "supersession_edges": edges,
        "serving_variant": svc.settings.serving_variant,
    }


@router.get("/entities")
def entities(svc: Annotated[Any, Depends(services)]) -> list[dict[str, Any]]:
    """The firms whose policies can be checked for gaps."""
    loaded = load_entities(svc.settings.configs_dir / "entities.yaml")
    return [
        {
            "id": e.id,
            "name": e.name,
            "jurisdiction": e.jurisdiction,
            "applies_to": list(e.applies_to),
        }
        for e in loaded.values()
    ]


@router.get("/reports/{name}")
def report(name: str, svc: Annotated[Any, Depends(services)]) -> Any:
    """Evaluation reports (allow-listed names only: no path tricks)."""
    if name not in REPORTS:
        raise HTTPException(status_code=404, detail="unknown report")
    path = svc.settings.reports_dir / f"{name}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="report not generated yet")
    return json.loads(path.read_text(encoding="utf-8"))
