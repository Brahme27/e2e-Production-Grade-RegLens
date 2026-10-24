"""Build the supersession graph + validity intervals and load them into the database."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import delete

from reglens.config import Settings, get_settings
from reglens.evals.supersession import load_gold, score
from reglens.llm.client import LLMClient, build_client
from reglens.log import configure_logging, get_logger
from reglens.parse.model import ParsedDocument, load_documents
from reglens.store.db import DocumentVersion, SupersessionEdge, init_db, make_engine, session_scope
from reglens.temporal.supersession import (
    Edge,
    edges_to_json,
    llm_edges,
    merge_edges,
    rule_edges,
)
from reglens.temporal.validity import Validity, compute_validity

log = get_logger(__name__)


def content_sha(doc: ParsedDocument) -> str:
    joined = "\n".join(f"{p.ref}\t{p.text}" for p in doc.paragraphs)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def apply_overrides(edges: list[Edge], path: Path) -> list[Edge]:
    """Reviewer decisions: drop rejected edges, add missing ones."""
    if not path.exists():
        return edges
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rejected = {(r["source"], r["target"], r["type"]) for r in raw.get("reject", [])}
    kept = [e for e in edges if e.pair not in rejected]
    added = [
        Edge(a["source"], a["target"], a["type"], "rule", evidence="reviewer")
        for a in raw.get("add", [])
    ]
    if rejected or added:
        log.info("supersession_overrides", rejected=len(edges) - len(kept), added=len(added))
    return merge_edges(kept, added)


def build_temporal(
    documents: list[ParsedDocument],
    llm: LLMClient | None,
    today: date,
    overrides: Path | None = None,
) -> tuple[list[Edge], list[Edge], dict[str, Validity]]:
    """Return (raw extracted edges, reviewed edges, validity of every version)."""
    raw = rule_edges(documents)
    if llm is not None:
        raw = merge_edges(raw, llm_edges(documents, llm))
    raw = merge_edges(raw)
    reviewed = apply_overrides(raw, overrides) if overrides else raw
    return raw, reviewed, compute_validity(documents, reviewed, today)


def write_eval_report(raw: list[Edge], documents: list[ParsedDocument], settings: Settings) -> None:
    gold_path = settings.evals_dir / "supersession_gold.yaml"
    if not gold_path.exists():
        return
    gold = load_gold(gold_path)
    rules_only = [e for e in raw if e.method != "llm"]
    report: dict[str, Any] = {
        "gold_edges": len(gold.edges),
        "labelled_sources": len(gold.labelled_sources),
        "rules": score(rules_only, gold),
        "rules_internal": score(rules_only, gold, internal_only=True),
        "rules_plus_llm": score(raw, gold),
        "rules_plus_llm_internal": score(raw, gold, internal_only=True),
        "documents": len({d.doc_id for d in documents}),
    }
    out = settings.reports_dir / "supersession_eval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1), encoding="utf-8")
    log.info(
        "supersession_eval",
        rules_f1=report["rules"]["f1"],
        rules_plus_llm_f1=report["rules_plus_llm"]["f1"],
    )


def save_temporal(
    documents: list[ParsedDocument],
    edges: list[Edge],
    validity: dict[str, Validity],
    settings: Settings,
) -> None:
    out = settings.data_dir / "processed"
    out.mkdir(parents=True, exist_ok=True)
    (out / "supersession_edges.json").write_text(edges_to_json(edges), encoding="utf-8")
    rows = {
        key: {
            "valid_from": v.valid_from.isoformat() if v.valid_from else None,
            "valid_to": v.valid_to.isoformat() if v.valid_to else None,
            "status": v.status,
            "superseded_by": v.superseded_by,
        }
        for key, v in sorted(validity.items())
    }
    (out / "validity.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    engine = make_engine(settings.sqlalchemy_url)
    init_db(engine)
    with session_scope(engine) as session:
        session.execute(delete(SupersessionEdge))
        session.execute(delete(DocumentVersion))
        for doc in documents:
            v = validity[doc.key]
            session.add(
                DocumentVersion(
                    key=doc.key,
                    doc_id=doc.doc_id,
                    version=doc.version,
                    regulator=doc.regulator,
                    doc_type=doc.doc_type,
                    title=doc.title,
                    doc_number=doc.doc_number,
                    url=doc.url,
                    topics=doc.topics,
                    applies_to=doc.applies_to,
                    issue_date=doc.issue_date,
                    valid_from=v.valid_from,
                    valid_to=v.valid_to,
                    status=v.status,
                    superseded_by=v.superseded_by,
                    paragraph_count=len(doc.paragraphs),
                    content_sha=content_sha(doc),
                )
            )
        for edge in edges:
            session.add(
                SupersessionEdge(
                    source=edge.source,
                    target=edge.target,
                    type=edge.type,
                    method=edge.method,
                    effective=edge.effective,
                    evidence=edge.evidence,
                )
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Supersession graph + validity intervals")
    parser.add_argument("--no-llm", action="store_true", help="rules only (no LLM calls)")
    parser.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    documents = load_documents(settings.data_dir / "processed" / "documents")
    llm = None if args.no_llm else build_client(settings)
    overrides = settings.configs_dir / "supersession_overrides.yaml"
    raw, edges, validity = build_temporal(documents, llm, args.today, overrides)
    write_eval_report(raw, documents, settings)
    save_temporal(documents, edges, validity, settings)
    statuses = [v.status for v in validity.values()]
    log.info(
        "temporal_done",
        edges=len(edges),
        current=statuses.count("current"),
        superseded=statuses.count("superseded"),
        future=statuses.count("future"),
        db=settings.sqlalchemy_url.split("@")[-1],
    )


if __name__ == "__main__":  # pragma: no cover
    main()
