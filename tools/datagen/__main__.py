"""CLI entry point for python -m tools.datagen."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from tools.datagen.generator import check_determinism_and_correctness, generate_documents

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tools.datagen")


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic procurement document generator and verifier.")
    parser.add_argument(
        "--out",
        type=str,
        default="tools/datagen/out",
        help="Output directory for generated PDFs and PNGs (default: tools/datagen/out)",
    )
    parser.add_argument(
        "--truth-dir",
        type=str,
        default="eval/data/truth",
        help="Optional directory to also save ground-truth JSON files (default: eval/data/truth)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run verification checks: determinism, footers, arithmetic, denylist",
    )

    args = parser.parse_args()

    if args.check:
        logger.info("Executing verification suite (--check)...")
        try:
            passed = check_determinism_and_correctness()
            if passed:
                print("SUCCESS: All verification checks passed.")
                return 0
            else:
                print("FAILURE: Verification failed.")
                return 1
        except Exception:
            logger.exception("Verification check error encountered")
            return 1

    out_dir = Path(args.out)
    truth_dir = Path(args.truth_dir) if args.truth_dir else None
    logger.info("Generating scenario documents into '%s'...", out_dir)

    results = generate_documents(out_dir=out_dir, truth_dir=truth_dir)
    print(f"Generated {len(results)} documents into {out_dir}")
    print(json.dumps({k: {"sha256": v["sha256"], "type": v["doc_type"]} for k, v in results.items()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
