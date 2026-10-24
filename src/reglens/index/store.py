"""Qdrant vector store: named dense + sparse vectors, hybrid search, "as of" filters.

One collection per index variant (``reglens_fixed``, ``reglens_para``, ...). Production
reads through the alias ``reglens``, so a re-index builds a new collection and then swaps
the alias atomically (zero downtime).
"""

from __future__ import annotations

import warnings
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from qdrant_client import QdrantClient, models

from reglens.index.chunking import Chunk
from reglens.index.embed import SparseVec
from reglens.log import get_logger

log = get_logger(__name__)

DENSE = "dense"
SPARSE = "bm25"
UPSERT_BATCH = 256
KEYWORD_FIELDS = ("regulator", "doc_id", "status", "applies_to", "topics", "doc_type")
INTEGER_FIELDS = ("valid_from_day", "valid_to_day")


@dataclass(frozen=True)
class SearchFilter:
    as_of: date | None = None
    regulators: tuple[str, ...] = ()
    doc_ids: tuple[str, ...] = ()
    applies_to: tuple[str, ...] = ()

    def to_qdrant(self) -> models.Filter | None:
        must: list[Any] = []
        if self.as_of is not None:
            day = self.as_of.toordinal()
            must.append(models.FieldCondition(key="valid_from_day", range=models.Range(lte=day)))
            must.append(models.FieldCondition(key="valid_to_day", range=models.Range(gt=day)))
        for key, values in (
            ("regulator", self.regulators),
            ("doc_id", self.doc_ids),
            ("applies_to", self.applies_to),
        ):
            if values:
                must.append(models.FieldCondition(key=key, match=models.MatchAny(any=list(values))))
        return models.Filter(must=must) if must else None


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


def connect(url: str | None, local_path: Path) -> QdrantClient:
    """Qdrant server when a URL is set (docker/cloud), else an embedded on-disk store."""
    if url:
        return QdrantClient(url=url, timeout=30)
    local_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(local_path))


def _sparse(vec: SparseVec) -> models.SparseVector:
    return models.SparseVector(indices=vec.indices, values=vec.values)


class VectorStore:
    def __init__(self, client: QdrantClient) -> None:
        self.client = client

    # ---------- build ----------
    def recreate(self, collection: str, dense_dim: int) -> None:
        if self.client.collection_exists(collection):
            self.client.delete_collection(collection)
        self.client.create_collection(
            collection,
            vectors_config={
                DENSE: models.VectorParams(size=dense_dim, distance=models.Distance.COSINE)
            },
            # IDF is computed by Qdrant over the whole collection: true BM25 scoring
            sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)},
        )
        # payload indexes make filtered search fast on a Qdrant server; the embedded local
        # mode scans everything anyway and warns, so silence that warning
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name in KEYWORD_FIELDS:
                self.client.create_payload_index(collection, name, models.PayloadSchemaType.KEYWORD)
            for name in INTEGER_FIELDS:
                self.client.create_payload_index(collection, name, models.PayloadSchemaType.INTEGER)

    def upsert(
        self,
        collection: str,
        chunks: Sequence[Chunk],
        dense: Sequence[list[float]],
        sparse: Sequence[SparseVec],
    ) -> None:
        for start in range(0, len(chunks), UPSERT_BATCH):
            points = [
                models.PointStruct(
                    id=chunk.chunk_id,
                    vector={DENSE: d, SPARSE: _sparse(s)},
                    payload=chunk.payload(),
                )
                for chunk, d, s in zip(
                    chunks[start : start + UPSERT_BATCH],
                    dense[start : start + UPSERT_BATCH],
                    sparse[start : start + UPSERT_BATCH],
                    strict=True,
                )
            ]
            self.client.upsert(collection, points=points, wait=True)

    def point_alias(self, alias: str, collection: str) -> None:
        """Atomically (re)point an alias: readers never see a half-built index."""
        operations: list[Any] = (
            [models.DeleteAliasOperation(delete_alias=models.DeleteAlias(alias_name=alias))]
            if any(a.alias_name == alias for a in self.client.get_aliases().aliases)
            else []
        )
        operations.append(
            models.CreateAliasOperation(
                create_alias=models.CreateAlias(collection_name=collection, alias_name=alias)
            )
        )
        self.client.update_collection_aliases(change_aliases_operations=operations)

    def count(self, collection: str) -> int:
        return self.client.count(collection, exact=True).count

    # ---------- search ----------
    @staticmethod
    def _hits(points: Sequence[Any]) -> list[Hit]:
        return [Hit(Chunk.from_payload(p.payload or {}), float(p.score)) for p in points]

    def dense_search(
        self, collection: str, vector: list[float], k: int, flt: SearchFilter | None = None
    ) -> list[Hit]:
        result = self.client.query_points(
            collection,
            query=vector,
            using=DENSE,
            limit=k,
            with_payload=True,
            query_filter=flt.to_qdrant() if flt else None,
        )
        return self._hits(result.points)

    def sparse_search(
        self, collection: str, vector: SparseVec, k: int, flt: SearchFilter | None = None
    ) -> list[Hit]:
        result = self.client.query_points(
            collection,
            query=_sparse(vector),
            using=SPARSE,
            limit=k,
            with_payload=True,
            query_filter=flt.to_qdrant() if flt else None,
        )
        return self._hits(result.points)

    def hybrid_search(
        self,
        collection: str,
        dense: list[float],
        sparse: SparseVec,
        k: int,
        flt: SearchFilter | None = None,
        *,
        prefetch: int = 50,
    ) -> list[Hit]:
        """Dense and sparse candidates fused with Reciprocal Rank Fusion inside Qdrant."""
        qfilter = flt.to_qdrant() if flt else None
        result = self.client.query_points(
            collection,
            prefetch=[
                models.Prefetch(query=dense, using=DENSE, limit=prefetch, filter=qfilter),
                models.Prefetch(
                    query=_sparse(sparse), using=SPARSE, limit=prefetch, filter=qfilter
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=k,
            with_payload=True,
        )
        return self._hits(result.points)

    def fetch(self, collection: str, ids: list[str]) -> list[Chunk]:
        points = self.client.retrieve(collection, ids=ids, with_payload=True)
        return [Chunk.from_payload(p.payload or {}) for p in points]
