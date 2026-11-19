"""CLI entry point for python -m tools.datagen."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from tools.datagen.generator import check_determinism_and_correctness, generate_documents
from tools.datagen.replay import generate_all_replay_fixtures

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("tools.datagen")

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = _REPO_ROOT / "tools" / "datagen" / "out"
DEFAULT_TRUTH_DIR = _REPO_ROOT / "eval" / "data" / "truth"
DEFAULT_REPLAY_DIR = _REPO_ROOT / "eval" / "data" / "replay"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic procurement document generator and verifier."
    )
    parser.add_argument(
        "--out",
        type=str,
        default=str(DEFAULT_OUT_DIR),
        help=f"Output directory for generated PDFs and PNGs (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--truth-dir",
        type=str,
        default=str(DEFAULT_TRUTH_DIR),
        help=f"Optional directory to save ground-truth JSON files (default: {DEFAULT_TRUTH_DIR})",
    )
    parser.add_argument(
        "--replay",
        action="store_true",
        help="Also generate replay fixtures into eval/data/replay",
    )
    parser.add_argument(
        "--replay-dir",
        type=str,
        default=str(DEFAULT_REPLAY_DIR),
        help=f"Output directory for replay fixtures (default: {DEFAULT_REPLAY_DIR})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run verification checks: determinism, footers, arithmetic, denylist",
    )

    args = parser.parse_args()

    # If --check is passed alone without generating docs
    only_check = (
        args.check
        and not args.replay
        and "--out" not in sys.argv
        and "--truth-dir" not in sys.argv
        and len(sys.argv) == 2
    )
    if only_check:
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
    print(
        json.dumps(
            {k: {"sha256": v["sha256"], "type": v["doc_type"]} for k, v in results.items()},
            indent=2,
        )
    )

    if args.replay:
        replay_dir = Path(args.replay_dir)
        logger.info("Generating replay fixtures into '%s'...", replay_dir)
        fixture_count = generate_all_replay_fixtures(out_dir=replay_dir)
        print(f"Generated {fixture_count} replay fixture pairs into {replay_dir}")

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

    return 0


if __name__ == "__main__":
    sys.exit(main())
