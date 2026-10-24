"""Deterministic fakes for models: tests run in milliseconds, without downloads."""

from __future__ import annotations

import hashlib
import re
from datetime import date

import numpy as np

from reglens.index.chunking import Chunk
from reglens.index.embed import SparseVec
from reglens.index.store import Hit

DIM = 32


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _bucket(token: str) -> int:
    return int(hashlib.md5(token.encode()).hexdigest(), 16) % DIM  # noqa: S324 - test hashing


class FakeEmbedder:
    """Bag-of-words vectors: texts sharing words are close. Same interface as Embedder."""

    dense_model = "fake-dense"
    sparse_model = "fake-sparse"

    def dense(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            v = np.zeros(DIM, dtype=np.float32)
            for token in _tokens(text):
                v[_bucket(token)] += 1.0
            norm = float(np.linalg.norm(v)) or 1.0
            out.append((v / norm).tolist())
        return out

    def sparse(self, texts: list[str]) -> list[SparseVec]:
        out = []
        for text in texts:
            counts: dict[int, float] = {}
            for token in _tokens(text):
                index = int(hashlib.md5(token.encode()).hexdigest(), 16) % 100_000  # noqa: S324
                counts[index] = counts.get(index, 0.0) + 1.0
            out.append(SparseVec(list(counts), list(counts.values())))
        return out

    def dense_query(self, text: str) -> list[float]:
        return self.dense([text])[0]

    def sparse_query(self, text: str) -> SparseVec:
        return self.sparse([text])[0]


class FakeReranker:
    """Scores by word overlap with the question (a stand-in for a cross-encoder)."""

    name = "fake"

    def rerank(self, question: str, hits: list[Hit], top_k: int) -> list[Hit]:
        words = set(_tokens(question))
        scored = [
            Hit(h.chunk, len(words & set(_tokens(h.chunk.text))) / (len(words) or 1)) for h in hits
        ]
        return sorted(scored, key=lambda h: h.score, reverse=True)[:top_k]


def make_chunk(
    chunk_id: str,
    text: str,
    *,
    regulator: str = "RBI",
    doc_id: str = "doc",
    ref: str = "1",
    valid_from: date | None = date(2020, 1, 1),
    valid_to: date | None = None,
    status: str = "current",
    topics: tuple[str, ...] = ("kyc",),
) -> Chunk:
    import uuid  # noqa: PLC0415

    return Chunk(
        chunk_id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id)),
        doc_key=f"{doc_id}@current",
        doc_id=doc_id,
        version="current",
        regulator=regulator,
        doc_type="directions",
        title=f"Title of {doc_id}",
        doc_number=f"NUM/{doc_id}",
        url="https://reg.example",
        ref=ref,
        refs=(ref,),
        part=1,
        parts=1,
        section_path=("Chapter I",),
        text=text,
        kind="paragraph",
        valid_from=valid_from,
        valid_to=valid_to,
        status=status,
        topics=topics,
        applies_to=("commercial_banks",),
    )
