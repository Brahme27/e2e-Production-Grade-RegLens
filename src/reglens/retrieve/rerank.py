"""Cross-encoder reranking: read (question, passage) together and score relevance.

First-stage search compares two separately computed vectors, which is fast but shallow. A
cross-encoder reads the question and each candidate passage *together*, which is slower
but much more precise, so we use it only on the top ~30-50 candidates.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

from reglens.index.store import Hit

RerankerName = Literal["none", "minilm", "bge-m3"]
MODELS = {
    "minilm": "Xenova/ms-marco-MiniLM-L-6-v2",  # 80 MB, fast, English web-search trained
    "bge-m3": "BAAI/bge-reranker-v2-m3-int8",  # 570 MB, multilingual, stronger
}
MAX_PASSAGE_WORDS = 220  # cross-encoders read ~512 tokens; long passages are truncated


class Reranker:
    def __init__(self, name: RerankerName, models_dir: Path | None = None) -> None:
        self.name = name
        self.models_dir = str(models_dir) if models_dir else None
        self._model: Any = None

    def _impl(self) -> Any:
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder  # noqa: PLC0415

            self._model = TextCrossEncoder(MODELS[self.name], cache_dir=self.models_dir)
        return self._model

    @staticmethod
    def passage(hit: Hit) -> str:
        words = hit.chunk.embed_text.split()
        return " ".join(words[:MAX_PASSAGE_WORDS])

    def rerank(self, question: str, hits: list[Hit], top_k: int) -> list[Hit]:
        if self.name == "none" or not hits:
            return hits[:top_k]
        scores = list(self._impl().rerank(question, [self.passage(h) for h in hits], batch_size=16))
        ranked = sorted(zip(hits, scores, strict=True), key=lambda pair: pair[1], reverse=True)
        return [replace(hit, score=float(score)) for hit, score in ranked[:top_k]]
