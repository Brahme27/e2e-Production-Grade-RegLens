"""Obligation extraction and gap judgement (the two LLM steps of change impact).

An **obligation** is one thing a regulated firm must (or must not) do, in a fixed schema:
``{id, text, actor, action, condition, deadline, source_ref, severity}``.

A **gap judgement** compares one obligation with the firm's most relevant policy clauses:
``covered | partially_covered | not_covered`` plus a rationale and the clauses relied on.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, cast

from reglens.index.store import Hit
from reglens.llm.client import LLMClient, LLMUnavailableError
from reglens.log import get_logger
from reglens.parse.model import Paragraph

log = get_logger(__name__)

GapStatus = Literal["covered", "partially_covered", "not_covered"]
GAP_STATUSES: tuple[GapStatus, ...] = ("covered", "partially_covered", "not_covered")
PARAGRAPHS_PER_CALL = 3
EXTRACT_PROMPT_VERSION = "obligations-v1"
GAP_PROMPT_VERSION = "gap-v1"

EXTRACT_SYSTEM = """You extract regulatory obligations for a compliance team.
From the numbered regulation paragraphs, list every distinct obligation: something a regulated
firm (or its board, staff, officers) MUST or MUST NOT do. Split compound paragraphs into separate
obligations when they require different actions. Skip definitions, applicability statements,
descriptions of what the regulator may do, and purely permissive statements ("may").
For each obligation give:
- "text": the obligation in one plain-English sentence, keeping numbers and deadlines exact
- "actor": who must act; "action": the required action; "condition": when it applies ("" if always)
- "deadline": any time limit or frequency ("" if none)
- "source_ref": the paragraph number it comes from, exactly as given
- "severity": high (customer harm / regulatory breach), medium, or low (administrative)
Reply as JSON: {"obligations": [ ... ]}"""

GAP_SYSTEM = """You are a compliance analyst checking whether a firm's internal policies meet a
regulatory obligation. Compare the obligation with the policy clauses provided (they are the most
relevant clauses found; they may be irrelevant). Decide:
- "covered": the policy clauses require what the obligation requires, including any numbers,
  frequencies and deadlines (a stricter policy requirement also counts as covered);
- "partially_covered": the policy addresses the topic but misses part of the obligation or uses a
  weaker number, frequency or deadline;
- "not_covered": no clause addresses it, or a clause contradicts it.
Reply as JSON: {"status": "...", "rationale": "<one or two sentences>", "policy_refs": ["<label>", ...], "confidence": 0.0-1.0}"""


@dataclass(frozen=True)
class Obligation:
    id: str
    text: str
    source_ref: str
    actor: str = ""
    action: str = ""
    condition: str = ""
    deadline: str = ""
    severity: str = "medium"


@dataclass(frozen=True)
class GapJudgement:
    obligation_id: str
    status: GapStatus
    rationale: str
    policy_refs: tuple[str, ...] = ()
    confidence: float = 0.0
    evidence: tuple[str, ...] = field(default_factory=tuple)  # clause labels shown to the judge


def obligation_id(doc_key: str, ref: str, text: str) -> str:
    return hashlib.sha1(f"{doc_key}|{ref}|{text}".encode()).hexdigest()[:16]  # noqa: S324


def _batches(paragraphs: list[Paragraph]) -> list[list[Paragraph]]:
    return [
        paragraphs[i : i + PARAGRAPHS_PER_CALL]
        for i in range(0, len(paragraphs), PARAGRAPHS_PER_CALL)
    ]


def extract_obligations(
    doc_key: str, paragraphs: list[Paragraph], llm: LLMClient
) -> list[Obligation]:
    obligations: list[Obligation] = []
    valid_refs = {p.ref for p in paragraphs}
    for batch in _batches(paragraphs):
        text = "\n\n".join(f"[para {p.ref}]\n{p.text}" for p in batch)
        try:
            answer = llm.complete_json(
                [
                    {"role": "system", "content": EXTRACT_SYSTEM},
                    {"role": "user", "content": f"Document: {doc_key}\n\n{text}"},
                ],
                alias="reasoning-large",
                max_tokens=2500,
                purpose="obligations",
            )
        except (LLMUnavailableError, ValueError) as exc:
            log.warning("obligation_extraction_failed", doc=doc_key, error=str(exc))
            continue
        for raw in answer.get("obligations", []):
            ref = str(raw.get("source_ref", "")).replace("para", "").strip()
            sentence = str(raw.get("text", "")).strip()
            if not sentence:
                continue
            if ref not in valid_refs:  # the model must cite one of the paragraphs it was given
                ref = batch[0].ref if len(batch) == 1 else ref
                if ref not in valid_refs:
                    continue
            obligations.append(
                Obligation(
                    id=obligation_id(doc_key, ref, sentence),
                    text=sentence,
                    source_ref=ref,
                    actor=str(raw.get("actor", "")),
                    action=str(raw.get("action", "")),
                    condition=str(raw.get("condition", "")),
                    deadline=str(raw.get("deadline", "")),
                    severity=str(raw.get("severity", "medium")).lower()
                    if raw.get("severity")
                    else "medium",
                )
            )
    return obligations


def _clauses(hits: list[Hit]) -> str:
    return "\n\n".join(
        f"[{h.chunk.doc_number} §{h.chunk.ref}] ({h.chunk.title}, section: {' > '.join(h.chunk.section_path)})\n{h.chunk.text}"
        for h in hits
    )


def judge_gap(obligation: Obligation, policy_hits: list[Hit], llm: LLMClient) -> GapJudgement:
    evidence = tuple(f"{h.chunk.doc_number} §{h.chunk.ref}" for h in policy_hits)
    user = f"Obligation ({obligation.source_ref}): {obligation.text}\n\nPolicy clauses:\n{_clauses(policy_hits) or '(none found)'}"
    try:
        answer = llm.complete_json(
            [{"role": "system", "content": GAP_SYSTEM}, {"role": "user", "content": user}],
            alias="reasoning-large",
            max_tokens=700,
            purpose="gap_judge",
        )
    except (LLMUnavailableError, ValueError) as exc:
        log.warning("gap_judge_failed", obligation=obligation.id, error=str(exc))
        return GapJudgement(
            obligation.id,
            "not_covered",
            "Judge unavailable: needs manual review.",
            (),
            0.0,
            evidence,
        )
    status = str(answer.get("status", "")).strip().lower()
    if status not in GAP_STATUSES:
        status = "not_covered"
    verdict = cast(GapStatus, status)
    refs = tuple(str(r) for r in answer.get("policy_refs", []) if str(r) in evidence)
    try:
        confidence = max(0.0, min(1.0, float(answer.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return GapJudgement(
        obligation.id, verdict, str(answer.get("rationale", "")), refs, confidence, evidence
    )


def to_dict(item: Obligation | GapJudgement) -> dict[str, Any]:
    return asdict(item)
