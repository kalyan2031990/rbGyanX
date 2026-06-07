"""
End-to-end rbgyanx-engine pipeline (TCP Phases 1–8 + classical NTCP).

Supports DICOM RT and commercial TPS DVH text exports for any configured site.
"""

from __future__ import annotations

import argparse
import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd
import pydicom

from config.site_params import load_site_params
from dicom_io.dicom_reader import DicomPlanReader
from dicom_io.dvh_extractor import DVHExtractor
from dicom_io.site_detector import (
    detect_site,
    detect_site_from_text,
    resolve_pipeline_site,
)
from config.site_ntcp_params import allowed_oar_names, load_site_ntcp_params
from dicom_io.structure_mapper import canon_target, get_oar_structures, get_target_structures
from radiobiology.ntcp_calculator import NTCPCalculator
from dicom_io.txt_dvh_reader import iter_dvh_text_files, parse_dvh_text_file
from radiobiology.tcp_calculator import TCPCalculator
from statistical_models.epv_guard import EPV_MINIMUM
from uncertainty import ParamUncertaintyConfig, run_parameter_mc
from uncertainty.hypoxia import apply_hypoxia_correction

logger = logging.getLogger(__name__)

FEATURE_COLS = [
    "TCP_Poisson",
    "TCP_ZM",
    "TCP_gEUD",
    "TCP_Logistic",
    "EQD2_gy",
    "Dmean_gy",
]

MIN_ML_COHORT = 30


def _attach_site_metadata(row: dict, site_info: dict) -> None:
    row["site_detected"] = site_info.get("site", "")
    row["site_histology"] = site_info.get("histology", "")
    row["site_fractionation"] = site_info.get("fractionation", site_info.get("subtype", ""))
    row["site_subtype"] = row["site_fractionation"]  # legacy column name
    row["site_confidence"] = site_info.get("confidence", "")
    row["site_params_key"] = site_info.get("params_site_key", "")
    row["site_evidence"] = "; ".join(site_info.get("evidence", []))


def _dominant_params_site(results: list[dict]) -> str:
    keys = [r.get("site_params_key") for r in results if r.get("site_params_key")]
    if not keys:
        return "HN"
    return max(set(keys), key=keys.count)


def _structures_for_site_detection(rt_struct_ds, plan_metadata: dict) -> list[dict]:
    """Targets plus OAR canonical names for anatomical site detection."""
    targets = get_target_structures(rt_struct_ds, plan_metadata)
    seen = {s.get("canonical") for s in targets}
    combined = list(targets)
    for roi in getattr(rt_struct_ds, "StructureSetROISequence", []) or []:
        mapped = canon_target(str(getattr(roi, "ROIName", "")))
        canonical = mapped.get("canonical", "")
        if canonical and canonical not in seen:
            combined.append(
                {
                    "canonical": canonical,
                    "raw_name": str(getattr(roi, "ROIName", "")),
                    "confidence": mapped.get("confidence", ""),
                }
            )
            seen.add(canonical)
    return combined


def iter_dicom_patient_jobs(dicom_root: Path) -> Iterator[tuple[str, Path, str | None]]:
    """
  Yield (anon_patient_id, folder_path, patient_id_filter) for cohort processing.

  - One subdirectory per patient, or
  - Flat folder: multiple patients distinguished by DICOM PatientID.
    """
    dicom_root = Path(dicom_root)
    subdirs = sorted(p for p in dicom_root.iterdir() if p.is_dir())
    if subdirs:
        for idx, sub in enumerate(subdirs):
            yield sub.name, sub, None
        return

    by_pid: dict[str, list[Path]] = defaultdict(list)
    for path in dicom_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
        except Exception:
            continue
        pid = str(getattr(ds, "PatientID", "") or path.stem).strip()
        if pid:
            by_pid[pid].append(path)

    for pid in sorted(by_pid):
        yield pid, dicom_root, pid


