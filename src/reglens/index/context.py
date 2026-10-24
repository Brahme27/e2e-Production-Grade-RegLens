"""Contextual retrieval: give every chunk the context a reader would have.

A paragraph like "The bank shall review it at least annually." is unsearchable on its own.
Anthropic's "contextual retrieval" prepends a short, chunk-specific context before
embedding. Calling an LLM per chunk (~6,000 calls) does not fit a free tier
(1,000 requests/day), so we build the context in two cheap layers:

1. **structural header** (free): regulator, document, number, heading path, paragraph ref;
2. **document summary** (one LLM call per document, 37 calls): what the document is about
   and who it applies to.

Both are measured separately in the ablation (rows E1 and E2).
"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from reglens.index.chunking import Chunk
from reglens.llm.client import LLMClient, LLMUnavailableError
from reglens.log import get_logger
from reglens.parse.model import ParsedDocument
from reglens.temporal.supersession import latest_versions

log = get_logger(__name__)

ContextMode = Literal["none", "structural", "structural+summary"]
SUMMARY_INPUT_WORDS = 700
SUMMARY_HEADINGS = 40

SUMMARY_SYSTEM = (
    "You write retrieval context for regulatory documents. In at most two sentences say "
    "what the document covers and which firms it applies to. Be specific and factual; "
    'no preamble. Reply as JSON: {"summary": "..."}'
)


def structural_header(chunk: Chunk) -> str:
    kind = chunk.doc_type.replace("_", " ")
    name = f"{chunk.title} ({chunk.doc_number})" if chunk.doc_number else chunk.title
    path = " > ".join(chunk.section_path)
    header = f"{chunk.regulator} {kind}: {name}."
    if path:
        header += f" Section: {path}."
    return header + f" Paragraph {chunk.ref}."


def _summary_prompt(doc: ParsedDocument) -> str:
    headings = list(dict.fromkeys(h for p in doc.paragraphs for h in p.section_path))
    words: list[str] = []
    for para in doc.paragraphs:
        words.extend(para.text.split())
        if len(words) >= SUMMARY_INPUT_WORDS:
            break
    return (
        f"Regulator: {doc.regulator}\nTitle: {doc.title}\n"
        f"Applies to (our tags): {', '.join(doc.applies_to)}\n"
        f"Headings: {'; '.join(headings[:SUMMARY_HEADINGS])}\n"
        f"Opening text: {' '.join(words[:SUMMARY_INPUT_WORDS])}"
    )


def document_summaries(documents: list[ParsedDocument], llm: LLMClient) -> dict[str, str]:
    """One short summary per document (latest version), cached by the LLM client."""
    summaries: dict[str, str] = {}
    for doc_id, doc in sorted(latest_versions(documents).items()):
        messages = [
            {"role": "system", "content": SUMMARY_SYSTEM},
            {"role": "user", "content": _summary_prompt(doc)},
        ]
        try:
            answer = llm.complete_json(
                messages, alias="fast-small", max_tokens=400, purpose="doc_summary"
            )
        except (LLMUnavailableError, ValueError) as exc:
            log.warning("summary_failed", doc=doc_id, error=str(exc))
            continue
        summary = str(answer.get("summary", "")).strip()
        if summary:
            summaries[doc_id] = summary
    return summaries


def add_context(
    chunks: list[Chunk], mode: ContextMode, summaries: dict[str, str] | None = None
) -> list[Chunk]:
    if mode == "none":
        return chunks
    summaries = summaries or {}
    contextualised = []
    for chunk in chunks:
        context = structural_header(chunk)
        if mode == "structural+summary" and chunk.doc_id in summaries:
            context = f"{context} Document context: {summaries[chunk.doc_id]}"
        contextualised.append(replace(chunk, context=context))
    return contextualised
