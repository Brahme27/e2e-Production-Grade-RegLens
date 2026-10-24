"""Build the search indexes: chunk -> add context -> embed -> load into Qdrant.

One collection per *variant*, so the ablation can compare them side by side:

| variant        | chunking   | context added before embedding            | ablation row |
|----------------|------------|-------------------------------------------|--------------|
| fixed          | ~512 tokens| none                                      | A            |
| para           | paragraph  | none                                      | B, C, D      |
| para_ctx       | paragraph  | structural header                         | E1           |
| para_ctx_sum   | paragraph  | structural header + LLM document summary  | E2           |

The serving alias ``reglens`` points at ``settings.serving_variant``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from reglens.config import Settings, get_settings
from reglens.index.chunking import Chunk, Strategy, chunk_corpus
from reglens.index.context import ContextMode, add_context, document_summaries
from reglens.index.embed import Embedder
from reglens.index.store import VectorStore, connect
from reglens.llm.client import build_client
from reglens.log import configure_logging, get_logger
from reglens.parse.model import load_documents
from reglens.temporal.validity import load_validity

log = get_logger(__name__)


@dataclass(frozen=True)
class Variant:
    name: str
    strategy: Strategy
    context: ContextMode

    @property
    def collection(self) -> str:
        return f"reglens_{self.name}"


VARIANTS = {
    v.name: v
    for v in (
        Variant("fixed", "fixed", "none"),
        Variant("para", "paragraph", "none"),
        Variant("para_ctx", "paragraph", "structural"),
        Variant("para_ctx_sum", "paragraph", "structural+summary"),
    )
}


def make_embedder(settings: Settings) -> Embedder:
    return Embedder(
        settings.dense_model,
        settings.sparse_model,
        cache_path=settings.artifacts_dir / "embeddings.sqlite",
        models_dir=settings.models_cache_dir,
    )


def write_chunks(chunks: list[Chunk], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.payload(), ensure_ascii=False) + "\n")


def read_chunks(path: Path) -> list[Chunk]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [Chunk.from_payload(json.loads(line)) for line in lines]


def build(settings: Settings, variants: list[Variant], *, use_llm: bool = True) -> dict[str, int]:
    processed = settings.data_dir / "processed"
    documents = load_documents(processed / "documents")
    validity = load_validity(processed / "validity.json")
    summaries: dict[str, str] = {}
    if any(v.context == "structural+summary" for v in variants):
        llm = build_client(settings, cache_only=not use_llm)
        summaries = document_summaries(documents, llm)
        (processed / "doc_summaries.json").write_text(
            json.dumps(summaries, indent=1, ensure_ascii=False), encoding="utf-8"
        )
    embedder = make_embedder(settings)
    store = VectorStore(connect(settings.qdrant_url, settings.artifacts_dir / "qdrant"))
    counts = {}
    for variant in variants:
        chunks = add_context(
            chunk_corpus(documents, validity, variant.strategy), variant.context, summaries
        )
        texts = [c.embed_text for c in chunks]
        dense = embedder.dense(texts)
        sparse = embedder.sparse(texts)
        store.recreate(variant.collection, len(dense[0]))
        store.upsert(variant.collection, chunks, dense, sparse)
        write_chunks(chunks, processed / "chunks" / f"{variant.name}.jsonl")
        counts[variant.name] = store.count(variant.collection)
        log.info("indexed", variant=variant.name, chunks=counts[variant.name])
    if settings.serving_variant in counts:
        store.point_alias(settings.qdrant_collection, VARIANTS[settings.serving_variant].collection)
        log.info("alias", alias=settings.qdrant_collection, target=settings.serving_variant)
    store.client.close()
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the Qdrant indexes")
    parser.add_argument("--variants", nargs="*", default=list(VARIANTS), choices=list(VARIANTS))
    parser.add_argument("--no-llm", action="store_true", help="only use cached document summaries")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    build(settings, [VARIANTS[name] for name in args.variants], use_llm=not args.no_llm)


if __name__ == "__main__":  # pragma: no cover
    main()
