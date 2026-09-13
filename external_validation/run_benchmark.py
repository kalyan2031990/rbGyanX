"""
Run the Phase-3/4 four-class external-validation benchmark on cohort_features.csv.

Emits, under ``--out-dir``:
  benchmark_<endpoint>_<featureset>.csv   one row per model class
  benchmark_results.json                  all tables + run metadata
  optimism_<endpoint>.png                 apparent-vs-CV AUC (Fig-4 style)

Everything is derived from the reference-planned-dose feature table; frame results
as "association on reference-planned dose" (see docs/EXTVAL_DATA_READINESS.md).

Usage:
    python external_validation/run_benchmark.py \
        --features external_validation/data/cohort_features.csv \
        --out-dir  external_validation/data/benchmark [--seed 0]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from validation.extval_benchmark import run_benchmark  # noqa: E402

_TABLE_COLS = [
    "tier",
    "name",
    "note",
    "apparent_auc",
    "cv_auc",
    "optimism",
    "brier",
    "brier_lo",
    "brier_hi",
    "hosmer_lemeshow_p",
    "ece",
    "calibration_slope",
    "net_benefit",
    "refused",
]


def _optimism_plot(table: pd.DataFrame, endpoint: str, out_png: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    labels = [f"{t}\n{n}" for t, n in zip(table["tier"], table["note"], strict=False)]
    x = range(len(table))
    ax.plot(x, table["apparent_auc"], "o-", label="apparent AUC", color="#1f77b4")
    ax.plot(x, table["cv_auc"], "s--", label="cross-validated AUC", color="#d62728")
    ax.axhline(0.5, color="grey", lw=0.8, ls=":")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("AUC")
    ax.set_ylim(0.4, 1.02)
    ax.set_title(f"Apparent vs cross-validated AUC — {endpoint}\n(reference-planned dose; small N)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument(
        "--quick", action="store_true", help="CI mode: one endpoint, reduced lambda sweep"
    )
    args = ap.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.features)
    if args.quick:
        runs = [("locoregional", "dosiomics")]
        sweep = (0.0, 1.0)
    else:
        runs = [("locoregional", "dosiomics"), ("locoregional", "dvh"), ("death", "dosiomics")]
        sweep = (0.0, 0.5, 1.0, 2.0)
    results: dict[str, object] = {"source": str(args.features), "seed": args.seed, "runs": {}}
    for endpoint, feature_set in runs:
        table, extras = run_benchmark(
            df, endpoint=endpoint, feature_set=feature_set, lambda_phys_sweep=sweep, seed=args.seed
        )
        key = f"{endpoint}_{feature_set}"
        csv = args.out_dir / f"benchmark_{key}.csv"
        table[_TABLE_COLS].to_csv(csv, index=False)
        results["runs"][key] = {
            "extras": extras,
            "table": table[_TABLE_COLS].round(4).to_dict(orient="records"),
        }
        print(f"\n=== {endpoint} / {feature_set}  (n={extras['n']}, events={extras['events']}) ===")
        print(table[_TABLE_COLS].round(3).to_string(index=False))
        if feature_set == "dosiomics":
            _optimism_plot(table, endpoint, args.out_dir / f"optimism_{endpoint}.png")

    (args.out_dir / "benchmark_results.json").write_text(
        json.dumps(results, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote tables + plots to {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
