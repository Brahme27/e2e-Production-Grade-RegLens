"""Write docs/RESULTS.md from the evaluation reports (every README number comes from here)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from reglens.config import Settings, get_settings
from reglens.log import configure_logging, get_logger

log = get_logger(__name__)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def _f(value: Any, digits: int = 3) -> str:
    return "—" if value is None else f"{value:.{digits}f}"


def _pct(value: Any) -> str:
    return "—" if value is None else f"{value * 100:.0f}%"


def corpus_section(settings: Settings) -> list[str]:
    validity = _load(settings.data_dir / "processed" / "validity.json") or {}
    docs = settings.data_dir / "processed" / "documents"
    paragraphs = 0
    regulators: Counter[str] = Counter()
    for path in docs.glob("*.json") if docs.exists() else []:
        record = json.loads(path.read_text(encoding="utf-8"))
        paragraphs += len(record["paragraphs"])
        regulators[record["regulator"]] += 1
    statuses = Counter(v["status"] for v in validity.values())
    return [
        "## Corpus",
        "",
        f"- **{len({k.split('@')[0] for k in validity})} documents, {len(validity)} versions, {paragraphs:,} paragraphs** "
        f"({', '.join(f'{r} {n}' for r, n in sorted(regulators.items()))} versions)",
        f"- Status today: {statuses.get('current', 0)} current, {statuses.get('superseded', 0)} superseded, "
        f"{statuses.get('future', 0)} future",
        "",
    ]


def ablation_section(report: list[dict[str, Any]] | None) -> list[str]:
    if not report:
        return []
    lines = [
        "## Retrieval ablation (golden set, answerable questions)",
        "",
        "| Row | Pipeline | Recall@10 | nDCG@10 | MRR | Stale in top 5 | p95 latency |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in report:
        o = row["overall"]
        n = f" (n={o['n']})" if o["n"] < 100 else ""  # noqa: PLR2004 - subset experiments
        lines.append(
            f"| {row['key']} | {row['label']}{n} | {_f(o['recall@10'])} | {_f(o['ndcg@10'])} | {_f(o['mrr'])} | "
            f"{_pct(o['stale_in_top5_rate'])} | {row['latency_ms']['p95']:,} ms |"
        )
    final = next((r for r in report if r["key"] == "G"), None)
    if final:
        lines += [
            "",
            "Production row by question type:",
            "",
            "| Type | n | Recall@10 | nDCG@10 |",
            "|---|---|---|---|",
        ]
        for category, o in final["by_category"].items():
            lines.append(f"| {category} | {o['n']} | {_f(o['recall@10'])} | {_f(o['ndcg@10'])} |")
    return [*lines, ""]


def generation_section(
    report: dict[str, Any] | None, abstention: dict[str, Any] | None
) -> list[str]:
    if not report:
        return []
    lines = [
        "## Answers (LLM judge, stratified subset)",
        "",
        "| Metric | Final pipeline | Naive pipeline (row A, no guardrails) |",
        "|---|---|---|",
    ]
    final = report.get("final", {}).get("summary", {})
    naive = report.get("naive", {}).get("summary", {})
    for key, label in [
        ("faithfulness", "Faithfulness (sentences supported by the sources)"),
        ("citation_precision", "Citation precision (cited source supports the sentence)"),
        ("answer_relevancy", "Answer relevancy"),
        ("judged", "Answers the judge scored (the n behind the three rows above)"),
        ("verifier_pass_rate", "Built-in citation verifier pass rate"),
        ("temporal_correctness", "Temporal correctness (all citations valid on the date)"),
        ("abstention_accuracy", "Abstention on unanswerable questions"),
        ("refusal_accuracy", "Refusal on adversarial prompts"),
        ("false_abstention_rate", "False abstention on answerable questions"),
        ("latency_p50_ms", "p50 end-to-end latency (ms, uncached)"),
        ("latency_p95_ms", "p95 end-to-end latency (ms, uncached)"),
        ("n", "Questions"),
    ]:
        digits = 0 if key in ("latency_p50_ms", "latency_p95_ms", "n", "judged") else 3
        lines.append(f"| {label} | {_f(final.get(key), digits)} | {_f(naive.get(key), digits)} |")
    if abstention:
        lines += [
            "",
            f"Abstention threshold (reranker score) calibrated on the golden set: {_f(abstention['threshold'])} "
            f"(balanced accuracy {_f(abstention['balanced_accuracy'])}, n={abstention['n']}).",
        ]
    return [*lines, ""]


def other_section(supersession: Any, router: Any, impact: Any) -> list[str]:
    lines = [
        "## Supersession, routing, change impact",
        "",
        "| Capability | Metric | Result |",
        "|---|---|---|",
    ]
    if supersession:
        r, rl = supersession["rules"], supersession["rules_plus_llm"]
        lines.append(
            f"| Supersession extraction ({supersession['gold_edges']} gold edges) "
            f"| F1 rules / rules + LLM | {_f(r['f1'])} / {_f(rl['f1'])} |"
        )
        ri, rli = supersession["rules_internal"], supersession["rules_plus_llm_internal"]
        lines.append(
            f"| Supersession inside the corpus | recall rules / rules + LLM | {_f(ri['recall'])} / {_f(rli['recall'])} |"
        )
    if router:
        lines.append(
            f"| Query router | accuracy on golden set (n={router['golden_n']}) | {_f(router['golden_accuracy'])} |"
        )
    if impact and "extraction" in impact:
        e = impact["extraction"]
        lines.append(
            f"| Obligation extraction | recall / judged precision / F1 | {_f(e['recall'])} / {_f(e['precision'])} / {_f(e['f1'])} |"
        )
    if impact and "gaps" in impact:
        g = impact["gaps"]
        lines.append(
            f"| Gap judgement on planted gaps (n={g['n']}) | accuracy / covered-vs-gap accuracy / Cohen's κ | "
            f"{_f(g['accuracy'])} / {_f(g['gap_detection_accuracy'])} / {_f(g['cohen_kappa'])} |"
        )
        lines += [
            "",
            "Gap judgement confusion matrix (rows = planted truth, columns = judge):",
            "",
            "| | covered | partially | not covered |",
            "|---|---|---|---|",
        ]
        for truth, row in g["confusion"].items():
            lines.append(
                f"| {truth} | {row['covered']} | {row['partially_covered']} | {row['not_covered']} |"
            )
    return [*lines, ""]


def usage_section(settings: Settings) -> list[str]:
    path = settings.artifacts_dir / "llm-usage.jsonl"
    if not path.exists():
        return []
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    by_purpose: dict[str, list[int]] = {}
    for r in rows:
        item = by_purpose.setdefault(r["purpose"] or "other", [0, 0, 0])
        item[0] += 1
        item[1] += r["prompt_tokens"]
        item[2] += r["completion_tokens"]
    lines = [
        "## LLM usage to build and evaluate everything (free tier, $0)",
        "",
        "| Purpose | Calls | Prompt tokens | Completion tokens |",
        "|---|---|---|---|",
    ]
    for purpose, (calls, prompt, completion) in sorted(
        by_purpose.items(), key=lambda kv: -kv[1][0]
    ):
        lines.append(f"| {purpose} | {calls} | {prompt:,} | {completion:,} |")
    total = [sum(v[i] for v in by_purpose.values()) for i in range(3)]
    lines.append(f"| **total** | **{total[0]}** | **{total[1]:,}** | **{total[2]:,}** |")
    return [*lines, ""]


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    reports = settings.reports_dir
    lines = [
        "# RegLens results",
        "",
        f"_Generated by `uv run poe results` on {date.today().isoformat()} from `artifacts/reports/`. "
        "Do not edit by hand._",
        "",
        *corpus_section(settings),
        *ablation_section(_load(reports / "ablation.json")),
        *generation_section(
            _load(reports / "generation_eval.json"), _load(reports / "abstention.json")
        ),
        *other_section(
            _load(reports / "supersession_eval.json"),
            _load(reports / "router_eval.json"),
            _load(reports / "impact_eval.json"),
        ),
        *usage_section(settings),
    ]
    out = Path(settings.evals_dir).parent / "docs" / "RESULTS.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    log.info("results_written", path=str(out))


if __name__ == "__main__":  # pragma: no cover
    main()
