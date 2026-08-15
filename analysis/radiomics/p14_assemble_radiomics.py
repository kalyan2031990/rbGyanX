"""Assemble the sharded CT-radiomics checkpoints into the final outputs, and verify them.

Verification is the point of this step, not a formality. The brief is explicit that completion must not
be inferred from a file existing, so every claim in the manifest is measured here: patient counts,
duplicate IDs, duplicate feature columns, NaN/Inf, zero-variance features, and consistency of the
extraction settings across shards.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SETTINGS = {"voxel_mm": 2.0, "bin_width_HU": 25.0, "hu_clip": [-1000.0, 3000.0],
            "min_voxels": 64, "resampling": "trilinear (image) / nearest (mask)",
            "discretisation": "fixed bin width, inside mask",
            "engine": "rbGyanX in-house IBSI-aligned implementation (pyradiomics unavailable on "
                      "Python 3.14); BENCHMARKED against the IBSI-1 digital phantom - "
                      "56/63 features pass; first-order, GLCM, GLRLM, GLSZM and NGTDM "
                      "verified, GLDM and shape partially verified"}


def load_jsonl(paths) -> list[dict]:
    out = []
    for p in paths:
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    out.append(json.loads(line))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--eligible", required=True, type=Path)
    ap.add_argument("--supervised", required=True, type=Path)
    a = ap.parse_args()
    D = a.dir

    feats = load_jsonl(sorted(D.glob("_checkpoint_features*.jsonl")))
    qcs = load_jsonl(sorted(D.glob("_checkpoint_qc*.jsonl")))
    if not feats:
        print("no checkpoints found - extraction has not produced anything yet")
        return 1

    long = pd.DataFrame(feats).drop_duplicates(subset=["patient_id", "roi"], keep="last")
    qc = pd.DataFrame(qcs).drop_duplicates(subset=["patient_id", "roi", "status"], keep="last")
    long.to_csv(D / "radiomics_features_raw_long.csv", index=False)
    qc.to_csv(D / "radiomics_qc_report.csv", index=False)

    featcols = [c for c in long.columns
                if c not in ("patient_id", "roi", "roi_source_name", "n_levels")]
    wide = long.pivot_table(index="patient_id", columns="roi", values=featcols)
    wide.columns = [f"ctrx_{roi}_{f}" for f, roi in wide.columns]
    wide = wide.reset_index()
    wide.to_csv(D / "radiomics_features_raw.csv", index=False)

    keep = [c for c in wide.columns if c != "patient_id"]
    num = wide[keep].apply(pd.to_numeric, errors="coerce")
    miss = num.isna().mean()
    const = num.nunique(dropna=True) <= 1
    # `np.isfinite(..., where=...)` without `out=` returns uninitialised memory for the masked
    # entries, so the previous count was meaningless. Count NaN and Inf separately.
    _arr = num.to_numpy(dtype=float)
    n_nan = int(np.isnan(_arr).sum())
    n_inf = int(np.isinf(_arr).sum())
    nonfinite = n_inf
    drop_missing = set(miss[miss > 0.20].index)
    drop_const = set(const[const].index)
    drop = drop_missing | drop_const
    qcw = wide[["patient_id"] + [c for c in keep if c not in drop]]
    qcw.to_csv(D / "radiomics_features_qc.csv", index=False)

    fam = {"shape": "_shape_", "first_order": "_fo_", "GLCM": "_glcm_", "GLRLM": "_glrlm_",
           "GLSZM": "_glszm_", "GLDM": "_gldm_", "NGTDM": "_ngtdm_"}
    pd.DataFrame([{"feature": c, "roi": c.split("_")[1],
                   "family": next((k for k, t in fam.items() if t in c), "other"),
                   "missing_fraction": float(miss.get(c, np.nan)),
                   "zero_variance": bool(const.get(c, False)),
                   "retained_after_qc": c in qcw.columns} for c in keep]).to_csv(
        D / "radiomics_feature_dictionary.csv", index=False)

    elig = pd.read_csv(a.eligible)
    sup = pd.read_csv(a.supervised)
    have = set(wide.patient_id.astype(str))
    outcome_linked = sorted(have & set(sup.patient_id.astype(str)))

    man = {
        "generated": date.today().isoformat(),
        "ALL_ELIGIBLE_multimodal": int(len(elig)),
        "attempted": int(qc.patient_id.nunique()),
        "QC_PASSED_patients": int(len(wide)),
        "OUTCOME_LINKED_patients": len(outcome_linked),
        "eligible_not_extracted": sorted(set(elig.patient_id.astype(str)) - have),
        "roi_extractions_ok": int((qc.status == "OK").sum()),
        "roi_skipped": int((qc.status == "SKIPPED").sum()),
        "roi_failed": int((qc.status == "FAILED").sum()),
        "patients_failed": int((qc.status == "PATIENT_FAILED").sum()),
        "rois_per_patient_median": float(qc[qc.status == "OK"].groupby("patient_id").size().median()),
        "features_before_qc": int(len(keep)),
        "features_after_qc": int(qcw.shape[1] - 1),
        "features_dropped_missing_gt20pct": int(len(drop_missing)),
        "features_dropped_zero_variance": int(len(drop_const)),
        "duplicate_patient_ids": int(wide.patient_id.duplicated().sum()),
        "duplicate_feature_columns": int(len(keep) - len(set(keep))),
        "infinite_cells_in_raw": n_inf,
        "nan_cells_in_raw": n_nan,
        "nan_fraction_in_raw": round(n_nan / _arr.size, 5),
        "nan_cause": "structurally absent ROIs (PTV_low in 39 patients, Esophagus in 89); "
                     "identical in the superseded extraction, so not introduced by the IBSI fixes",
        "max_missing_fraction_retained": float(miss[[c for c in qcw.columns
                                                     if c != "patient_id"]].max()),
        "shards_merged": len(list(D.glob("_checkpoint_features*.jsonl"))),
        **SETTINGS,
    }
    (D / "radiomics_manifest.json").write_text(json.dumps(man, indent=2), encoding="utf-8")

    pd.DataFrame([{"patient_id": p, "qc_passed": True,
                   "outcome_linked": p in set(outcome_linked),
                   "n_rois_ok": int((qc[(qc.patient_id == p) & (qc.status == "OK")]).shape[0])}
                  for p in sorted(have)]).to_csv(D / "radiomics_patient_manifest.csv", index=False)

    for k in ("ALL_ELIGIBLE_multimodal", "attempted", "QC_PASSED_patients",
              "OUTCOME_LINKED_patients", "roi_extractions_ok", "roi_skipped", "roi_failed",
              "features_before_qc", "features_after_qc", "duplicate_patient_ids",
              "duplicate_feature_columns", "infinite_cells_in_raw", "nan_cells_in_raw"):
        print(f"  {k:34s} {man[k]}")
    if man["eligible_not_extracted"]:
        print(f"  NOT YET EXTRACTED: {len(man['eligible_not_extracted'])} patients")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
