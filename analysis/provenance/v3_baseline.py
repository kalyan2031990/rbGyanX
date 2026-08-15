"""FINAL_V3 step 0 - read-only baseline manifest, captured BEFORE the Bayesian and IBSI upgrades.

Nothing is modified. Everything downstream is compared against this file, so an unintended numerical
change anywhere is detectable rather than merely unlikely.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

# artefacts whose exact bytes define "the current authoritative result"
TRACKED = [
    "08_Validation_Reports/FINAL_ML_PERFORMANCE_SUMMARY.csv",
    "08_Validation_Reports/FINAL_PINN_SUMMARY.csv",
    "08_Validation_Reports/FINAL_BAYESIAN_NTCP_SUMMARY.csv",
    "08_Validation_Reports/FINAL_DOSIOMICS_SUMMARY.csv",
    "08_Validation_Reports/FINAL_XAI_SUMMARY.csv",
    "05_STATISTICS/FINAL_MODEL_PERFORMANCE.csv",
    "05_STATISTICS/FINAL_RADIOMICS_STATISTICS.csv",
    "05_STATISTICS/statistical_results.csv",
    "05_STATISTICS/descriptive_statistics.csv",
    "01_COHORTS/FINAL_COHORT_SUMMARY.csv",
    "01_COHORTS/FINAL_PATIENT_MANIFEST.csv",
    "03_RADIOMICS/radiomics/radiomics_features_qc.csv",
    "03_RADIOMICS/radiomics/radiomics_manifest.json",
    "04_DOSIOMICS/real_dosiomics_TCIA_HN_wide.csv",
    "02_RBGYANX_VALIDATION/ccs/ccs_results.csv",
    "03_Statistical_Analysis/results_v3_multimodal/p15/P15_feature_family_comparison.csv",
    "03_Statistical_Analysis/results_v2_real_dosiomics/xai_v2/V2_TEXTURE_ABLATION.csv",
]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--repo", required=True, type=Path)
    a = ap.parse_args()
    W, R = a.workspace, a.repo

    try:
        commit = subprocess.run(["git", "-C", str(R), "rev-parse", "HEAD"],
                                capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(R), "status", "--porcelain"],
                               capture_output=True, text=True).stdout.strip().splitlines()
    except Exception:
        commit, dirty = "unavailable", []

    files = {}
    for rel in TRACKED:
        p = W / rel
        files[rel] = ({"sha256": sha256(p), "bytes": p.stat().st_size,
                       "modified_utc": datetime.fromtimestamp(p.stat().st_mtime,
                                                              timezone.utc).isoformat()}
                      if p.is_file() else {"status": "MISSING"})

    coh = json.loads((W / "01_COHORTS" / "FINAL_COHORT_SUMMARY.json").read_text(encoding="utf-8"))
    rad = json.loads((W / "03_RADIOMICS" / "radiomics" /
                      "radiomics_manifest.json").read_text(encoding="utf-8"))
    perf = pd.read_csv(W / "05_STATISTICS" / "FINAL_MODEL_PERFORMANCE.csv")
    bay = pd.read_csv(W / "08_Validation_Reports" / "FINAL_BAYESIAN_NTCP_SUMMARY.csv")
    par = bay[bay.cohort == "Parotid"].iloc[0]
    p15 = pd.read_csv(W / "03_Statistical_Analysis" / "results_v3_multimodal" / "p15" /
                      "P15_feature_family_comparison.csv")
    p15c = p15[p15.status == "COMPUTED"]

    def metric(paradigm_contains, model_contains=None):
        d = perf[perf.paradigm.astype(str).str.contains(paradigm_contains, case=False, na=False)]
        if model_contains:
            d = d[d.model.astype(str).str.contains(model_contains, case=False, na=False)]
        d = d.dropna(subset=["AUC"])
        if not len(d):
            return None
        r = d.nlargest(1, "AUC").iloc[0]
        return {"model": str(r.model), "cohort": str(r.cohort), "AUC": round(float(r.AUC), 4),
                "AUC_lo95": None if pd.isna(r.AUC_lo95) else round(float(r.AUC_lo95), 4),
                "AUC_hi95": None if pd.isna(r.AUC_hi95) else round(float(r.AUC_hi95), 4)}

    base = {
        "captured_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "read-only baseline before the PyMC-Bayesian and IBSI-radiomics upgrades",
        "repository": {"path": str(R), "commit": commit,
                       "uncommitted_changes": len(dirty), "files_changed": dirty[:20]},
        "environment": {"python": "3.14.2", "pymc": "NOT INSTALLED at baseline",
                        "arviz": "NOT INSTALLED at baseline",
                        "pyradiomics": "does not build on Python 3.14",
                        "SimpleITK": "not installed"},
        "cohort_denominators": {
            "Parotid_internal": 54, "SPARK_external": 43, "TCIA_HN_external": 186,
            "total_external": coh["external_n"], "total_validation": coh["total_n"],
            "TCIA_HN_outcome_labelled": 121,
            "TCIA_multimodal_eligible": rad["ALL_ELIGIBLE_multimodal"],
            "TCIA_multimodal_outcome_linked": rad["OUTCOME_LINKED_patients"],
            "TCIA_multimodal_modellable": 114,
            "TCIA_Lung": "EXCLUDED",
        },
        "model_metrics": {
            "ML_nested_TCIA_HN": {"AUC": 0.699, "CI": [0.567, 0.826],
                                  "note": "authoritative; 0.724 superseded"},
            "ML_Parotid_best": metric("Machine learning", "elasticnet"),
            "logistic_Parotid": metric("logistic"),
            "PINN_v2c": {"AUC": 0.648, "CI": [0.492, 0.796], "Brier": 0.134},
            "classical_Parotid_LKB": metric("Classical"),
        },
        "radiomics_metrics": {
            "QC_PASSED": rad["QC_PASSED_patients"],
            "OUTCOME_LINKED": rad["OUTCOME_LINKED_patients"],
            "roi_extractions_ok": rad["roi_extractions_ok"],
            "roi_skipped": rad["roi_skipped"], "roi_failed": rad["roi_failed"],
            "features_before_qc": rad["features_before_qc"],
            "features_after_qc": rad["features_after_qc"],
            "voxel_mm": rad["voxel_mm"], "bin_width_HU": rad["bin_width_HU"],
            "hu_clip": rad["hu_clip"], "min_voxels": rad["min_voxels"],
            "engine": rad["engine"],
            "univariable_raw_p_lt_05": 85, "univariable_BH_significant": 0,
            "min_q": 0.648,
            "family_comparison": {r.arm: {"model": r.model, "AUC": round(float(r.cv_AUC), 4),
                                          "CI": [round(float(r.auc_lo95), 4),
                                                 round(float(r.auc_hi95), 4)]}
                                  for _, r in p15c.iterrows()},
        },
        "bayesian_baseline": {
            "method": str(par.method),
            "IS_GENUINE_BAYESIAN": False,
            "cohort": "Parotid", "n": int(par.n), "events": int(par.events),
            "TD50_gy": round(float(par.TD50_gy), 3),
            "TD50_CI": [round(float(par["TD50_CI2.5"]), 3), round(float(par["TD50_CI97.5"]), 3)],
            "m": round(float(par.m), 3), "m_at_bound": bool(par.m_at_bound),
            "interval_type": "percentile bootstrap CONFIDENCE interval, not credible",
            "verdict": str(par.verdict),
            "exploratory_fits": int((~bay.is_valid_ntcp_endpoint.astype(bool)).sum()),
        },
        "test_results_baseline": {
            "working_repo": {"passed": 818, "skipped": 3, "failed": 0},
            "release_candidate": {"passed": 817, "skipped": 4, "failed": 0},
        },
        "qc_baseline": {"pass": 30, "fail": 0},
        "file_hashes": files,
    }
    out = W / "00_FINAL_AUDIT" / "PRE_BAYESIAN_IBSI_BASELINE.json"
    out.write_text(json.dumps(base, indent=2), encoding="utf-8")
    print(f"baseline captured: {out.name}")
    print(f"  tracked files hashed: {sum(1 for v in files.values() if 'sha256' in v)}/{len(files)}")
    print(f"  cohorts: {base['cohort_denominators']}")
    print(f"  bayesian baseline: {base['bayesian_baseline']['method'][:60]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
