#!/usr/bin/env python3
"""Build a PHI-safe inventory of local test data folders (paths + counts only)."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_INPUT_ROOT = Path(r"C:\Users\Sampa\OneDrive\Desktop\input_folders")

SKIP_DIR_NAMES = {
    "_validation_engine_adv",
    "_validation_ml_xai_out",
    "_integration_test_output",
    "_test_preprocess_out",
    "__pycache__",
    ".git",
}


def _folder_stats(root: Path) -> dict:
    if not root.is_dir():
        return {"exists": False}
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for name in filenames:
            p = Path(dirpath) / name
            try:
                files.append(p)
            except OSError:
                continue
    total_bytes = sum(f.stat().st_size for f in files if f.is_file())
    ext_counts: dict[str, int] = {}
    for f in files:
        ext = f.suffix.lower() or "(no ext)"
        ext_counts[ext] = ext_counts.get(ext, 0) + 1
    top_dirs = sorted(
        {str(p.relative_to(root).parts[0]) for p in files if p.relative_to(root).parts},
    )
    return {
        "exists": True,
        "file_count": len(files),
        "total_bytes": total_bytes,
        "total_mb": round(total_bytes / (1024 * 1024), 2),
        "extensions": dict(sorted(ext_counts.items())),
        "top_level_entries": top_dirs,
    }


def build_inventory(input_root: Path | None = None) -> dict:
    root = input_root or DEFAULT_INPUT_ROOT
    cohorts = {}
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if child.is_dir():
                cohorts[child.name] = _folder_stats(child)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_root": str(root),
        "note": "Counts only — no patient identifiers or file contents.",
        "cohorts": cohorts,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="Root folder containing rbgyanx_test_data and related cohorts",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "reproducibility" / "DATA_INVENTORY.json",
    )
    args = parser.parse_args()
    inv = build_inventory(args.input_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(inv, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