def collect_dicom_tcp(
    dicom_dir: Path,
    site_override: str | None,
    anon_id: str,
    user_config: Path | None,
    patient_id: str | None = None,
) -> list[dict]:
    """Phase 1–2: DICOM load, DVH extraction, classical TCP."""
    reader = DicomPlanReader()
    dicom = reader.load_patient_dicom(dicom_dir, patient_id=patient_id)
    meta = reader.extract_plan_metadata(dicom["rt_plan"])
    structs = get_target_structures(dicom["rt_struct"], meta)
    detection = detect_site(meta, _structures_for_site_detection(dicom["rt_struct"], meta))
    params_key, site_info = resolve_pipeline_site(site_override, detection)
    site_params = load_site_params(params_key, user_config=user_config)
    logger.info(
        "Patient %s: site=%s (%s) confidence=%s",
        anon_id,
        site_info.get("site"),
        params_key,
        site_info.get("confidence"),
    )

    dvh_map = DVHExtractor().extract_all_dvhs(
        dicom["rt_dose"], dicom["rt_struct"], structs
    )

    calc = TCPCalculator()
    results: list[dict] = []
    for dvh_r in dvh_map.values():
        t_type = dvh_r.canonical_name
        if t_type not in ("GTV", "CTV", "PTV"):
            continue
        row = calc.compute_all(dvh_r, meta, site_params, target_type=t_type)
        row["AnonPatientID"] = anon_id
        row["site"] = params_key
        _attach_site_metadata(row, site_info)
        row["params_snapshot"] = {
            "params_source": site_params.params_source,
            "TCD50_gy": site_params.TCD50_gy,
            "alpha_beta_gy": site_params.alpha_beta_gy,
        }
        results.append(row)
    return results


def collect_txt_tcp(
    dvh_dir: Path,
    site_override: str | None,
    user_config: Path | None,
    glob_pattern: str,
    default_dpf_gy: float,
) -> list[dict]:
    """Phase 1–2 from TPS DVH text exports."""
    calc = TCPCalculator()
    results: list[dict] = []

    for path in iter_dvh_text_files(dvh_dir, glob_pattern):
        txt = parse_dvh_text_file(path, default_dose_per_fraction_gy=default_dpf_gy)
        detection = detect_site_from_text(
            txt.plan_metadata, txt.raw_name, txt.header_text
        )
        params_key, site_info = resolve_pipeline_site(site_override, detection)
        site_params = load_site_params(params_key, user_config=user_config)
        logger.info(
            "DVH %s: site=%s (%s) confidence=%s",
            path.name,
            site_info.get("site"),
            params_key,
            site_info.get("confidence"),
        )
        row = calc.compute_all(
            txt, txt.plan_metadata, site_params, target_type=txt.canonical_name
        )
        row["AnonPatientID"] = txt.patient_id
        row["total_volume_cc"] = txt.total_volume_cc
        row["site"] = params_key
        _attach_site_metadata(row, site_info)
        row["params_snapshot"] = {
            "params_source": site_params.params_source,
            "TCD50_gy": site_params.TCD50_gy,
            "alpha_beta_gy": site_params.alpha_beta_gy,
        }
        results.append(row)
    return results


