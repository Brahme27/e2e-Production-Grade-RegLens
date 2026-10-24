"""Internal policies: load the (synthetic) policy documents and search them by clause.

Each policy is a markdown file with YAML front matter (entity, title, version) and numbered
clauses ("3.2 The Bank shall ..."). Clauses become chunks in their own Qdrant collection
(``policies``), searched with the same hybrid + rerank machinery as the regulations, and
always filtered to one entity.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import yaml

from reglens.index.chunking import Chunk, chunk_uuid
from reglens.index.embed import Embedder
from reglens.index.store import Hit, SearchFilter, VectorStore
from reglens.retrieve.rerank import Reranker

POLICY_COLLECTION = "policies"
CLAUSE = re.compile(r"^(\d{1,2}\.\d{1,2})\s+(.+)$")
HEADING = re.compile(r"^#{1,3}\s+(.+)$")


@dataclass(frozen=True)
class PolicyClause:
    entity: str
    policy_id: str
    policy_title: str
    version: str
    clause: str
    section: str
    text: str

    @property
    def label(self) -> str:
        return f"{self.policy_id} §{self.clause}"


def parse_policy(path: Path) -> list[PolicyClause]:
    raw = path.read_text(encoding="utf-8")
    _, front, body = raw.split("---", 2)
    meta = yaml.safe_load(front)
    clauses: list[PolicyClause] = []
    section = ""
    current: list[str] = []
    number = ""

    def close() -> None:
        if number and current:
            clauses.append(
                PolicyClause(
                    meta["entity"],
                    meta["policy_id"],
                    meta["title"],
                    str(meta["version"]),
                    number,
                    section,
                    " ".join(current),
                )
            )

    for raw_line in body.splitlines():
        line = raw_line.strip()
        heading = HEADING.match(line)
        clause = CLAUSE.match(line)
        if heading:
            close()
            number, current = "", []
            section = heading.group(1)
        elif clause:
            close()
            number, current = clause.group(1), [clause.group(2)]
        elif line and number:
            current.append(line)  # wrapped continuation line
    close()
    return clauses


def load_policies(folder: Path, entity: str | None = None) -> list[PolicyClause]:
    clauses = [c for path in sorted(folder.glob("*/*.md")) for c in parse_policy(path)]
    return [c for c in clauses if entity is None or c.entity == entity]


def clause_chunk(clause: PolicyClause) -> Chunk:
    return Chunk(
        chunk_id=chunk_uuid("policy", clause.policy_id, clause.version, clause.clause),
        doc_key=f"{clause.policy_id}@{clause.version}",
        doc_id=clause.policy_id,
        version=clause.version,
        regulator="INTERNAL",
        doc_type="policy",
        title=clause.policy_title,
        doc_number=clause.policy_id,
        url="",
        ref=clause.clause,
        refs=(clause.clause,),
        part=1,
        parts=1,
        section_path=(clause.section,),
        text=clause.text,
        kind="paragraph",
        valid_from=date.min,
        valid_to=None,
        status="current",
        topics=(),
        applies_to=(clause.entity,),
        context=f"{clause.policy_title} ({clause.policy_id} v{clause.version}). Section: {clause.section}.",
    )


def index_policies(store: VectorStore, embedder: Embedder, clauses: list[PolicyClause]) -> int:
    chunks = [clause_chunk(c) for c in clauses]
    texts = [c.embed_text for c in chunks]
    dense = embedder.dense(texts)
    store.recreate(POLICY_COLLECTION, len(dense[0]))
    store.upsert(POLICY_COLLECTION, chunks, dense, embedder.sparse(texts))
    return len(chunks)


class PolicySearch:
    def __init__(
        self, store: VectorStore, embedder: Embedder, reranker: Reranker, candidates: int = 20
    ) -> None:
        self.store = store
        self.embedder = embedder
        self.reranker = reranker
        self.candidates = candidates

    def search(self, obligation: str, entity: str, top_k: int = 5) -> list[Hit]:
        flt = SearchFilter(applies_to=(entity,))
        hits = self.store.hybrid_search(
            POLICY_COLLECTION,
            self.embedder.dense_query(obligation),
            self.embedder.sparse_query(obligation),
            self.candidates,
            flt,
            prefetch=self.candidates,
        )
        return [replace(h) for h in self.reranker.rerank(obligation, hits, top_k)]
