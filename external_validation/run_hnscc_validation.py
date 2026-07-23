#!/usr/bin/env python3
"""Run HNSCC external validation (Prompt B)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "external_validation" / "data" / "hnscc"
sys.path.insert(0, str(ROOT / "engine"))
sys.path.insert(0, str(ROOT / "clinical"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=DATA)
    parser.add_argument("--clinical", type=Path, default=DATA / "clinical")
    parser.add_argument("--mode", choices=("basic", "advanced"), default="basic")
    parser.add_argument("--output", type=Path, default=DATA / "reports")
    args = parser.parse_args()

    xlsx = None
    if args.clinical.is_dir():
        files = list(args.clinical.glob("*.xlsx")) + list(args.clinical.glob("*.xls"))
        xlsx = files[0] if files else None
    elif args.clinical.is_file():
        xlsx = args.clinical

    from validation.hnscc_external_val import run_hnscc_external_validation

    run_hnscc_external_validation(args.data_root, xlsx, args.output, mode=args.mode)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
