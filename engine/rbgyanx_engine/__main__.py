"""
CLI: ``python -m rbgyanx_engine``

Examples:
  python -m rbgyanx_engine --dicom-dir ./dicom --endpoint both --output-dir ./out
  python -m rbgyanx_engine --dvh-dir ./dvh --endpoint ntcp --output-dir ./out
  python -m rbgyanx_engine --plan-a ./plan_a --plan-b ./plan_b --output-dir ./delta_out
  python -m rbgyanx_engine --dicom-dir ./dicom --calibrate-ntcp --outcome-csv outcomes.csv
"""

from __future__ import annotations

import argparse
import logging
import pathlib
import sys

from rbgyanx_engine.engine import run_analysis
from rbgyanx_engine.run_config import RunConfig


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="rbgyanx_engine",
        description=(
            "rbGyanX CDSS engine: TCP + NTCP from DICOM RT or TPS DVH text, "
            "multi-site, classical radiobiology and optional ML (ADVANCED)."
        ),
    )
    inp = p.add_mutually_exclusive_group(required=False)
    inp.add_argument("--dicom-dir", type=pathlib.Path, help="DICOM RT folder (required for clinic workflow)")
    inp.add_argument("--dvh-dir", type=pathlib.Path, help="TPS DVH text export folder")
    p.add_argument(
        "--endpoint",
        choices=["tcp", "ntcp", "both"],
        default="both",
        help="Analysis endpoint [default: both]",
    )
    p.add_argument(
        "--mode",
        choices=["basic", "advanced"],
        default="basic",
        help="basic=clinic-safe defaults; advanced=research ML depth [default: basic]",
    )
    p.add_argument(
        "--site",
        default=None,
        choices=[
            "BRAIN",
            "BRAIN_METS",
            "BRAIN_GBM",
            "HN",
            "LUNG",
            "BREAST",
            "PROSTATE",
            "LIVER",
            "PELVIS",
        ],
        help="Override auto-detected site",
    )
    p.add_argument("--output-dir", type=pathlib.Path, default=pathlib.Path("rbgyanx_output"))
    p.add_argument("--cohort", action="store_true", help="Multi-patient DICOM cohort mode")
    p.add_argument("--dvh-glob", default="*.txt")
    p.add_argument("--dose-per-fraction", type=float, default=2.0)
    p.add_argument("--user-config", type=pathlib.Path, default=None, help="TCP site_params_user.yaml")
    p.add_argument("--user-ntcp-config", type=pathlib.Path, default=None, help="NTCP YAML override")
    p.add_argument("--outcome-csv", type=pathlib.Path, default=None)
    p.add_argument("--clinical-csv", type=pathlib.Path, default=None)
    p.add_argument("--n-mc", type=int, default=1000)
    p.add_argument("--no-uncertainty", action="store_true")
    p.add_argument("--no-ml", action="store_true")
    p.add_argument("--no-ml-augment", action="store_true")
    p.add_argument("--figures", action="store_true")
    p.add_argument("--verbose", action="store_true")
    p.add_argument("--plan-a", type=pathlib.Path, help="Plan A DICOM directory (delta NTCP comparison)")
    p.add_argument("--plan-b", type=pathlib.Path, help="Plan B DICOM directory (delta NTCP comparison)")
    p.add_argument("--delta-threshold", type=float, default=5.0, help="Delta NTCP threshold %% [default: 5]")
    p.add_argument("--plan-a-label", default="Plan_A")
    p.add_argument("--plan-b-label", default="Plan_B")
    p.add_argument(
        "--calibrate-ntcp",
        action="store_true",
        help="Fit LKB TD50/m from outcome_csv; writes site_params_fitted.yaml",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.plan_a and args.plan_b:
        from rbgyanx_engine.delta_analysis import compare_plans

        delta_df, out = compare_plans(
            plan_a_dir=args.plan_a,
            plan_b_dir=args.plan_b,
            output_dir=args.output_dir,
            plan_a_label=args.plan_a_label,
            plan_b_label=args.plan_b_label,
            site=args.site,
            delta_threshold_pct=args.delta_threshold,
            no_uncertainty=args.no_uncertainty,
        )
        print(f"Delta NTCP comparison: {out} ({len(delta_df)} rows)")
        return 0

    if args.calibrate_ntcp:
        if not args.outcome_csv:
            print("ERROR: --calibrate-ntcp requires --outcome-csv", file=sys.stderr)
            return 1
        if not args.dicom_dir and not args.dvh_dir:
            print("ERROR: --calibrate-ntcp requires --dicom-dir or --dvh-dir", file=sys.stderr)
            return 1
        cfg = RunConfig(
            endpoint="ntcp",
            input_kind="dicom" if args.dicom_dir else "dvh_txt",
            input_dir=args.dicom_dir or args.dvh_dir,
            output_dir=args.output_dir,
            outcome_csv=args.outcome_csv,
            site=args.site,
            cohort=args.cohort,
            no_uncertainty=True,
            verbose=args.verbose,
        )
        result = run_analysis(cfg)
        if not result.ntcp_results:
            print("ERROR: no NTCP results to calibrate", file=sys.stderr)
            return result.exit_code or 1
        from validation.ntcp_calibration import calibrate_ntcp_from_results

        site_key = args.site or "HN"
        if result.ntcp_results:
            site_key = str(result.ntcp_results[0].get("site_params_key") or result.ntcp_results[0].get("site") or site_key)
        out_yaml = calibrate_ntcp_from_results(
            result.ntcp_results,
            args.outcome_csv,
            site_key,
            args.output_dir,
        )
        if out_yaml:
            print(f"Fitted NTCP YAML: {out_yaml}")
            return 0
        print("WARNING: calibration produced no fitted organs", file=sys.stderr)
        return 1

    if not args.dicom_dir and not args.dvh_dir:
        build_parser().print_help()
        print("\nERROR: provide --dicom-dir or --dvh-dir (or --plan-a with --plan-b)", file=sys.stderr)
        return 2

    cfg = RunConfig(
        endpoint=args.endpoint,
        input_kind="dicom" if args.dicom_dir else "dvh_txt",
        input_dir=args.dicom_dir or args.dvh_dir,
        output_dir=args.output_dir,
        clinical_csv=args.clinical_csv,
        outcome_csv=args.outcome_csv,
        site=args.site,
        n_mc=args.n_mc,
        enable_ml=not args.no_ml,
        mode=args.mode,
        user_config=args.user_config,
        user_ntcp_config=args.user_ntcp_config,
        dvh_glob=args.dvh_glob,
        dose_per_fraction=args.dose_per_fraction,
        cohort=args.cohort,
        no_uncertainty=args.no_uncertainty,
        no_ml_augment=args.no_ml_augment,
        figures=args.figures,
        verbose=args.verbose,
    )
    return run_analysis(cfg).exit_code


if __name__ == "__main__":
    sys.exit(main())