def collect_dicom_ntcp(
    dicom_dir: Path,
    site_override: str | None,
    anon_id: str,
    user_tcp_config: Path | None,
    user_ntcp_config: Path | None,
    patient_id: str | None = None,
) -> list[dict]:
    """Phase 1–2 NTCP: DICOM OAR DVHs and classical NTCP models."""
    reader = DicomPlanReader()
    dicom = reader.load_patient_dicom(dicom_dir, patient_id=patient_id)
    meta = reader.extract_plan_metadata(dicom["rt_plan"])
    detection = detect_site(meta, _structures_for_site_detection(dicom["rt_struct"], meta))
    params_key, site_info = resolve_pipeline_site(site_override, detection)
    ntcp_site = load_site_ntcp_params(params_key, user_config=user_ntcp_config)
    allowed = allowed_oar_names(params_key, user_ntcp_config)
    oars = get_oar_structures(dicom["rt_struct"], allowed_canonicals=allowed)
    if not oars:
        logger.warning("Patient %s: no mapped OARs for site %s", anon_id, params_key)
        return []

    dvh_map = DVHExtractor().extract_all_dvhs(dicom["rt_dose"], dicom["rt_struct"], oars)
    calc = NTCPCalculator()
    results: list[dict] = []
    for dvh_r in dvh_map.values():
        organ = dvh_r.canonical_name
        op = ntcp_site.organs.get(organ)
        if op is None:
            continue
        row = calc.compute_all(dvh_r, meta, op, params_key)
        row["AnonPatientID"] = anon_id
        _attach_site_metadata(row, site_info)
        results.append(row)
    return results


def collect_txt_ntcp(
    dvh_dir: Path,
    site_override: str | None,
    user_tcp_config: Path | None,
    user_ntcp_config: Path | None,
    glob_pattern: str,
    default_dpf_gy: float,
) -> list[dict]:
    """NTCP from TPS DVH text when structure maps to a configured OAR."""
    calc = NTCPCalculator()
    results: list[dict] = []

    for path in iter_dvh_text_files(dvh_dir, glob_pattern):
        txt = parse_dvh_text_file(path, default_dose_per_fraction_gy=default_dpf_gy)
        detection = detect_site_from_text(
            txt.plan_metadata, txt.raw_name, txt.header_text
        )
        params_key, site_info = resolve_pipeline_site(site_override, detection)
        ntcp_site = load_site_ntcp_params(params_key, user_config=user_ntcp_config)
        op = ntcp_site.organs.get(txt.canonical_name)
        if op is None:
            continue
        row = calc.compute_all(txt, txt.plan_metadata, op, params_key)
        row["AnonPatientID"] = txt.patient_id
        _attach_site_metadata(row, site_info)
        results.append(row)
    return results


def apply_uncertainty_and_hypoxia(
    results: list[dict],
    user_config: Path | None,
    n_mc: int,
) -> None:
    """Phase 3: parameter MC and hypoxia correction (in-place)."""
    mc_cfg = ParamUncertaintyConfig(n_samples=n_mc)

    for r in results:
        dvh_df = r.get("_dvh_df")
        if dvh_df is None:
            continue
        params_key = r.get("site_params_key") or r.get("site", "HN")
        sp = load_site_params(params_key, user_config=user_config)
        try:
            mc = run_parameter_mc(
                dvh_df,
                int(r.get("n_fractions", 30)),
                sp,
                target_type=str(r.get("target_type", "GTV")),
                config=mc_cfg,
            )
            r["TCP_Poisson_mc"] = mc.get("TCP_Poisson_mc", {})
            r["TCP_gEUD_mc"] = mc.get("TCP_gEUD_mc", {})
        except Exception as exc:
            logger.warning("MC failed for %s: %s", r.get("AnonPatientID"), exc)

        try:
            hyp = apply_hypoxia_correction(
                dvh_df,
                int(r.get("n_fractions", 30)),
                sp,
                target_type=str(r.get("target_type", "GTV")),
            )
            r["TCP_Poisson_hypoxia"] = hyp.get("TCP_Poisson_hypoxia", np.nan)
            r["TCP_gEUD_hypoxia"] = hyp.get("TCP_gEUD_hypoxia", np.nan)
            r["TCP_Logistic_hypoxia"] = hyp.get("TCP_Logistic_hypoxia", np.nan)
        except Exception as exc:
            logger.warning("Hypoxia failed for %s: %s", r.get("AnonPatientID"), exc)


