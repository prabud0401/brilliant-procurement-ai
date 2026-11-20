"""CLI entry point for running the AI Quality evaluation suite (make eval).

Usage:
    python -m eval.run [--mode replay|live] [--out eval/reports/<timestamp>] [--confirm-live] [--max-cost-usd 0.50]
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _REPO_ROOT / "services" / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import argparse
import json
import logging
from datetime import datetime, timezone

from eval.runner import EvaluationRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval.run")

_REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the AI Quality Evaluation Suite across all AIQ-01 to AIQ-10 metrics."
    )
    parser.add_argument(
        "--mode",
        choices=["replay", "live"],
        default="replay",
        help="Evaluation mode: 'replay' (offline mock/replay, default) or 'live' (live Azure calls)",
    )
    parser.add_argument(
        "--out",
        type=str,
        default=None,
        help="Output directory to write report.json and report.md (default: eval/reports/<timestamp>)",
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Explicit confirmation required to run live evaluation (which incurs cost)",
    )
    parser.add_argument(
        "--max-cost-usd",
        type=float,
        default=0.50,
        help="Maximum allowable AI budget in USD for live evaluation (default: 0.50)",
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default=str(_REPO_ROOT / "eval" / "data"),
        help="Path to evaluation data directory containing truth, replay, and questions",
    )

    args = parser.parse_args()

    # Determine report output directory
    if args.out:
        out_dir = Path(args.out)
    else:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        out_dir = _REPO_ROOT / "eval" / "reports" / ts

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        runner = EvaluationRunner(
            mode=args.mode,
            data_dir=args.data_dir,
            max_cost_usd=args.max_cost_usd,
            confirm_live=args.confirm_live,
        )

        if args.mode == "live":
            est_cost = runner.estimate_live_cost_usd()
            print("==================================================")
            print(f"LIVE EVALUATION RUN CONFIRMED: Estimated Cost ~${est_cost:.4f} USD")
            print("==================================================")

        report = runner.run()

    except Exception as exc:
        print(f"\nEvaluation failed with error: {exc}", file=sys.stderr)
        return 1

    # Write report.json and report.md
    json_path = out_dir / "report.json"
    md_path = out_dir / "report.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report.to_markdown())

    # Print summary table to stdout
    print("\n" + report.to_markdown() + "\n")
    print(f"Reports written to: {out_dir}")
    print(f"  - JSON: {json_path}")
    print(f"  - Markdown: {md_path}")

    if not report.all_passed:
        failed_list = [m.id for m in report.metrics if not m.passed]
        print(f"\nFAILURE: {len(failed_list)} metric(s) fell below target: {failed_list}", file=sys.stderr)
        return 1

    print("\nSUCCESS: All AI Quality metrics met or exceeded target thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
