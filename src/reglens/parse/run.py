"""Parse every raw version in the manifest into ``data/processed/documents/*.json``."""

from __future__ import annotations

import re
import shutil
from datetime import date
from pathlib import Path

from reglens.config import get_settings
from reglens.corpus.crawl import RawVersion, read_manifest
from reglens.corpus.sources import SourceDoc, load_sources
from reglens.log import configure_logging, get_logger
from reglens.parse.handbooks import parse_fca_section, parse_pra_part
from reglens.parse.model import ParsedDocument, save_documents
from reglens.parse.pdf import parse_pdf
from reglens.parse.rbi import parse_rbi_html
from reglens.parse.text import find_dates

log = get_logger(__name__)

DOC_NUMBERS = [
    re.compile(r"\bSEBI/HO/[A-Z0-9/_-]+/\d{4}/\d+\b"),
    re.compile(r"\bRBI/[A-Za-z]*/?\d{4}-\d{2}/\d+\b"),
    re.compile(r"\b(?:SS|PS|CP)\d{1,2}/\d{2}\b"),
    re.compile(r"\bCIR/[A-Z0-9/_-]+/\d{4}\b"),
]
FCA_CHAPTER_CODE = re.compile(r"^([A-Z]+ \d+[A-Z]?)\.")
MIN_PARAGRAPHS = 1


def _doc_number(text: str) -> str | None:
    for pattern in DOC_NUMBERS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def _version_label_date(version: str) -> date | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})", version)
    return date.fromisoformat(match.group(1)) if match else None


def _base(source: SourceDoc, raw: RawVersion) -> ParsedDocument:
    return ParsedDocument(
        doc_id=source.id,
        version=raw.version,
        regulator=source.regulator,
        doc_type=source.doc_type,
        title=source.title,
        url=raw.parts[0].url,
        topics=list(source.topics),
        applies_to=list(source.applies_to),
        issue_date=source.issue_date,
    )


def parse_version(source: SourceDoc, raw: RawVersion, raw_dir: Path) -> ParsedDocument:
    doc = _base(source, raw)
    snapshot = next((s for s in source.snapshots if raw.version == f"v{s.label.isoformat()}"), None)
    first = raw_dir / raw.parts[0].path
    if source.kind == "fca_chapter":
        doc.paragraphs = [
            p for part in raw.parts for p in parse_fca_section((raw_dir / part.path).read_bytes())
        ]
        dates = [p.effective_from for p in doc.paragraphs if p.effective_from]
        doc.version_date = max(dates) if dates else None
        code = FCA_CHAPTER_CODE.match(doc.paragraphs[0].ref) if doc.paragraphs else None
        doc.doc_number = code.group(1) if code else None
        doc.url = raw.parts[0].url.rsplit("/", 1)[0]  # the chapter, not its first section
    elif source.kind == "pra_part":
        _, doc.paragraphs = parse_pra_part(first.read_bytes())
        as_at = _version_label_date(raw.version)
        dates = [p.effective_from for p in doc.paragraphs if p.effective_from]
        # the version in force on the as-at date started at the latest rule change before it
        doc.version_date = max((d for d in dates if as_at is None or d <= as_at), default=None)
        doc.doc_number = f"PRA Rulebook: {source.title.split(' - ')[-1]}"
    elif first.suffix == ".pdf":
        first_page, doc.paragraphs = parse_pdf(first.read_bytes())
        doc.doc_number = _doc_number(first_page)
        dates = find_dates(first_page)
        doc.version_date = snapshot.label if snapshot else (dates[0] if dates else None)
    else:
        header, doc.paragraphs = parse_rbi_html(first.read_bytes())
        doc.title = header.title or doc.title
        doc.doc_number = header.doc_number
        doc.issue_date = doc.issue_date or header.issue_date
        doc.version_date = header.version_date or header.issue_date
    if snapshot is not None:
        doc.effective_from = snapshot.effective_from or snapshot.label
    elif raw.version == "current" and source.effective_from:
        doc.effective_from = source.effective_from
    else:
        doc.effective_from = doc.version_date or doc.issue_date
    if len(doc.paragraphs) < MIN_PARAGRAPHS:
        raise ValueError(f"{doc.key}: only {len(doc.paragraphs)} paragraphs parsed")
    return doc


def parse_all(raw_dir: Path, sources_path: Path) -> list[ParsedDocument]:
    sources = load_sources(sources_path)
    known = {d.id for d in sources.documents}
    documents = []
    for raw in read_manifest(raw_dir / "manifest.jsonl"):
        if raw.doc_id not in known:
            continue
        doc = parse_version(sources.by_id(raw.doc_id), raw, raw_dir)
        log.info(
            "parsed", doc=doc.key, paragraphs=len(doc.paragraphs), effective=doc.effective_from
        )
        documents.append(doc)
    return documents


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    documents = parse_all(settings.raw_dir, settings.configs_dir / "sources.yaml")
    out = settings.data_dir / "processed" / "documents"
    shutil.rmtree(out, ignore_errors=True)
    save_documents(documents, out)
    total = sum(len(d.paragraphs) for d in documents)
    log.info("parse_done", documents=len(documents), paragraphs=total, folder=str(out))


if __name__ == "__main__":
    main()
