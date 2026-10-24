"""Embeddings: dense (meaning) + sparse (exact words), local ONNX models on the CPU.

- **dense**: BAAI/bge-small-en-v1.5 (384-d). "Outsourcing to a cloud vendor" finds
  "arrangements with cloud service providers".
- **sparse**: BM25 (Qdrant/bm25). "SS1/23", "PRIN 2A.4.1R" and "Annex II" are matched
  exactly; dense models blur such identifiers.

Vectors are cached in SQLite keyed by a hash of (model, text): re-indexing after a change
only embeds new or edited chunks.
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from reglens.log import get_logger

log = get_logger(__name__)

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
BATCH = 16  # small batches: less padding waste with mixed-length paragraphs


@dataclass(frozen=True)
class SparseVec:
    indices: list[int]
    values: list[float]


class EmbeddingCache:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute("create table if not exists vec (key text primary key, value blob)")

    @staticmethod
    def key(model: str, text: str) -> str:
        return hashlib.sha256(f"{model}\x00{text}".encode()).hexdigest()

    def get_many(self, keys: list[str]) -> dict[str, bytes]:
        found: dict[str, bytes] = {}
        for start in range(0, len(keys), 500):
            batch = keys[start : start + 500]
            marks = ",".join("?" * len(batch))
            for key, value in self._db.execute(
                f"select key, value from vec where key in ({marks})",  # noqa: S608 - placeholders only
                batch,
            ):
                found[key] = value
        return found

    def put_many(self, items: list[tuple[str, bytes]]) -> None:
        self._db.executemany("insert or replace into vec values (?, ?)", items)
        self._db.commit()


def _cached(
    texts: list[str],
    model: str,
    cache: EmbeddingCache | None,
    compute: Callable[[list[str]], list[bytes]],
) -> list[bytes]:
    keys = [EmbeddingCache.key(model, t) for t in texts]
    found = cache.get_many(keys) if cache else {}
    missing = [i for i, k in enumerate(keys) if k not in found]
    if missing:
        computed = compute([texts[i] for i in missing])
        new = [(keys[i], blob) for i, blob in zip(missing, computed, strict=True)]
        if cache:
            cache.put_many(new)
        found.update(dict(new))
        log.info("embedded", model=model, new=len(missing), cached=len(texts) - len(missing))
    return [found[k] for k in keys]


def _sparse_to_blob(vector: Any) -> bytes:
    indices = np.asarray(vector.indices, dtype=np.int64)
    values = np.asarray(vector.values, dtype=np.float32)
    return np.int64(len(indices)).tobytes() + indices.tobytes() + values.tobytes()


def _blob_to_sparse(blob: bytes) -> SparseVec:
    n = int(np.frombuffer(blob[:8], dtype=np.int64)[0])
    indices = np.frombuffer(blob[8 : 8 + 8 * n], dtype=np.int64)
    values = np.frombuffer(blob[8 + 8 * n :], dtype=np.float32)
    return SparseVec(indices.tolist(), values.tolist())


class Embedder:
    """Dense + sparse embeddings with a persistent cache. Models load lazily."""

    def __init__(
        self,
        dense_model: str,
        sparse_model: str,
        cache_path: Path | None,
        models_dir: Path | None = None,
    ) -> None:
        self.dense_model = dense_model
        self.sparse_model = sparse_model
        self.models_dir = str(models_dir) if models_dir else None
        self.cache = EmbeddingCache(cache_path) if cache_path else None
        self._dense: Any = None
        self._sparse: Any = None

    def _dense_impl(self) -> Any:
        if self._dense is None:
            from fastembed import TextEmbedding  # noqa: PLC0415 - loads an ONNX model

            self._dense = TextEmbedding(self.dense_model, cache_dir=self.models_dir)
        return self._dense

    def _sparse_impl(self) -> Any:
        if self._sparse is None:
            from fastembed import SparseTextEmbedding  # noqa: PLC0415

            self._sparse = SparseTextEmbedding(self.sparse_model, cache_dir=self.models_dir)
        return self._sparse

    @property
    def dense_dim(self) -> int:
        return len(self.dense([" "])[0])

    def dense(self, texts: list[str]) -> list[list[float]]:
        def compute(batch: list[str]) -> list[bytes]:
            vectors: Iterable[Any] = self._dense_impl().embed(batch, batch_size=BATCH)
            return [np.asarray(v, dtype=np.float32).tobytes() for v in vectors]

        blobs = _cached(texts, self.dense_model, self.cache, compute)
        return [np.frombuffer(b, dtype=np.float32).tolist() for b in blobs]

    def sparse(self, texts: list[str]) -> list[SparseVec]:
        def compute(batch: list[str]) -> list[bytes]:
            vectors = self._sparse_impl().embed(batch, batch_size=BATCH)
            return [_sparse_to_blob(v) for v in vectors]

        return [_blob_to_sparse(b) for b in _cached(texts, self.sparse_model, self.cache, compute)]

    def dense_query(self, text: str) -> list[float]:
        prefix = BGE_QUERY_PREFIX if "bge" in self.dense_model.lower() else ""
        return self.dense([prefix + text])[0]

    def sparse_query(self, text: str) -> SparseVec:
        # BM25 weights queries differently from documents (no length normalisation)
        vector = next(iter(self._sparse_impl().query_embed(text)))
        return SparseVec(list(map(int, vector.indices)), list(map(float, vector.values)))