def apply_ntcp_uncertainty(
    ntcp_results: list[dict],
    site_key: str,
    user_ntcp_config: Path | None,
    n_mc: int,
) -> None:
    """Phase 3 NTCP: run uNTCP parameter MC in-place on each OAR row."""
    from uncertainty.ntcp_mc import NTCPUncertaintyConfig, run_untcp

    ntcp_site = load_site_ntcp_params(site_key, user_config=user_ntcp_config)
    cfg = NTCPUncertaintyConfig(n_samples=n_mc)
    for r in ntcp_results:
        organ = r.get("structure", "")
        dvh_df = r.get("_dvh_df")
        op = ntcp_site.organs.get(organ)
        if dvh_df is None or op is None:
            continue
        try:
            mc = run_untcp(dvh_df, op, config=cfg)
            r["uNTCP_LKB_loglogit"] = mc["uNTCP_LKB_loglogit"]
            r["uNTCP_LKB_probit"] = mc["uNTCP_LKB_probit"]
            r["uNTCP_RS"] = mc["uNTCP_RS"]
        except Exception as exc:
            logger.warning("uNTCP failed for %s/%s: %s", r.get("AnonPatientID"), organ, exc)


def _attach_outcomes(results: list[dict], outcomes: pd.DataFrame | None) -> None:
    if outcomes is None or outcomes.empty:
        return
    for r in results:
        pid = r.get("AnonPatientID", "")
        oc = outcomes[outcomes["AnonPatientID"].astype(str) == str(pid)]
        if oc.empty:
            continue
        r["LocalControl"] = int(oc.iloc[0]["LocalControl"])
        if "FollowUp_months" in oc.columns:
            r["FollowUp_months"] = float(oc.iloc[0]["FollowUp_months"])


SHAPE_FEATURE_COLS = [
    "D2_gy",
    "D50_gy",
    "D98_gy",
    "D2_D98_ratio",
    "dose_skewness",
    "dose_kurtosis",
    "V95_rx_frac",
    "dose_std_gy",
]


def results_to_feature_df(
    results: list[dict],
    clinical_features_csv: Path | None = None,
) -> pd.DataFrame:
    rows = []
    extra_cols = SHAPE_FEATURE_COLS
    for r in results:
        if "LocalControl" not in r:
            continue
        rows.append(
            {
                "AnonPatientID": r.get("AnonPatientID", ""),
                "target_type": r.get("target_type", ""),
                "LocalControl": r.get("LocalControl"),
                **{c: r.get(c, np.nan) for c in FEATURE_COLS},
                **{c: r.get(c, np.nan) for c in extra_cols},
            }
        )
    feat_df = pd.DataFrame(rows)
    if clinical_features_csv and Path(clinical_features_csv).is_file():
        clin_df = pd.read_csv(clinical_features_csv)
        id_col = next(
            (c for c in clin_df.columns if c.lower() in ("anonpatientid", "patientid", "id")),
            None,
        )
        if id_col:
            clin_df = clin_df.rename(columns={id_col: "AnonPatientID"})
            feat_df = feat_df.merge(clin_df, on="AnonPatientID", how="left")
            logger.info(
                "Merged clinical covariates: %d columns added",
                len(clin_df.columns) - 1,
            )
        else:
            logger.warning(
                "clinical_features_csv has no recognised ID column; skipping merge."
            )
    return feat_df


