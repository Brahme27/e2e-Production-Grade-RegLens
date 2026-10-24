"""Semantic answer cache: the same question, asked in other words, is answered instantly.

A cached answer is reused only when ALL of these match:
- the question embeddings are near-identical (cosine >= 0.95);
- the same "as of" date (an answer about 2024 is not an answer about today);
- the same regulator filters and the same index/prompt version.

Backed by Redis in docker compose / AWS (shared by every API replica), or a small
in-process store locally. Each bucket keeps at most ``MAX_PER_BUCKET`` entries.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import date
from typing import Any, Protocol

import numpy as np

SIMILARITY = 0.95
MAX_PER_BUCKET = 200
TTL_SECONDS = 7 * 24 * 3600


@dataclass(frozen=True)
class CacheHit:
    answer: dict[str, Any]
    similarity: float


class _Backend(Protocol):
    def entries(self, bucket: str) -> list[dict[str, Any]]: ...
    def add(self, bucket: str, entry: dict[str, Any]) -> None: ...


class MemoryBackend:
    def __init__(self) -> None:
        self._buckets: dict[str, list[dict[str, Any]]] = {}

    def entries(self, bucket: str) -> list[dict[str, Any]]:
        now = time.time()
        return [e for e in self._buckets.get(bucket, []) if e["expires"] > now]

    def add(self, bucket: str, entry: dict[str, Any]) -> None:
        items = self._buckets.setdefault(bucket, [])
        items.append(entry)
        del items[:-MAX_PER_BUCKET]


class RedisBackend:
    def __init__(self, url: str) -> None:
        import redis  # noqa: PLC0415 - only needed when configured

        self._redis: Any = redis.Redis.from_url(url, socket_timeout=2)

    def entries(self, bucket: str) -> list[dict[str, Any]]:
        now = time.time()
        raw = self._redis.lrange(f"semcache:{bucket}", 0, -1)
        return [e for e in (json.loads(r) for r in raw) if e["expires"] > now]

    def add(self, bucket: str, entry: dict[str, Any]) -> None:
        key = f"semcache:{bucket}"
        pipe = self._redis.pipeline()
        pipe.lpush(key, json.dumps(entry))
        pipe.ltrim(key, 0, MAX_PER_BUCKET - 1)
        pipe.expire(key, TTL_SECONDS)
        pipe.execute()


class SemanticCache:
    def __init__(self, backend: _Backend, version: str) -> None:
        self.backend = backend
        self.version = version  # index + prompt version: a new index invalidates old answers

    def _bucket(self, as_of: date | None, regulators: tuple[str, ...]) -> str:
        return f"{self.version}|{as_of.isoformat() if as_of else 'today'}|{','.join(sorted(regulators))}"

    def get(
        self, embedding: list[float], as_of: date | None, regulators: tuple[str, ...]
    ) -> CacheHit | None:
        query = np.asarray(embedding, dtype=np.float32)
        best: CacheHit | None = None
        for entry in self.backend.entries(self._bucket(as_of, regulators)):
            similarity = float(query @ np.asarray(entry["embedding"], dtype=np.float32))
            if similarity >= SIMILARITY and (best is None or similarity > best.similarity):
                best = CacheHit(entry["answer"], similarity)
        return best

    def put(
        self,
        embedding: list[float],
        as_of: date | None,
        regulators: tuple[str, ...],
        answer: dict[str, Any],
    ) -> None:
        entry = {
            "embedding": list(map(float, embedding)),
            "answer": answer,
            "expires": time.time() + TTL_SECONDS,
        }
        self.backend.add(self._bucket(as_of, regulators), entry)


def build_cache(redis_url: str | None, version: str) -> SemanticCache:
    backend: _Backend = RedisBackend(redis_url) if redis_url else MemoryBackend()
    return SemanticCache(backend, version)
