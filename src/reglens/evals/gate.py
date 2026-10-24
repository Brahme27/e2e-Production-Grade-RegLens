"""CI quality gate: fail the build if retrieval quality drops versus the committed baseline.

``evals/baseline.json`` holds the numbers of the production row (G) when the baseline was
last accepted. CI re-runs the retrieval ablation for row G (no LLM needed) and fails if any
metric falls by more than the allowed margin (3 points), or if stale passages reappear.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from reglens.config import get_settings

MARGIN = 0.03
METRICS = ("recall@10", "ndcg@10", "mrr")


def compare(current: dict[str, Any], baseline: dict[str, Any], margin: float = MARGIN) -> list[str]:
    failures = []
    for metric in METRICS:
        if current[metric] < baseline[metric] - margin:
            failures.append(
                f"{metric} {current[metric]:.3f} < baseline {baseline[metric]:.3f} - {margin}"
            )
    if current["stale_in_top5_rate"] > baseline["stale_in_top5_rate"]:
        failures.append(f"stale passages in top 5 rose to {current['stale_in_top5_rate']:.3f}")
    return failures


def row(report: list[dict[str, Any]], key: str) -> dict[str, Any]:
    for item in report:
        if item["key"] == key:
            overall: dict[str, Any] = item["overall"]
            return overall
    raise KeyError(key)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Retrieval quality gate")
    parser.add_argument("--row", default="G")
    parser.add_argument(
        "--update", action="store_true", help="accept current numbers as the new baseline"
    )
    args = parser.parse_args(argv)
    settings = get_settings()
    report = json.loads((settings.reports_dir / "ablation.json").read_text(encoding="utf-8"))
    current = row(report, args.row)
    baseline_path: Path = settings.evals_dir / "baseline.json"
    if args.update or not baseline_path.exists():
        keep = {k: current[k] for k in (*METRICS, "stale_in_top5_rate", "n")}
        baseline_path.write_text(
            json.dumps({"row": args.row, **keep}, indent=1) + "\n", encoding="utf-8"
        )
        print(f"baseline written: {keep}")
        return 0
    failures = compare(current, json.loads(baseline_path.read_text(encoding="utf-8")))
    for failure in failures:
        print(f"QUALITY GATE FAILED: {failure}")
    if not failures:
        print(f"quality gate passed: {[f'{m}={current[m]:.3f}' for m in METRICS]}")
    return 1 if failures else 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
