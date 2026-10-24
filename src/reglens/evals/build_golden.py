"""CLI: build ``evals/golden/golden_v1.jsonl`` (LLM-generated + hand-written items)."""

from __future__ import annotations

import argparse
import random

import numpy as np

from reglens.config import get_settings
from reglens.evals.golden import (
    Equivalents,
    comparison_items,
    handwritten_items,
    lookup_items,
    save,
    temporal_items,
)
from reglens.index.build import make_embedder, read_chunks
from reglens.llm.client import build_client
from reglens.log import configure_logging, get_logger

log = get_logger(__name__)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build the golden evaluation set")
    parser.add_argument("--per-regulator", type=int, default=20)
    parser.add_argument("--temporal", type=int, default=30)
    parser.add_argument("--comparison", type=int, default=25)
    parser.add_argument("--no-llm", action="store_true", help="replay cached LLM answers only")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    rng = random.Random(settings.random_seed)
    chunks = read_chunks(settings.data_dir / "processed" / "chunks" / "para.jsonl")
    eq = Equivalents(chunks)
    llm = build_client(settings, cache_only=args.no_llm)

    items = lookup_items(chunks, eq, llm, args.per_regulator, rng)
    items += temporal_items(chunks, eq, llm, args.temporal, rng)
    embedder = make_embedder(settings)
    current = [c for c in chunks if c.status == "current"]
    vectors = {
        c.chunk_id: np.asarray(v, dtype=np.float32)
        for c, v in zip(current, embedder.dense([c.text for c in current]), strict=True)
    }
    items += comparison_items(chunks, vectors, eq, llm, args.comparison, rng=rng)
    items += handwritten_items(settings.evals_dir / "golden" / "handwritten.yaml")
    out = settings.evals_dir / "golden" / "golden_v1.jsonl"
    save(items, out)
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category] = counts.get(item.category, 0) + 1
    log.info("golden_built", total=len(items), llm_calls=llm.calls, **counts)


if __name__ == "__main__":  # pragma: no cover
    main()