def augment_for_ml(feat_df: pd.DataFrame, n_target: int = 32, seed: int = 0) -> pd.DataFrame:
    """Bootstrap-style augmentation when cohort n < MIN_ML_COHORT (demo / development)."""
    rng = np.random.default_rng(seed)
    parts: list[pd.DataFrame] = []
    while sum(len(p) for p in parts) < n_target:
        parts.append(feat_df.copy())
    aug = pd.concat(parts, ignore_index=True).iloc[:n_target].copy()
    for col in FEATURE_COLS:
        aug[col] = aug[col] * rng.uniform(0.97, 1.03, size=len(aug))
    score = (
        0.4 * aug["TCP_Poisson"].fillna(0.5)
        + 0.3 * aug["TCP_gEUD"].fillna(0.5)
        + 0.3 * aug["TCP_Logistic"].fillna(0.5)
    )
    med = float(np.median(score))
    lc = (score + rng.normal(0, 0.08, len(aug)) > med).astype(int)
    if lc.sum() in (0, len(lc)):
        lc = rng.integers(0, 2, size=len(aug))
    aug["LocalControl"] = lc
    aug["AnonPatientID"] = [f"AUG{i:04d}" for i in range(len(aug))]
    return aug


def _annotate_ml_safety(
    perf: dict,
    model_name: str,
    auc: float,
    cv_auc: float | None,
    overfitting_index: float | None,
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_patients: int,
    synthetic_data_used: bool,
    epv: float | None = None,
) -> None:
    from validation.calibration import compute_calibration_slope_intercept
    from validation.clinical_safety_guard import run_safety_checks

    cal_slope = None
    try:
        cal_slope, _ = compute_calibration_slope_intercept(y_true, y_prob)
    except Exception:
        pass
    report = run_safety_checks(
        model_name,
        auc=auc,
        cv_auc=cv_auc,
        overfitting_index=overfitting_index,
        calibration_slope=cal_slope,
        epv=epv,
        n_patients=n_patients,
        synthetic_data_used=synthetic_data_used,
    )
    if model_name in perf:
        perf[model_name]["safety_annotation"] = report.annotation()
        perf[model_name]["safety_status"] = report.overall_status
        perf[model_name]["calibration_slope"] = cal_slope


