"""The question-answering service: every request goes through the same steps.

    guard -> semantic cache -> retrieve (route, filters, rerank) -> context rail
          -> generate (streamed) -> verify citations -> cache + trace

Used by the API (streaming and JSON) and by the generation evaluation, so what we
measure is exactly what users get.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from reglens.cache.semantic import SemanticCache
from reglens.generate.answer import Answer, Answerer
from reglens.guard.rails import REFUSALS, check_input, filter_context
from reglens.llm.client import LLMClient
from reglens.obs.tracing import Tracer
from reglens.retrieve.pipeline import RetrievalConfig, RetrievalResult, Retriever
from reglens.retrieve.query import analyse

DISCLAIMER = "Information only, not legal advice. Always check the cited source."


@dataclass(frozen=True)
class AskRequest:
    question: str
    as_of: date | None = None
    regulators: tuple[str, ...] = ()


def answer_to_dict(answer: Answer) -> dict[str, Any]:
    verification = answer.verification
    return {
        "question": answer.question,
        "text": answer.text,
        "abstained": answer.abstained,
        "reason": answer.reason,
        "route": answer.route,
        "as_of": answer.as_of.isoformat() if answer.as_of else None,
        "citations": [asdict(c) for c in answer.citations],
        "verification": None
        if verification is None
        else {
            "ok": verification.ok,
            "uncited_sentences": verification.uncited,
            "unsupported_sentences": verification.unsupported,
            "invalid_markers": list(verification.invalid_markers),
            "sentences": [asdict(s) for s in verification.sentences],
        },
        "prompt_version": answer.prompt_version,
        "disclaimer": DISCLAIMER,
    }


def _sources(result: RetrievalResult) -> list[dict[str, Any]]:
    return [
        {
            "number": i,
            "label": h.chunk.citation,
            "doc_id": h.chunk.doc_id,
            "doc_key": h.chunk.doc_key,
            "ref": h.chunk.ref,
            "regulator": h.chunk.regulator,
            "title": h.chunk.title,
            "status": h.chunk.status,
            "score": round(h.score, 4),
        }
        for i, h in enumerate(result.hits, start=1)
    ]


class QAService:
    def __init__(
        self,
        retriever: Retriever,
        answerer: Answerer,
        tracer: Tracer,
        cache: SemanticCache | None,
        config: RetrievalConfig,
        *,
        guard_llm: LLMClient | None = None,
    ) -> None:
        self.retriever = retriever
        self.answerer = answerer
        self.tracer = tracer
        self.cache = cache
        self.config = config
        self.guard_llm = guard_llm

    def ask_stream(self, request: AskRequest) -> Iterator[dict[str, Any]]:
        trace = self.tracer.start(
            "ask", request.question, as_of=str(request.as_of), regulators=list(request.regulators)
        )
        final: dict[str, Any] | None = None
        try:
            for event in self._steps(request, trace):
                if event["type"] == "final":
                    final = event["answer"]
                yield event
        finally:
            self.tracer.finish(trace, final)

    def ask(self, request: AskRequest) -> dict[str, Any]:
        answer: dict[str, Any] = {}
        for event in self.ask_stream(request):
            if event["type"] == "final":
                answer = event["answer"]
        return answer

    def _refusal(self, request: AskRequest, verdict: str, trace_id: str) -> dict[str, Any]:
        return {
            "type": "final",
            "answer": {
                "question": request.question,
                "text": REFUSALS[verdict],
                "abstained": True,
                "reason": verdict,
                "route": "refused",
                "as_of": None,
                "citations": [],
                "verification": None,
                "disclaimer": DISCLAIMER,
                "trace_id": trace_id,
                "cached": False,
            },
        }

    def _steps(self, request: AskRequest, trace: Any) -> Iterator[dict[str, Any]]:
        yield {"type": "meta", "trace_id": trace.id}
        with trace.span("guard", request.question) as span:
            check = check_input(request.question, self.guard_llm)
            span.output = {
                "verdict": check.verdict,
                "score": check.injection_score,
                "sanitised": check.removed,
            }
        if not check.allowed:
            yield self._refusal(request, check.verdict, trace.id)
            return
        question = check.question
        signals = analyse(question)
        as_of = request.as_of or signals.as_of
        regulators = request.regulators or signals.regulators

        embedding: list[float] = []
        if self.cache is not None:
            with trace.span("cache") as span:
                embedding = self.retriever.embedder.dense_query(question)
                hit = self.cache.get(embedding, as_of, regulators)
                span.output = {"hit": hit is not None}
            if hit is not None:
                yield {
                    "type": "final",
                    "answer": {**hit.answer, "trace_id": trace.id, "cached": True},
                }
                return

        with trace.span("retrieve", question) as span:
            result = self.retriever.retrieve(
                question, self.config, as_of=as_of, regulators=regulators
            )
            span.output = {
                "route": result.route,
                "as_of": str(result.as_of),
                "hits": [h.chunk.chunk_id for h in result.hits],
            }
            span.metadata = {"timings_ms": result.timings_ms}
        if result.route == "out_of_scope":
            yield self._refusal(request, "refuse_off_topic", trace.id)
            return
        safe, dropped = filter_context(result.hits)
        result.hits = safe
        yield {
            "type": "sources",
            "route": result.route,
            "as_of": str(result.as_of),
            "sources": _sources(result),
            "dropped": len(dropped),
        }

        with trace.span("generate", kind="generation") as span:
            final_answer: Answer | None = None
            for item in self.answerer.stream(result):
                if isinstance(item, Answer):
                    final_answer = item
                else:
                    yield {"type": "delta", "text": item}
            if final_answer is None:  # the answerer always ends with an Answer
                raise RuntimeError("answer stream ended without a final answer")
            span.output = final_answer.text
            span.metadata = {"model": self.answerer.alias, "abstained": final_answer.abstained}
        payload = answer_to_dict(final_answer) | {"trace_id": trace.id, "cached": False}
        if self.cache is not None and not final_answer.abstained and embedding:
            self.cache.put(embedding, as_of, regulators, payload)
        yield {"type": "final", "answer": payload}
