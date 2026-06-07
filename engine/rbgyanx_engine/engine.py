"""Unified ``run_analysis`` entry point (TCP + NTCP, DICOM + txt)."""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from rbgyanx_engine.run_config import EngineResult, RunConfig
from rbgyanx_engine.pipeline import (
    _attach_outcomes,
    _dominant_params_site,
    _write_site_detection_report,
    apply_ntcp_uncertainty,
    apply_uncertainty_and_hypoxia,
    collect_dicom_ntcp,
    collect_dicom_tcp,
    collect_txt_ntcp,
    collect_txt_tcp,
    results_to_feature_df,
    run_ml_xai_validation,
)
from outputs.ntcp_reporter import save_ntcp_excel

logger = logging.getLogger(__name__)


def _write_provenance(cfg: RunConfig, result: EngineResult) -> Path:
    path = result.output_dir / "provenance.json"
    payload = {
        "engine": "rbgyanx-engine",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "endpoint": cfg.endpoint,
        "input_kind": cfg.input_kind,
        "mode": cfg.mode,
        "input_dir": str(cfg.input_dir.resolve()),
        "output_dir": str(result.output_dir.resolve()),
        "n_tcp_rows": len(result.tcp_results),
        "n_ntcp_rows": len(result.ntcp_results),
        "n_physical_rows": len(getattr(result, "physical_results", []) or []),
        "exit_code": result.exit_code,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _write_ntcp_validation_metrics(
    cfg: RunConfig,
    ntcp_results: list[dict],
    output_dir: Path,
) -> Path | None:
    """Publication metrics when outcome_csv is provided (CURSOR_FIXES §23)."""
    if not cfg.outcome_csv or not ntcp_results:
        return None
    from validation.validation_metrics import (
        validate_ntcp_model,
        validation_result_to_dict,
    )

    outcome_df = pd.read_csv(cfg.outcome_csv)
    ntcp_df_val = pd.DataFrame(
        [{k: v for k, v in r.items() if not str(k).startswith("_")} for r in ntcp_results]
    )
    val_rows: list[dict] = []
    for ntcp_col in ("NTCP_LKB_loglogit", "NTCP_LKB_probit", "NTCP_RS"):
        if ntcp_col not in ntcp_df_val.columns:
            continue
        merged = ntcp_df_val[["AnonPatientID", "structure", ntcp_col]].merge(
            outcome_df, on="AnonPatientID", how="inner"
        )
        if "ntcp_outcome" not in merged.columns:
            continue
        for organ, grp in merged.groupby("structure"):
            if len(grp) < 10:
                continue
            y_true = grp["ntcp_outcome"].astype(float).values
            y_pred = grp[ntcp_col].astype(float).values
            if grp["ntcp_outcome"].nunique() < 2:
                continue
            vr = validate_ntcp_model(
                y_true,
                y_pred,
                model_name=f"{ntcp_col}_{organ}",
                n_bootstrap=500 if cfg.mode == "advanced" else 0,
            )
            row = validation_result_to_dict(vr)
            row["organ"] = organ
            val_rows.append(row)
    if not val_rows:
        return None
    val_path = output_dir / "validation_metrics.xlsx"
    pd.DataFrame(val_rows).to_excel(val_path, index=False)
    logger.info("Validation metrics written to %s", val_path)
    return val_path


def _write_qa_report(cfg: RunConfig, result: EngineResult) -> Path:
    path = result.output_dir / "qa_report.json"
    issues: list[str] = []
    if cfg.input_kind == "dicom" and not result.tcp_results and cfg.endpoint in ("tcp", "both"):
        issues.append("No TCP rows from DICOM — check RTPLAN/RTDOSE/RTSTRUCT and targets.")
    if cfg.input_kind == "dicom" and not result.ntcp_results and cfg.endpoint in ("ntcp", "both"):
        issues.append("No NTCP rows — check OAR contours and site NTCP YAML.")
    if cfg.mode == "basic" and cfg.enable_ml and cfg.outcome_csv is None:
        issues.append("BASIC mode: ML enabled without outcome CSV — interpret ML as demo only.")
    payload = {"status": "warn" if issues else "ok", "issues": issues, "mode": cfg.mode}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _config_to_namespace(cfg: RunConfig) -> argparse.Namespace:
    """Map RunConfig to legacy argparse namespace for TCP ML phases."""
    return argparse.Namespace(
        dicom_dir=cfg.input_dir if cfg.input_kind == "dicom" else None,
        dvh_dir=cfg.input_dir if cfg.input_kind == "dvh_txt" else None,
        site=cfg.site,
        output_dir=cfg.output_dir,
        cohort=cfg.cohort,
        dvh_glob=cfg.dvh_glob,
        dose_per_fraction=cfg.dose_per_fraction,
        user_config=cfg.user_config,
        outcome_csv=cfg.outcome_csv,
        n_mc=cfg.n_mc,
        no_uncertainty=cfg.no_uncertainty,
        no_ml=not cfg.enable_ml or cfg.endpoint == "ntcp",
        no_ml_augment=cfg.no_ml_augment or cfg.mode == "basic",
        figures=cfg.figures,
        verbose=cfg.verbose,
    )


def run_analysis(cfg: RunConfig) -> EngineResult:
    """
    Run TCP and/or NTCP analysis for one cohort or patient folder.

    DICOM is the primary input path for clinic workflows (``input_kind='dicom'``).
    """
    output_dir = Path(cfg.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    site_override = cfg.site
    user_tcp = cfg.user_config
    user_ntcp = cfg.user_ntcp_config or cfg.user_config

    tcp_results: list[dict] = []
    ntcp_results: list[dict] = []

    if cfg.input_kind == "dicom":
        from rbgyanx_engine.pipeline import iter_dicom_patient_jobs

        jobs = list(iter_dicom_patient_jobs(Path(cfg.input_dir).resolve()))
        if not cfg.cohort and len(jobs) == 1:
            jobs = jobs[:1]
        for anon_id, folder, pid_filter in jobs:
            try:
                if cfg.endpoint in ("tcp", "both"):
                    tcp_results.extend(
                        collect_dicom_tcp(
                            folder, site_override, anon_id, user_tcp, patient_id=pid_filter
                        )
                    )
                if cfg.endpoint in ("ntcp", "both"):
                    ntcp_results.extend(
                        collect_dicom_ntcp(
                            folder,
                            site_override,
                            anon_id,
                            user_tcp,
                            user_ntcp,
                            patient_id=pid_filter,
                        )
                    )
            except Exception as exc:
                logger.warning("Skipping patient %s: %s", anon_id, exc)
    else:
        if cfg.endpoint in ("tcp", "both"):
            tcp_results = collect_txt_tcp(
                Path(cfg.input_dir).resolve(),
                site_override,
                user_tcp,
                cfg.dvh_glob,
                cfg.dose_per_fraction,
            )
        if cfg.endpoint in ("ntcp", "both"):
            ntcp_results = collect_txt_ntcp(
                Path(cfg.input_dir).resolve(),
                site_override,
                user_tcp,
                user_ntcp,
                cfg.dvh_glob,
                cfg.dose_per_fraction,
            )

    all_for_site = tcp_results or ntcp_results
    if not all_for_site:
        return EngineResult(
            exit_code=1,
            output_dir=output_dir,
            message="No results produced. Check DICOM/OAR contours or DVH text inputs.",
        )

    combined_site_rows = tcp_results if tcp_results else ntcp_results
    _write_site_detection_report(combined_site_rows, output_dir)
    site_detection_csv = output_dir / "site_detection.csv"

    physical_rows: list[dict] = []
    physical_csv: Path | None = None
    plan_quality_xlsx: Path | None = None
    plan_quality_flags_csv: Path | None = None
    patient_pdf: Path | None = None
    if cfg.input_kind == "dicom":
        from rbgyanx_engine.physical_dose import collect_cohort_physical_metrics
        from outputs.physical_reporter import save_physical_outputs

        physical_rows = collect_cohort_physical_metrics(
            Path(cfg.input_dir).resolve(),
            site_override,
            cfg.cohort,
            user_config=cfg.user_config,
            user_ntcp_config=cfg.user_ntcp_config,
        )
        if physical_rows:
            paths = save_physical_outputs(physical_rows, output_dir, cfg.user_config)
            physical_csv = paths["physical_dose_metrics_csv"]
            plan_quality_xlsx = paths["plan_quality_summary_xlsx"]
            plan_quality_flags_csv = paths["plan_quality_flags_csv"]
            logger.info(
                "Physical plan-quality: %s structures, workbook %s",
                len(physical_rows),
                plan_quality_xlsx,
            )

    if tcp_results and not cfg.no_uncertainty:
        apply_uncertainty_and_hypoxia(tcp_results, user_tcp, cfg.n_mc)

    quantec_csv: Path | None = None
    quantec_df: pd.DataFrame | None = None
    ntcp_csv: Path | None = None
    ntcp_xlsx: Path | None = None
    if ntcp_results:
        if not cfg.no_uncertainty:
            site_for_ntcp = site_override or _dominant_params_site(ntcp_results)
            apply_ntcp_uncertainty(ntcp_results, site_for_ntcp, user_ntcp, cfg.n_mc)
        from validation.quantec_checker import check_cohort_quantec

        quantec_df = check_cohort_quantec(ntcp_results)
        quantec_csv = output_dir / "quantec_flags.csv"
        quantec_df.to_csv(quantec_csv, index=False)
        ntcp_df = pd.DataFrame(
            [
                {k: v for k, v in r.items() if not str(k).startswith("_")}
                for r in ntcp_results
            ]
        )
        ntcp_csv = output_dir / "ntcp_results.csv"
        ntcp_df.to_csv(ntcp_csv, index=False)
        ntcp_xlsx = output_dir / "ntcp_benchmarking.xlsx"
        save_ntcp_excel(ntcp_results, ntcp_xlsx, quantec_df=quantec_df)

    validation_metrics_xlsx: Path | None = None
    dose_arrays_available = False
    if ntcp_results and cfg.endpoint in ("ntcp", "both"):
        validation_metrics_xlsx = _write_ntcp_validation_metrics(
            cfg, ntcp_results, output_dir
        )

    if (
        tcp_results
        and ntcp_results
        and cfg.endpoint == "both"
    ):
        from radiobiology.utcp import attach_utcp_to_tcp_results

        site_for_utcp = site_override or _dominant_params_site(tcp_results)
        attach_utcp_to_tcp_results(tcp_results, ntcp_results, site_for_utcp)

    if cfg.mode == "advanced" and ntcp_results:
        try:
            import sys
            from pathlib import Path as _P

            adv_root = _P(__file__).resolve().parents[2] / "engine_advanced"
            if str(adv_root) not in sys.path:
                sys.path.insert(0, str(adv_root))
            from rbgyanx_advanced.integration import enable_advanced_analysis

            _, dose_arrays_available = enable_advanced_analysis(
                cfg, tcp_results, ntcp_results, pd.DataFrame(), output_dir
            )
        except Exception as exc:
            logger.warning("ADVANCED NTCP extensions skipped: %s", exc)

    exit_code = 0
    tcp_xlsx: Path | None = None
    feat_csv: Path | None = None
    perf_metrics: dict = {}
    feat_df = pd.DataFrame()
    part_f_meta: dict = {}

    if tcp_results and cfg.endpoint in ("tcp", "both"):
        if cfg.outcome_csv:
            outcomes = pd.read_csv(cfg.outcome_csv)
            _attach_outcomes(tcp_results, outcomes)
            feat_df = results_to_feature_df(
                tcp_results, clinical_features_csv=cfg.clinical_features_csv
            )
            if not feat_df.empty:
                feat_csv = output_dir / "cohort_features.csv"
                feat_df.to_csv(feat_csv, index=False)
            ml_site = site_override or _dominant_params_site(tcp_results)
            if cfg.mode == "advanced":
                try:
                    import sys
                    from pathlib import Path as _P

                    adv_root = _P(__file__).resolve().parents[2] / "engine_advanced"
                    if str(adv_root) not in sys.path:
                        sys.path.insert(0, str(adv_root))
                    from rbgyanx_advanced.integration import enable_advanced_analysis

                    feat_df, dose_arrays_available = enable_advanced_analysis(
                        cfg,
                        tcp_results,
                        ntcp_results,
                        feat_df,
                        output_dir,
                    )
                except Exception as exc:
                    logger.warning("ADVANCED ML feature extensions skipped: %s", exc)
            if cfg.enable_ml and cfg.mode == "advanced" and not feat_df.empty:
                perf_metrics = run_ml_xai_validation(
                    feat_df,
                    output_dir,
                    ml_site,
                    user_tcp,
                    ml_augment=not cfg.no_ml_augment,
                )
        from outputs.reporter import print_summary_table, save_benchmarking_excel

        tcp_xlsx = output_dir / "tcp_benchmarking.xlsx"
        save_benchmarking_excel(tcp_results, perf_metrics or None, tcp_xlsx)
        print_summary_table(tcp_results, max_rows=min(30, len(tcp_results)))
    elif cfg.endpoint == "tcp":
        exit_code = 1

    if cfg.endpoint == "ntcp" and not ntcp_results:
        exit_code = 1

    if physical_rows:
        from outputs.patient_summary_pdf import save_patient_summary_pdf

        patient_pdf = save_patient_summary_pdf(
            output_dir,
            physical_rows=physical_rows,
            tcp_results=tcp_results,
            ntcp_results=ntcp_results,
            quantec_df=quantec_df,
        )

    if cfg.mode == "advanced" and (
        cfg.enable_bayesian_ntcp or cfg.pinn_train
    ):
        try:
            import sys
            from pathlib import Path as _P

            f_root = _P(__file__).resolve().parents[2] / "engine_advanced_f"
            if str(f_root) not in sys.path:
                sys.path.insert(0, str(f_root))
            from rbgyanx_advanced_f.integration import enable_part_f_analysis

            feat_df, part_f_meta = enable_part_f_analysis(
                cfg,
                tcp_results,
                ntcp_results,
                feat_df,
                output_dir,
            )
            if feat_df is not None and not feat_df.empty and feat_csv is None:
                feat_csv = output_dir / "cohort_features.csv"
                feat_df.to_csv(feat_csv, index=False)
        except Exception as exc:
            logger.warning("ADVANCED Part F skipped: %s", exc)

    result = EngineResult(
        exit_code=exit_code,
        output_dir=output_dir,
        tcp_results=tcp_results,
        ntcp_results=ntcp_results,
        site_detection_csv=site_detection_csv if site_detection_csv.is_file() else None,
        tcp_benchmark_xlsx=tcp_xlsx,
        ntcp_benchmark_xlsx=ntcp_xlsx,
        ntcp_results_csv=ntcp_csv,
        cohort_features_csv=feat_csv,
        physical_metrics_csv=physical_csv,
        plan_quality_summary_xlsx=plan_quality_xlsx,
        plan_quality_flags_csv=plan_quality_flags_csv,
        patient_summary_pdf=patient_pdf,
        validation_metrics_xlsx=validation_metrics_xlsx,
        dose_arrays_available=dose_arrays_available,
        physical_results=physical_rows,
        bayesian_ntcp_summary_csv=(
            Path(part_f_meta["bayesian_summary_csv"])
            if part_f_meta.get("bayesian_summary_csv")
            else None
        ),
        pinn_checkpoint=(
            Path(part_f_meta["pinn_checkpoint"])
            if part_f_meta.get("pinn_checkpoint")
            else None
        ),
        message="Complete",
    )
    result.provenance_json = _write_provenance(cfg, result)
    result.qa_report_json = _write_qa_report(cfg, result)
    logger.info("rbgyanx-engine finished: %s", output_dir)
    return result