def run_ml_xai_validation(
    feat_df: pd.DataFrame,
    output_dir: Path,
    site: str,
    user_config: Path | None,
    ml_augment: bool,
) -> dict:
    """Phases 4–7: MVL, ML, XAI, validation metrics."""
    from ml_models.random_forest_tcp import fit_random_forest_tcp
    from ml_models.xgboost_tcp import fit_xgboost_tcp
    from outputs.figures import plot_dose_response_curves, plot_model_comparison_bar
    from statistical_models.logistic_tcp_mv import fit_mvl_tcp, predict_tcp_mvl
    from validation.calibration import plot_calibration
    from validation.cohort_consistency import compute_ccs
    from validation.tcp_evaluator import evaluate_model
    from xai.pdp_ice import compute_pdp_ice, plot_pdp_ice
    from xai.shap_tcp import plot_shap_global

    perf: dict = {}
    mvl_fit = None
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    if len(feat_df) >= 4 and feat_df["LocalControl"].nunique() > 1:
        X = feat_df[FEATURE_COLS].astype(float).fillna(feat_df[FEATURE_COLS].median())
        y = feat_df["LocalControl"].values.astype(int)
        try:
            mvl = fit_mvl_tcp(
                X.values, y, feature_names=FEATURE_COLS, epv_threshold=EPV_MINIMUM
            )
            for idx, row in feat_df.iterrows():
                x_row = row[FEATURE_COLS].astype(float).values.reshape(1, -1)
                feat_df.at[idx, "TCP_MVL"] = float(predict_tcp_mvl(mvl.pipeline, x_row)[0])
            ev = evaluate_model(y, mvl.prob_train[: len(y)], cv_auc=mvl.auc_loo)
            mvl_fit = mvl
            perf["MVL"] = {
                "auc": ev.auc,
                "auc_ci": (ev.auc_ci_lower, ev.auc_ci_upper),
                "brier": ev.brier_score,
                "ece": ev.ece,
                "overfitting_index": ev.overfitting_index,
                "cv_auc": mvl.auc_loo,
                "harrell_c": None,
            }
        except ValueError as epv_exc:
            logger.warning(
                "MVL skipped - EPV insufficient: %s (need EPV>=%.0f; collect more events or reduce features).",
                epv_exc,
                EPV_MINIMUM,
            )
        except Exception as exc:
            logger.warning("MVL skipped: %s", exc)

    ml_df = feat_df
    synthetic_used = False
    if ml_augment and len(feat_df) < MIN_ML_COHORT:
        ml_df = augment_for_ml(feat_df, n_target=MIN_ML_COHORT)
        synthetic_used = True
        ml_df.to_csv(output_dir / "ml_cohort_augmented.csv", index=False)
        logger.info(
            "ML cohort augmented to n=%d (real n=%d). Use real outcomes for production.",
            len(ml_df),
            len(feat_df),
        )
    else:
        ml_df = feat_df.copy()
    if ml_df["AnonPatientID"].astype(str).str.startswith("AUG").any():
        synthetic_used = True

    if len(ml_df) < MIN_ML_COHORT or ml_df["LocalControl"].nunique() < 2:
        logger.info("Skipping ML/XAI (insufficient cohort or single outcome class).")
        plot_dose_response_curves(
            load_site_params(site, user_config=user_config),
            output_path=fig_dir / f"dose_response_{site}.png",
        )
        return perf

    Xa = ml_df[FEATURE_COLS].astype(float).fillna(ml_df[FEATURE_COLS].median())
    ya = ml_df["LocalControl"].values.astype(int)
    patient_ids = ml_df["AnonPatientID"].values

    xgb = fit_xgboost_tcp(
        Xa.values,
        ya,
        feature_names=FEATURE_COLS,
        compute_shap=True,
        patient_ids=patient_ids,
    )
    rf = fit_random_forest_tcp(
        Xa.values,
        ya,
        feature_names=FEATURE_COLS,
        compute_shap=False,
        patient_ids=patient_ids,
    )

    ex_xgb = evaluate_model(
        ya, xgb.model.predict_proba(Xa.values)[:, 1], cv_auc=xgb.auc_outer_mean
    )
    perf["XGBoost"] = {
        "auc": ex_xgb.auc,
        "auc_ci": (ex_xgb.auc_ci_lower, ex_xgb.auc_ci_upper),
        "brier": ex_xgb.brier_score,
        "ece": ex_xgb.ece,
        "overfitting_index": ex_xgb.overfitting_index,
        "cv_auc": xgb.auc_outer_mean,
        "harrell_c": None,
    }
    ex_rf = evaluate_model(ya, rf.model.predict_proba(Xa.values)[:, 1])
    perf["RandomForest"] = {
        "auc": ex_rf.auc,
        "auc_ci": (ex_rf.auc_ci_lower, ex_rf.auc_ci_upper),
        "brier": ex_rf.brier_score,
        "ece": ex_rf.ece,
        "overfitting_index": None,
        "cv_auc": rf.auc_outer_mean,
        "harrell_c": None,
    }

    try:
        from ml_models.lgbm_tcp import fit_lgbm_tcp

        lgbm = fit_lgbm_tcp(
            Xa.values,
            ya,
            feature_names=FEATURE_COLS,
            compute_shap=False,
            patient_ids=patient_ids,
        )
        ex_lgbm = evaluate_model(
            ya, lgbm.model.predict_proba(Xa.values)[:, 1], cv_auc=lgbm.auc_outer_mean
        )
        perf["LightGBM"] = {
            "auc": ex_lgbm.auc,
            "auc_ci": (ex_lgbm.auc_ci_lower, ex_lgbm.auc_ci_upper),
            "brier": ex_lgbm.brier_score,
            "ece": ex_lgbm.ece,
            "overfitting_index": ex_lgbm.overfitting_index,
            "cv_auc": lgbm.auc_outer_mean,
            "harrell_c": None,
        }
        _annotate_ml_safety(
            perf,
            "LightGBM",
            ex_lgbm.auc,
            lgbm.auc_outer_mean,
            ex_lgbm.overfitting_index,
            ya,
            lgbm.model.predict_proba(Xa.values)[:, 1],
            len(ml_df),
            synthetic_used,
        )
    except ImportError:
        logger.info("LightGBM not installed; skipping LGBM model.")

    n_events = int(ya.sum())
    epv_ml = n_events / max(len(FEATURE_COLS), 1)
    _annotate_ml_safety(
        perf,
        "XGBoost",
        ex_xgb.auc,
        xgb.auc_outer_mean,
        ex_xgb.overfitting_index,
        ya,
        xgb.model.predict_proba(Xa.values)[:, 1],
        len(ml_df),
        synthetic_used,
        epv=epv_ml,
    )
    _annotate_ml_safety(
        perf,
        "RandomForest",
        ex_rf.auc,
        rf.auc_outer_mean,
        None,
        ya,
        rf.model.predict_proba(Xa.values)[:, 1],
        len(ml_df),
        synthetic_used,
        epv=epv_ml,
    )
    if mvl_fit is not None and "MVL" in perf:
        y_mvl = feat_df["LocalControl"].values.astype(int)
        _annotate_ml_safety(
            perf,
            "MVL",
            perf["MVL"].get("auc", float("nan")),
            perf["MVL"].get("cv_auc"),
            perf["MVL"].get("overfitting_index"),
            y_mvl,
            mvl_fit.prob_train[: len(y_mvl)],
            len(feat_df),
            synthetic_used,
            epv=int(y_mvl.sum()) / max(len(FEATURE_COLS), 1),
        )

    ccs = compute_ccs(ya, ml_df["TCP_Poisson"].values, xgb.model.predict_proba(Xa.values)[:, 1])
    logger.info(
        "Cohort consistency score (CCS)=%.3f verdict=%s threshold=%.3f",
        ccs.get("ccs", float("nan")),
        ccs.get("verdict", ""),
        ccs.get("threshold_used", float("nan")),
    )
    perf["_ccs"] = ccs

    if xgb.shap_values is not None:
        plot_shap_global(xgb.shap_values, FEATURE_COLS, fig_dir / "shap_global_xgb.png")
    grid, pdp, ice = compute_pdp_ice(xgb.model, Xa.values, 0, grid_points=20)
    plot_pdp_ice(
        grid,
        pdp,
        ice,
        FEATURE_COLS[0],
        fig_dir / "pdp_tcp_poisson.png",
        classical_tcp_fn=lambda g: np.clip(g / 80.0, 0, 1),
    )
    plot_calibration(
        ya, xgb.model.predict_proba(Xa.values)[:, 1], "XGBoost", fig_dir / "calibration_xgb.png"
    )

    plot_dose_response_curves(
        load_site_params(site, user_config=user_config),
        output_path=fig_dir / f"dose_response_{site}.png",
    )
    if len(feat_df) >= 1:
        plot_model_comparison_bar(
            feat_df["AnonPatientID"].tolist(),
            {
                "Poisson": feat_df["TCP_Poisson"].values,
                "gEUD": feat_df["TCP_gEUD"].values,
                "Logistic": feat_df["TCP_Logistic"].values,
            },
            fig_dir / "model_comparison.png",
        )
    return perf


