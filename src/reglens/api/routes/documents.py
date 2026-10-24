"""Documents, versions, diffs, the supersession graph and the change feed."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select

from reglens.api.deps import AUTH, REQUESTS, services
from reglens.impact.diff import diff_versions, summarise
from reglens.store.db import DocumentVersion, SupersessionEdge, session_scope

router = APIRouter(prefix="/v1", dependencies=AUTH, tags=["documents"])


def _version(row: DocumentVersion) -> dict[str, Any]:
    return {
        "key": row.key,
        "doc_id": row.doc_id,
        "version": row.version,
        "regulator": row.regulator,
        "doc_type": row.doc_type,
        "title": row.title,
        "doc_number": row.doc_number,
        "url": row.url,
        "topics": row.topics,
        "applies_to": row.applies_to,
        "issue_date": row.issue_date,
        "valid_from": row.valid_from,
        "valid_to": row.valid_to,
        "status": row.status,
        "superseded_by": row.superseded_by,
        "paragraph_count": row.paragraph_count,
    }


@router.get("/documents")
def list_documents(
    svc: Annotated[Any, Depends(services)],
    regulator: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    """Every document version with its validity and status."""
    REQUESTS.labels("documents").inc()
    query = select(DocumentVersion).order_by(
        DocumentVersion.regulator, DocumentVersion.doc_id, DocumentVersion.valid_from
    )
    if regulator:
        query = query.where(DocumentVersion.regulator == regulator.upper())
    if status:
        query = query.where(DocumentVersion.status == status)
    with session_scope(svc.engine) as session:
        return [_version(row) for row in session.scalars(query)]


@router.get("/documents/{doc_id}")
def get_document(doc_id: str, svc: Annotated[Any, Depends(services)]) -> dict[str, Any]:
    """A document's versions (oldest first) and its supersession edges."""
    with session_scope(svc.engine) as session:
        versions = [
            _version(r)
            for r in session.scalars(
                select(DocumentVersion)
                .where(DocumentVersion.doc_id == doc_id)
                .order_by(DocumentVersion.valid_from)
            )
        ]
        if not versions:
            raise HTTPException(status_code=404, detail="unknown document")
        edges = [
            {
                "source": e.source,
                "target": e.target,
                "type": e.type,
                "method": e.method,
                "effective": e.effective,
                "evidence": e.evidence,
            }
            for e in session.scalars(
                select(SupersessionEdge).where(
                    or_(SupersessionEdge.source == doc_id, SupersessionEdge.target == doc_id)
                )
            )
        ]
    return {"doc_id": doc_id, "versions": versions, "edges": edges}


@router.get("/documents/{doc_id}/versions/{version}")
def get_version(
    doc_id: str, version: str, svc: Annotated[Any, Depends(services)]
) -> dict[str, Any]:
    """Full text of one version, paragraph by paragraph (the citation viewer)."""
    doc = svc.documents.get(f"{doc_id}@{version}")
    if doc is None:
        raise HTTPException(status_code=404, detail="unknown document version")
    return doc.to_json()  # type: ignore[no-any-return]


@router.get("/documents/{doc_id}/diff")
def diff(
    doc_id: str,
    svc: Annotated[Any, Depends(services)],
    from_version: Annotated[str, Query(alias="from")],
    to_version: Annotated[str, Query(alias="to")],
    include_unchanged: bool = False,
) -> dict[str, Any]:
    """Paragraph-level changes between two versions of a document."""
    old = svc.documents.get(f"{doc_id}@{from_version}")
    new = svc.documents.get(f"{doc_id}@{to_version}")
    if old is None or new is None:
        raise HTTPException(status_code=404, detail="unknown document version")
    changes = diff_versions(old, new)
    return {
        "doc_id": doc_id,
        "from": from_version,
        "to": to_version,
        "summary": summarise(changes),
        "changes": [
            asdict(c) | {"substantive": c.substantive}
            for c in changes
            if include_unchanged or c.kind != "unchanged"
        ],
    }


@router.get("/graph/supersession")
def supersession_graph(
    svc: Annotated[Any, Depends(services)], doc: str | None = None
) -> dict[str, Any]:
    """Nodes (corpus documents) and edges (who repealed / amended whom)."""
    with session_scope(svc.engine) as session:
        query = select(SupersessionEdge)
        if doc:
            query = query.where(or_(SupersessionEdge.source == doc, SupersessionEdge.target == doc))
        edges = list(session.scalars(query))
        ids = {e.source for e in edges} | {
            e.target for e in edges if not e.target.startswith("ext:")
        }
        rows = session.scalars(select(DocumentVersion).where(DocumentVersion.doc_id.in_(ids))).all()
        nodes: dict[str, dict[str, Any]] = {}
        for row in rows:  # one node per document: its latest version
            if row.doc_id not in nodes or (row.valid_from or date.min) > (
                nodes[row.doc_id]["valid_from"] or date.min
            ):
                nodes[row.doc_id] = {
                    "id": row.doc_id,
                    "title": row.title,
                    "regulator": row.regulator,
                    "status": row.status,
                    "valid_from": row.valid_from,
                }
        return {
            "nodes": list(nodes.values()),
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "type": e.type,
                    "method": e.method,
                    "effective": e.effective,
                    "evidence": e.evidence,
                }
                for e in edges
            ],
        }


@router.get("/changes")
def change_feed(
    svc: Annotated[Any, Depends(services)],
    since: Annotated[date, Query()] = date(2025, 1, 1),
) -> list[dict[str, Any]]:
    """Versions that started or ended on or after a date, newest first."""
    with session_scope(svc.engine) as session:
        rows = session.scalars(
            select(DocumentVersion).where(
                or_(DocumentVersion.valid_from >= since, DocumentVersion.valid_to >= since)
            )
        ).all()
    events = []
    for row in rows:
        if row.valid_from and row.valid_from >= since:
            events.append(
                {
                    "date": row.valid_from,
                    "event": "in_force" if row.status != "future" else "upcoming",
                    **_version(row),
                }
            )
        if row.valid_to and row.valid_to >= since:
            events.append({"date": row.valid_to, "event": "superseded", **_version(row)})
    return sorted(events, key=lambda e: e["date"], reverse=True)
