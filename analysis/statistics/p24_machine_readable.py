"""Phase 24 - emit the machine-readable result tables in a single consistent schema.

Every long-format table carries the same provenance columns so a downstream reader can join, filter and
audit without opening a report:

    patient_id | cohort | endpoint | feature_or_model | value | units |
    analysis_version | software_version | analysis_date

`patient_id` is always a pseudonym or a TCIA de-identified collection ID; no PHI is emitted. Wide
tables (feature matrices) keep their native shape but gain a sidecar dictionary.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SW_VERSION = "rbGyanX 1.0.0 (b2a81be + 5 working-tree fixes)"
TODAY = date.today().isoformat()
PROV = ["analysis_version", "software_version", "analysis_date"]


def long_rows(df: pd.DataFrame, id_col: str, cohort, endpoint, cols, kind, version,
              units_fn=lambda c: "") -> pd.DataFrame:
    out = []
    for _, r in df.iterrows():
        for c in cols:
            v = r.get(c)
            if pd.isna(v):
                continue
            out.append({"patient_id": r[id_col],
                        "cohort": cohort if isinstance(cohort, str) else r[cohort],
                        "endpoint": endpoint, "kind": kind, "feature_or_model": c,
                        "value": float(v) if isinstance(v, (int, float, np.floating)) else v,
                        "units": units_fn(c), "analysis_version": version,
                        "software_version": SW_VERSION, "analysis_date": TODAY})
    return pd.DataFrame(out)


def units_for(c: str) -> str:
    lc = c.lower()
    if lc.startswith(("ntcp", "tcp", "untcp")) or "_prob" in lc:
        return "probability"
    if lc.endswith("_gy") or "_gy_" in lc:
        return "Gy"
    if "volume_cc" in lc:
        return "cm3"
    if "_pct" in lc or lc.endswith("_hi") or lc.endswith("_ci"):
        return "ratio"
    return "arbitrary"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    W, O = a.workspace, a.out
    O.mkdir(parents=True, exist_ok=True)
    V2 = W / "03_Statistical_Analysis" / "results_v2_real_dosiomics"
    V3 = W / "03_Statistical_Analysis" / "results_v3_multimodal"
    VR = W / "08_Validation_Reports"
    written = {}

    def put(name, df):
        df.to_csv(O / name, index=False)
        written[name] = int(len(df))

    master = pd.read_csv(W / "03_Statistical_Analysis" / "feature_tables" /
                         "patient_features_ALL.csv", low_memory=False)
    master = master.rename(columns={"pseudonym": "patient_id"})

    # ---- patient master + cohort manifest ------------------------------------------------
    put("patient_master.csv", master.assign(analysis_version="v2", software_version=SW_VERSION,
                                            analysis_date=TODAY))
    cm = pd.read_csv(V3 / "cohort_audit" / "FINAL_COHORT_SUMMARY.csv")
    put("cohort_manifest.csv", cm.assign(analysis_version="v2", software_version=SW_VERSION,
                                         analysis_date=TODAY))

    # ---- classical radiobiology, TCP, NTCP, uncertainty ----------------------------------
    ntcp_c = [c for c in master.columns if c.startswith("NTCP__")]
    tcp_c = [c for c in master.columns if c.startswith("TCP__")]
    unc_c = [c for c in master.columns if c.startswith("uNTCP__") or c.startswith("uTCP__")]
    phys_c = [c for c in master.columns
              if any(k in c for k in ("__Dmean_gy", "__Dmax_gy", "__D2_gy", "__D98_gy",
                                      "__gEUD", "__EQD2", "__BED", "__HI", "__CI", "__GI_pct",
                                      "volume_cc"))]
    put("ntcp_results.csv", long_rows(master, "patient_id", "cohort", "organ toxicity",
                                      ntcp_c, "NTCP", "v2", units_for))
    put("tcp_results.csv", long_rows(master, "patient_id", "cohort", "local control",
                                     tcp_c, "TCP", "v2", units_for))
    put("uncertainty_results.csv", long_rows(master, "patient_id", "cohort", "MC parameter uncertainty",
                                             unc_c, "uncertainty", "v2", units_for))
    put("classical_radiobiology.csv", long_rows(master, "patient_id", "cohort", "dose/plan metric",
                                                phys_c, "physical", "v2", units_for))

    # ---- clinical outcomes ----------------------------------------------------------------
    oc = [c for c in master.columns if c.startswith("outcome_")]
    put("clinical_outcomes.csv", long_rows(master, "patient_id", "cohort", "outcome", oc,
                                           "outcome", "v2", lambda c: "binary"))

    # ---- CCS -------------------------------------------------------------------------------
    for src, name in ((V3 / "ccs" / "ccs_results.csv", "ccs_results.csv"),
                      (V3 / "ccs" / "ccs_per_patient.csv", "ccs_per_patient.csv")):
        if src.is_file():
            d = pd.read_csv(src)
            put(name, d.assign(analysis_version="v3", software_version=SW_VERSION,
                               analysis_date=TODAY))

    # ---- model performance tables ----------------------------------------------------------
    frames = []
    for src, kind, ver in ((VR / "FINAL_ML_PERFORMANCE_SUMMARY.csv", "ML", "v2"),
                           (VR / "FINAL_PINN_SUMMARY.csv", "PINN", "v2c"),
                           (VR / "FINAL_BAYESIAN_NTCP_SUMMARY.csv", "Bayesian-MLE", "v2")):
        if src.is_file():
            d = pd.read_csv(src)
            d["kind"] = kind
            frames.append(d.assign(analysis_version=ver, software_version=SW_VERSION,
                                   analysis_date=TODAY))
            put({"ML": "ml_results.csv", "PINN": "pinn_results.csv",
                 "Bayesian-MLE": "bayesian_results.csv"}[kind], d)
    if frames:
        put("model_performance.csv", pd.concat(frames, ignore_index=True, sort=False))

    # logistic arms are the dose-only reference rows inside the ML table
    ml = pd.read_csv(VR / "FINAL_ML_PERFORMANCE_SUMMARY.csv")
    if "model" in ml.columns:
        put("logistic_results.csv", ml[ml.model.astype(str).str.contains("logistic", case=False,
                                                                         na=False)]
            .assign(analysis_version="v2", software_version=SW_VERSION, analysis_date=TODAY))

    # ---- XAI --------------------------------------------------------------------------------
    xa = []
    for f, coh, ep in ((V2 / "xai_v2" / "V2_XAI_shap_global_TCIA_HN_locoregional.csv",
                        "TCIA_HN", "locoregional failure"),
                       (V2 / "xai_v2" / "V2_XAI_shap_global_Parotid_xerostomia_g2plus.csv",
                        "Parotid", "xerostomia G>=2")):
        if f.is_file():
            d = pd.read_csv(f)
            d["cohort"], d["endpoint"] = coh, ep
            xa.append(d)
    if xa:
        put("xai_results.csv", pd.concat(xa, ignore_index=True, sort=False)
            .assign(analysis_version="v2", software_version=SW_VERSION, analysis_date=TODAY))

    # ---- dosiomics + radiomics ---------------------------------------------------------------
    dos = V2 / "real_dosiomics_TCIA_HN_wide.csv"
    if dos.is_file():
        d = pd.read_csv(dos, low_memory=False).rename(columns={"pseudonym": "patient_id"})
        put("dosiomics_features.csv", d.assign(cohort="TCIA_HN", analysis_version="v2",
                                               software_version=SW_VERSION, analysis_date=TODAY))
    rad = V3 / "radiomics" / "radiomics_features_qc.csv"
    if rad.is_file():
        put("radiomics_features.csv", pd.read_csv(rad, low_memory=False)
            .assign(cohort="TCIA_HN_multimodal", analysis_version="v3",
                    software_version=SW_VERSION, analysis_date=TODAY))
        put("radiomics_qc.csv", pd.read_csv(V3 / "radiomics" / "radiomics_qc_report.csv")
            .assign(analysis_version="v3", software_version=SW_VERSION, analysis_date=TODAY))
    else:
        written["radiomics_features.csv"] = "NOT AVAILABLE - extraction not finished"

    # ---- statistics ---------------------------------------------------------------------------
    st = W / "05_STATISTICS" / "statistical_results.csv"
    if st.is_file():
        put("statistical_results.csv", pd.read_csv(st).assign(
            analysis_version="v3", software_version=SW_VERSION, analysis_date=TODAY))

    # ---- combined feature matrix for the supervised TCIA cohort --------------------------------
    frame = V2 / "pinn_v2" / "V2_PINN_input_features.csv"
    if frame.is_file():
        cf = pd.read_csv(frame, low_memory=False).rename(columns={"pseudonym": "patient_id"})
        if rad.is_file():
            r = pd.read_csv(rad, low_memory=False)
            pm = W / "09_Audit_Trail" / "_pseudonym_maps" / "TCIA_HN_pseudonym_map.csv"
            if pm.is_file():
                # the radiomics matrix is keyed by TCIA PatientID; the modelling frame by pseudonym
                m = pd.read_csv(pm)[["raw_patient_key", "pseudonym"]]
                r = r.merge(m, left_on="patient_id", right_on="raw_patient_key", how="inner")
                r = r.drop(columns=["patient_id", "raw_patient_key"]).rename(
                    columns={"pseudonym": "patient_id"})
                cf = cf.merge(r, on="patient_id", how="left")
        put("combined_features.csv", cf.assign(cohort="TCIA_HN", analysis_version="v3",
                                               software_version=SW_VERSION, analysis_date=TODAY))

    (O / "OUTPUTS_MANIFEST.json").write_text(json.dumps(
        {"generated": TODAY, "software_version": SW_VERSION,
         "schema": "patient_id | cohort | endpoint | kind | feature_or_model | value | units | "
                   "analysis_version | software_version | analysis_date",
         "no_PHI": True, "tables": written}, indent=2), encoding="utf-8")
    for k, v in written.items():
        print(f"  {k:34s} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