def _write_site_detection_report(results: list[dict], output_dir: Path) -> None:
    rows = []
    seen: set[tuple[str, str]] = set()
    for r in results:
        pid = str(r.get("AnonPatientID", ""))
        row_key = r.get("target_type") or r.get("structure") or ""
        if (pid, row_key) in seen:
            continue
        seen.add((pid, row_key))
        rows.append(
            {
                "AnonPatientID": pid,
                "structure_or_target": row_key,
                "site_detected": r.get("site_detected", ""),
                "site_histology": r.get("site_histology", ""),
                "site_fractionation": r.get("site_fractionation", ""),
                "site_params_key": r.get("site_params_key", ""),
                "site_confidence": r.get("site_confidence", ""),
                "site_evidence": r.get("site_evidence", ""),
            }
        )
    if rows:
        pd.DataFrame(rows).to_csv(output_dir / "site_detection.csv", index=False)


def run_pipeline(args: argparse.Namespace) -> int:
    """Execute full pipeline; return process exit code."""
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    site_override = getattr(args, "site", None)

    all_results: list[dict] = []

    if args.dicom_dir:
        dicom_root = Path(args.dicom_dir).resolve()
        jobs = list(iter_dicom_patient_jobs(dicom_root))
        if not args.cohort and len(jobs) == 1:
            anon_id, folder, pid_filter = jobs[0]
            all_results = collect_dicom_tcp(
                folder,
                site_override,
                anon_id,
                args.user_config,
                patient_id=pid_filter,
            )
        else:
            for anon_id, folder, pid_filter in jobs:
                try:
                    all_results.extend(
                        collect_dicom_tcp(
                            folder,
                            site_override,
                            anon_id,
                            args.user_config,
                            patient_id=pid_filter,
                        )
                    )
                except Exception as exc:
                    logger.warning("Skipping patient %s: %s", anon_id, exc)

    elif args.dvh_dir:
        all_results = collect_txt_tcp(
            Path(args.dvh_dir).resolve(),
            site_override,
            args.user_config,
            args.dvh_glob,
            args.dose_per_fraction,
        )
    else:
        logger.error("Provide --dicom-dir or --dvh-dir")
        return 2

    if not all_results:
        logger.error("No TCP results produced. Check inputs and site/target settings.")
        return 1

    _write_site_detection_report(all_results, output_dir)
    ml_site = site_override or _dominant_params_site(all_results)

    if not args.no_uncertainty:
        apply_uncertainty_and_hypoxia(all_results, args.user_config, args.n_mc)

    outcomes = None
    if args.outcome_csv:
        outcomes = pd.read_csv(args.outcome_csv)
        _attach_outcomes(all_results, outcomes)

    feat_df = results_to_feature_df(all_results)
    if feat_df.empty and outcomes is not None:
        feat_df = pd.DataFrame(
            [
                {
                    "AnonPatientID": r.get("AnonPatientID"),
                    "target_type": r.get("target_type"),
                    "LocalControl": r.get("LocalControl", np.nan),
                    **{c: r.get(c, np.nan) for c in FEATURE_COLS},
                }
                for r in all_results
                if "LocalControl" in r
            ]
        )
    if not feat_df.empty:
        feat_df.to_csv(output_dir / "cohort_features.csv", index=False)

    perf_metrics: dict = {}
    if not args.no_ml and not feat_df.empty and "LocalControl" in feat_df.columns:
        perf_metrics = run_ml_xai_validation(
            feat_df,
            output_dir,
            ml_site,
            args.user_config,
            ml_augment=not args.no_ml_augment,
        )
        if "TCP_MVL" in feat_df.columns:
            mvl_map = feat_df.set_index("AnonPatientID")["TCP_MVL"].to_dict()
            for r in all_results:
                pid = r.get("AnonPatientID")
                if pid in mvl_map and not pd.isna(mvl_map[pid]):
                    r["TCP_MVL"] = float(mvl_map[pid])
    elif args.figures:
        from outputs.figures import plot_dose_response_curves

        plot_dose_response_curves(
            load_site_params(ml_site, user_config=args.user_config),
            output_path=output_dir / "figures" / f"dose_response_{ml_site}.png",
        )

    from outputs.reporter import print_summary_table, save_benchmarking_excel

    excel_path = output_dir / "tcp_benchmarking.xlsx"
    save_benchmarking_excel(all_results, perf_metrics or None, excel_path)
    print_summary_table(all_results, max_rows=min(30, len(all_results)))
    logger.info("Complete. Outputs: %s", output_dir)
    return 0
