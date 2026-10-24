"""Evaluate change impact in two independent stages (``evals/impact_gold.yaml``).

Stage 1, obligation extraction on the labelled target paragraphs:
- **recall** vs the hand-labelled obligations (an extracted obligation from the same paragraph
  matches a gold one when their embeddings are similar, cosine >= 0.80);
- **precision** by an LLM judge ("is this a genuine obligation stated in the paragraph?"),
  because the gold list covers the important obligations, not every minor one.

Stage 2, gap judgement on the GOLD obligations (so extraction errors don't leak in):
policy search + judge per obligation, compared with the planted label. Reports accuracy, a
confusion matrix and Cohen's kappa.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from typing import Any

import numpy as np
import yaml

from reglens.config import Settings, get_settings
from reglens.impact.obligations import GAP_STATUSES, Obligation, extract_obligations, judge_gap
from reglens.impact.policies import PolicySearch, index_policies, load_policies
from reglens.index.build import make_embedder
from reglens.index.embed import Embedder
from reglens.llm.client import LLMClient, LLMUnavailableError, build_client
from reglens.log import configure_logging, get_logger
from reglens.parse.model import load_documents
from reglens.retrieve.rerank import Reranker
from reglens.services import build_store

log = get_logger(__name__)

MATCH_COSINE = 0.80
PRECISION_JUDGE = """You check extracted regulatory obligations. Given a regulation paragraph and a
list of obligations extracted from it, decide for each whether it is a genuine obligation (a MUST
or MUST NOT) actually stated in that paragraph, faithfully paraphrased.
Reply as JSON: {"verdicts": [true, false, ...]} in the same order."""


def cohen_kappa(a: Sequence[str], b: Sequence[str], labels: tuple[str, ...]) -> float:
    n = len(a)
    if n == 0:
        return 0.0
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    expected = sum((a.count(lab) / n) * (b.count(lab) / n) for lab in labels)
    return round((observed - expected) / (1 - expected), 3) if expected < 1 else 1.0


def _match(gold: list[dict[str, Any]], predicted: list[Obligation], embedder: Embedder) -> int:
    """Greedy one-to-one matching inside each paragraph by embedding similarity."""
    matched = 0
    for ref in {g["ref"] for g in gold}:
        g_items = [g for g in gold if g["ref"] == ref]
        p_items = [p for p in predicted if p.source_ref == ref]
        if not p_items:
            continue
        g_vec = np.asarray(embedder.dense([g["text"] for g in g_items]))
        p_vec = np.asarray(embedder.dense([p.text for p in p_items]))
        sims = g_vec @ p_vec.T
        used: set[int] = set()
        for gi in np.argsort(-sims.max(axis=1)):
            order = [int(j) for j in np.argsort(-sims[gi]) if int(j) not in used]
            if order and sims[gi, order[0]] >= MATCH_COSINE:
                used.add(order[0])
                matched += 1
    return matched


def _precision(paragraph: str, obligations: list[Obligation], llm: LLMClient) -> list[bool]:
    listing = "\n".join(f"{i + 1}. {o.text}" for i, o in enumerate(obligations))
    try:
        answer = llm.complete_json(
            [
                {"role": "system", "content": PRECISION_JUDGE},
                {"role": "user", "content": f"Paragraph:\n{paragraph}\n\nObligations:\n{listing}"},
            ],
            alias="fallback",
            max_tokens=600,
            purpose="obligation_precision",
            strict=False,
        )
    except (LLMUnavailableError, ValueError):
        return []
    verdicts = [bool(v) for v in answer.get("verdicts", [])]
    return verdicts if len(verdicts) == len(obligations) else []


def stage_one(
    gold: dict[str, Any], settings: Settings, llm: LLMClient, embedder: Embedder
) -> dict[str, Any]:
    documents = {d.key: d for d in load_documents(settings.data_dir / "processed" / "documents")}
    per_target = {}
    totals: Counter[str] = Counter()
    for target in gold["targets"]:
        doc = documents[target["doc_key"]]
        paragraphs = [p for p in doc.paragraphs if p.ref in set(target["paragraphs"])]
        predicted = extract_obligations(doc.key, paragraphs, llm)
        gold_items = [o for o in gold["obligations"] if o["target"] == target["id"]]
        matched = _match(gold_items, predicted, embedder)
        genuine = []
        for para in paragraphs:
            items = [o for o in predicted if o.source_ref == para.ref]
            if items:
                genuine.extend(_precision(para.text, items, llm))
        per_target[target["id"]] = {
            "gold": len(gold_items),
            "extracted": len(predicted),
            "gold_found": matched,
            "recall": round(matched / len(gold_items), 3) if gold_items else None,
            "judged_precision": round(sum(genuine) / len(genuine), 3) if genuine else None,
        }
        totals.update(
            {
                "gold": len(gold_items),
                "found": matched,
                "judged": len(genuine),
                "genuine": sum(genuine),
                "extracted": len(predicted),
            }
        )
    recall = totals["found"] / totals["gold"] if totals["gold"] else 0.0
    precision = totals["genuine"] / totals["judged"] if totals["judged"] else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "recall": round(recall, 3),
        "precision": round(precision, 3),
        "f1": round(f1, 3),
        "extracted": totals["extracted"],
        "by_target": per_target,
    }


def stage_two(gold: dict[str, Any], search: PolicySearch, llm: LLMClient) -> dict[str, Any]:
    entity_of = {t["id"]: t["entity"] for t in gold["targets"]}
    truth, predicted, rows = [], [], []
    for item in gold["obligations"]:
        obligation = Obligation(item["id"], item["text"], item["ref"])
        hits = search.search(item["text"], entity_of[item["target"]])
        verdict = judge_gap(obligation, hits, llm)
        truth.append(item["gap"])
        predicted.append(verdict.status)
        rows.append(
            {
                "id": item["id"],
                "gold": item["gap"],
                "predicted": verdict.status,
                "rationale": verdict.rationale,
                "evidence": list(verdict.evidence[:3]),
            }
        )
    confusion = {
        g: {
            p: sum(1 for t, q in zip(truth, predicted, strict=True) if t == g and q == p)
            for p in GAP_STATUSES
        }
        for g in GAP_STATUSES
    }
    accuracy = sum(t == p for t, p in zip(truth, predicted, strict=True)) / len(truth)
    lenient = sum(
        (t == p) or (t != "covered" and p != "covered")
        for t, p in zip(truth, predicted, strict=True)
    ) / len(truth)
    return {
        "n": len(truth),
        "accuracy": round(accuracy, 3),
        "gap_detection_accuracy": round(lenient, 3),  # covered vs needs-work
        "cohen_kappa": cohen_kappa(truth, predicted, GAP_STATUSES),
        "confusion": confusion,
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Evaluate obligation extraction and gap analysis")
    parser.add_argument("--stages", nargs="*", default=["1", "2"])
    args = parser.parse_args(argv)
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    gold = yaml.safe_load((settings.evals_dir / "impact_gold.yaml").read_text(encoding="utf-8"))
    llm = build_client(settings)
    embedder = make_embedder(settings)
    report: dict[str, Any] = {}
    if "1" in args.stages:
        report["extraction"] = stage_one(gold, settings, llm, embedder)
        log.info(
            "obligation_extraction",
            **{k: v for k, v in report["extraction"].items() if k != "by_target"},
        )
    if "2" in args.stages:
        store = build_store(settings)
        index_policies(store, embedder, load_policies(settings.data_dir / "policies"))
        search = PolicySearch(store, embedder, Reranker("minilm", settings.models_cache_dir))
        report["gaps"] = stage_two(gold, search, llm)
        log.info(
            "gap_judgement",
            **{
                k: v
                for k, v in report["gaps"].items()
                if k in ("n", "accuracy", "gap_detection_accuracy", "cohen_kappa")
            },
        )
    out = settings.reports_dir / "impact_eval.json"
    previous = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(previous | report, indent=1), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
