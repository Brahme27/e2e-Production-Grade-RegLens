"""Turn the source list into raw snapshots on disk + a manifest of every version.

Layout::

    data/raw/<doc_id>/<version>/<part>.<html|pdf>
    data/raw/manifest.jsonl      one line per (doc, version): where it came from, hashes

A *version* is one snapshot of a document as it stood at some moment:
``current`` (today's live page), ``v2025-11-28`` (an older snapshot, from the regulator's
own archive or the Wayback Machine) or ``asof2025-01-01`` (the PRA Rulebook as it stood
on that date).
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path

from reglens.config import get_settings
from reglens.corpus.fetch import FetchError, FetchResult, PoliteFetcher
from reglens.corpus.sources import SourceDoc, load_sources
from reglens.log import configure_logging, get_logger

log = get_logger(__name__)

FCA_BASE = "https://handbook.fca.org.uk/handbook"
PRA_BASE = "https://www.prarulebook.co.uk/pra-rules"
FCA_MAX_SECTIONS = 40
FCA_EMPTY_STREAK_TO_STOP = 2
MIN_PDF_BYTES = 1_000
SEBI_PDF = re.compile(
    rb"file=((?:https://www\.sebi\.gov\.in)?/sebi_data/[^'\"]+?\.pdf)", re.IGNORECASE
)
SEBI_HOST = "https://www.sebi.gov.in"


@dataclass(frozen=True)
class RawPart:
    name: str
    path: str  # relative to the raw dir
    url: str
    sha256: str


@dataclass
class RawVersion:
    doc_id: str
    version: str
    source: str  # live | wayback | pra_point_in_time
    parts: list[RawPart] = field(default_factory=list)


def _url(doc: SourceDoc) -> str:
    if doc.url is None:  # SourceDoc validation guarantees this for url-based kinds
        raise ValueError(f"{doc.id}: no url")
    return doc.url


def _extension(result: FetchResult) -> str:
    if "pdf" in result.content_type or result.content[:5] == b"%PDF-":
        return "pdf"
    return "html"


def _fca_section_has_provisions(result: FetchResult) -> bool:
    # an out-of-range section still returns HTTP 200, just with no provision cards
    return b"<p-card" in result.content


class Crawler:
    def __init__(self, fetcher: PoliteFetcher, raw_dir: Path) -> None:
        self.fetcher = fetcher
        self.raw_dir = raw_dir

    def _save(self, version: RawVersion, part: str, result: FetchResult) -> None:
        relative = Path(version.doc_id) / version.version / f"{part}.{_extension(result)}"
        target = self.raw_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.content)
        version.parts.append(RawPart(part, relative.as_posix(), result.url, result.sha256))

    def _single(self, doc: SourceDoc) -> Iterator[RawVersion]:
        live = RawVersion(doc.id, "current", "live")
        self._save(live, "main", self.fetcher.get(_url(doc)))
        yield live
        yield from self._snapshots(doc)

    def _snapshots(self, doc: SourceDoc) -> Iterator[RawVersion]:
        for snap in doc.snapshots:
            source = "wayback" if "web.archive.org" in snap.url else "archive"
            archived = RawVersion(doc.id, f"v{snap.label.isoformat()}", source)
            self._save(archived, "main", self.fetcher.get(snap.url))
            yield archived

    def _sebi_circular(self, doc: SourceDoc) -> Iterator[RawVersion]:
        """SEBI circular pages usually embed the real text as a PDF in an iframe."""
        page = self.fetcher.get(_url(doc))
        live = RawVersion(doc.id, "current", "live")
        match = SEBI_PDF.search(page.content)
        if match:
            pdf_url = match.group(1).decode()
            if pdf_url.startswith("/"):  # older pages use site-relative links
                pdf_url = SEBI_HOST + pdf_url
            self._save(live, "main", self.fetcher.get(pdf_url))
        else:  # older circulars are plain HTML pages
            self._save(live, "main", page)
        yield live

    def _fca_chapter(self, doc: SourceDoc) -> Iterator[RawVersion]:
        version = RawVersion(doc.id, "current", "live")
        chapter = doc.chapter
        empty_streak = 0
        for number in range(1, FCA_MAX_SECTIONS + 1):
            try:
                result: FetchResult | None = self.fetcher.get(
                    f"{FCA_BASE}/{chapter}/{chapter}s{number}"
                )
            except FetchError:
                result = None
            if result is None or not _fca_section_has_provisions(result):
                empty_streak += 1
                if empty_streak >= FCA_EMPTY_STREAK_TO_STOP:
                    break
                continue
            empty_streak = 0
            self._save(version, f"s{number:02d}", result)
        if not version.parts:
            raise FetchError(f"{doc.id}: no FCA sections found for chapter {chapter}")
        yield version

    def _pra_part(self, doc: SourceDoc) -> Iterator[RawVersion]:
        for day in doc.as_of:
            version = RawVersion(doc.id, f"asof{day.isoformat()}", "pra_point_in_time")
            url = f"{PRA_BASE}/{doc.part}/{day.strftime('%d-%m-%Y')}"
            self._save(version, "main", self.fetcher.get(url))
            yield version

    def crawl(self, doc: SourceDoc) -> list[RawVersion]:
        strategies = {
            "html": self._single,
            "pdf": self._single,
            "sebi_circular": self._sebi_circular,
            "fca_chapter": self._fca_chapter,
            "pra_part": self._pra_part,
        }
        versions = list(strategies[doc.kind](doc))
        if doc.kind == "pdf":
            for version in versions:
                pdf = self.raw_dir / version.parts[0].path
                if pdf.suffix != ".pdf" or pdf.stat().st_size < MIN_PDF_BYTES:
                    raise FetchError(f"{doc.id}: expected a PDF, got {pdf.name}")
        return versions


def write_manifest(versions: list[RawVersion], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for version in versions:
            handle.write(json.dumps(asdict(version)) + "\n")


def read_manifest(path: Path) -> list[RawVersion]:
    versions = []
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        parts = [RawPart(**p) for p in record.pop("parts")]
        versions.append(RawVersion(parts=parts, **record))
    return versions


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Download the curated regulatory corpus")
    parser.add_argument("--only", nargs="*", help="limit to these source ids")
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    sources = load_sources(settings.configs_dir / "sources.yaml")
    fetcher = PoliteFetcher(
        cache_dir=settings.raw_dir / ".http-cache",
        user_agent=settings.crawl_user_agent,
        delay_seconds=settings.crawl_delay_seconds,
        timeout_seconds=settings.crawl_timeout_seconds,
    )
    crawler = Crawler(fetcher, settings.raw_dir)
    versions: list[RawVersion] = []
    failures: list[str] = []
    for doc in sources.documents:
        if args.only and doc.id not in args.only:
            continue
        try:
            versions.extend(crawler.crawl(doc))
        except FetchError as exc:
            failures.append(doc.id)
            log.error("crawl_failed", doc=doc.id, error=str(exc))
    fetcher.close()
    manifest = settings.raw_dir / "manifest.jsonl"
    if args.only and manifest.exists():  # partial re-crawl: keep everything else
        versions = [v for v in read_manifest(manifest) if v.doc_id not in args.only] + versions
    write_manifest(versions, manifest)
    log.info("crawl_done", versions=len(versions), failed=failures)
    if failures:
        raise SystemExit(f"failed: {failures}")


if __name__ == "__main__":
    main()
