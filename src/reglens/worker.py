"""Scheduled worker: keep the corpus, the time model and the serving index up to date.

One cycle = crawl (polite, cached) → parse → supersession + validity → re-index the
serving variant → log which document versions are new or changed (by content hash).
Locally: ``python -m reglens.worker --once``; in docker compose it loops every N hours;
on AWS an EventBridge schedule runs ``--once`` daily as an ECS task.
"""

from __future__ import annotations

import argparse
import time
from datetime import date

from sqlalchemy import select

from reglens.config import Settings, get_settings
from reglens.corpus import crawl
from reglens.index.build import VARIANTS, build
from reglens.log import configure_logging, get_logger
from reglens.parse import run as parse_run
from reglens.store.db import DocumentVersion, init_db, make_engine, session_scope
from reglens.temporal import run as temporal_run

log = get_logger(__name__)


def fingerprints(settings: Settings) -> dict[str, str]:
    engine = make_engine(settings.sqlalchemy_url)
    init_db(engine)
    with session_scope(engine) as session:
        return {row.key: row.content_sha for row in session.scalars(select(DocumentVersion))}


def cycle(settings: Settings, *, do_crawl: bool) -> dict[str, list[str]]:
    before = fingerprints(settings)
    if do_crawl:
        crawl.main([])
    parse_run.main()
    temporal_run.main(["--today", date.today().isoformat()])
    build(settings, [VARIANTS[settings.serving_variant]], use_llm=settings.groq_api_key is not None)
    after = fingerprints(settings)
    changes = {
        "new": sorted(set(after) - set(before)),
        "changed": sorted(k for k in after if k in before and after[k] != before[k]),
        "gone": sorted(set(before) - set(after)),
    }
    log.info(
        "worker_cycle", **{k: len(v) for k, v in changes.items()}, new_versions=changes["new"][:20]
    )
    return changes


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="RegLens scheduled worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--no-crawl", action="store_true", help="reuse raw downloads (offline)")
    parser.add_argument("--every-hours", type=float, default=24.0)
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    while True:
        cycle(settings, do_crawl=not args.no_crawl)
        if args.once:
            return
        time.sleep(args.every_hours * 3600)


if __name__ == "__main__":  # pragma: no cover
    main()
