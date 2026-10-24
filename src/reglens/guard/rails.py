"""Guardrails: what we refuse to process, and what we refuse to pass to the model.

Input rails (before retrieval)
1. **sanitise**: strip hidden instructions (HTML comments, fake "SYSTEM:" prefixes) that
   ride along with a legitimate question;
2. **injection / jailbreak**: Llama Prompt Guard 2 (86M, hosted free on Groq) scores the
   sanitised text; offline we fall back to patterns;
3. **harmful intent**: requests to evade KYC/AML controls, forge documents or phish
   are refused, however politely phrased;
4. **off-topic** is decided by the router (route ``out_of_scope``).

Context rail (after retrieval): retrieved text is untrusted data. A passage that contains
instructions aimed at the model is dropped before generation (indirect prompt injection,
OWASP LLM01).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from reglens.index.store import Hit
from reglens.llm.client import LLMClient, LLMUnavailableError
from reglens.log import get_logger

log = get_logger(__name__)

Verdict = Literal["allow", "refuse_injection", "refuse_harmful", "refuse_off_topic"]

HIDDEN_INSTRUCTIONS = re.compile(
    r"<!--.*?-->|\[\[.*?\]\]|^\s*(?:system|assistant|developer)\s*:.*?(?:\.|$)", re.I | re.S | re.M
)
INJECTION_PATTERNS = re.compile(
    r"ignore (?:all |any |the )?(?:previous|prior|above|your) (?:instructions|rules|prompt)"
    r"|(?:reveal|print|show|repeat|translate) (?:me )?(?:your|the) (?:system|hidden) (?:prompt|instructions)"
    r"|\b(?:developer|god|jailbreak|dan) mode\b|you are now (?:dan|an ai without)"
    r"|disable (?:citations|safety|your rules)|stop citing"
    r"|other users'? (?:questions|data)",
    re.I,
)
HARMFUL_PATTERNS = re.compile(
    r"\b(?:launder\w*|money mule|mule accounts?|evade|evading|bypass\w*|get around|avoid (?:detection|triggering|reporting))\b"
    r"|\bfake (?:kyc|identity|id|document)|forg(?:e|ed|ery) (?:a |the )?(?:document|kyc|id)"
    r"|\bphishing\b|stay (?:just )?below (?:the )?(?:reporting|threshold)|split transactions"
    r"|hidden fees|customers won'?t notice|without authori[sz]ation|scrape customer data",
    re.I,
)
PROMPT_GUARD_ALIAS = "prompt-guard"
PROMPT_GUARD_THRESHOLD = 0.8

REFUSALS = {
    "refuse_injection": (
        "I can't follow instructions that try to change how I work. "
        "Please ask a question about RBI, SEBI, FCA or PRA regulation."
    ),
    "refuse_harmful": "I can't help with that. RegLens supports compliance with regulation, not ways around it.",
    "refuse_off_topic": "I can only help with questions about RBI, SEBI, FCA and PRA regulation in the indexed documents.",
}


@dataclass(frozen=True)
class InputCheck:
    verdict: Verdict
    question: str  # sanitised text to use downstream
    removed: bool  # hidden instructions were stripped
    injection_score: float | None = None
    detector: str = "patterns"

    @property
    def allowed(self) -> bool:
        return self.verdict == "allow"

    @property
    def message(self) -> str:
        return REFUSALS.get(self.verdict, "")


def sanitise(text: str) -> tuple[str, bool]:
    cleaned = HIDDEN_INSTRUCTIONS.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned, cleaned != re.sub(r"\s+", " ", text).strip()


def prompt_guard_score(text: str, llm: LLMClient | None) -> float | None:
    """Probability (0-1) that the text is a prompt attack, from Llama Prompt Guard 2."""
    if llm is None:
        return None
    try:
        response = llm.complete(
            [{"role": "user", "content": text}],
            alias=PROMPT_GUARD_ALIAS,
            max_tokens=8,
            purpose="prompt_guard",
        )
        return float(response.text.strip())
    except (LLMUnavailableError, ValueError) as exc:
        log.warning("prompt_guard_unavailable", error=str(exc))
        return None


def check_input(question: str, llm: LLMClient | None = None) -> InputCheck:
    cleaned, removed = sanitise(question)
    if not cleaned:
        return InputCheck("refuse_injection", cleaned, removed)
    if HARMFUL_PATTERNS.search(cleaned):
        return InputCheck("refuse_harmful", cleaned, removed)
    if INJECTION_PATTERNS.search(cleaned):
        return InputCheck("refuse_injection", cleaned, removed)
    score = prompt_guard_score(cleaned, llm)
    if score is not None and score >= PROMPT_GUARD_THRESHOLD:
        return InputCheck("refuse_injection", cleaned, removed, score, "prompt-guard-2")
    return InputCheck(
        "allow", cleaned, removed, score, "prompt-guard-2" if score is not None else "patterns"
    )


CONTEXT_INJECTION = re.compile(
    r"ignore (?:all |any )?(?:previous|prior|above) instructions|you (?:are|must) now|"
    r"(?:assistant|ai|model|chatbot)s? (?:must|should) (?:say|answer|respond|reply)|"
    r"disregard (?:the|your) (?:system|instructions)|<\s*/?\s*(?:system|instructions?)\s*>",
    re.I,
)


def filter_context(hits: list[Hit]) -> tuple[list[Hit], list[Hit]]:
    """Split retrieved hits into (safe, suspicious): suspicious ones never reach the model."""
    safe: list[Hit] = []
    suspicious: list[Hit] = []
    for hit in hits:
        (suspicious if CONTEXT_INJECTION.search(hit.chunk.text) else safe).append(hit)
    if suspicious:
        log.warning("context_injection_dropped", chunks=[h.chunk.chunk_id for h in suspicious])
    return safe, suspicious
