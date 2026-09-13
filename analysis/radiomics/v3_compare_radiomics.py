"""Compare the pre-IBSI (V2) and IBSI-corrected (V3) radiomics extractions, feature by feature.

The point is to quantify what the IBSI fixes actually changed, so the manuscript can state it rather
than assert that "the numbers moved a bit". Families the audit did not touch should be identical to
floating-point noise; if they are not, that is a regression and this script will show it.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

FAMILY_TOKENS = {"shape": "_shape_", "first_order": "_fo_", "GLCM": "_glcm_", "GLRLM": "_glrlm_",
                 "GLSZM": "_glszm_", "GLDM": "_gldm_", "NGTDM": "_ngtdm_"}
EXPECTED = {
    "first_order": "CHANGED - skewness/kurtosis now use population moments",
    "GLSZM": "CHANGED - zone labelling moved from 6- to 26-connectivity",
    "GLRLM": "CHANGED - 3 axis directions replaced by the 13 IBSI directions",
    "GLCM": "UNCHANGED expected - no code change, only the benchmark mapping was corrected",
    "GLDM": "UNCHANGED expected",
    "NGTDM": "UNCHANGED expected",
    "shape": "UNCHANGED expected",
}


def family_of(col: str) -> str:
    for fam, tok in FAMILY_TOKENS.items():
        if tok in col:
            return fam
    return "other"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", required=True, type=Path)
    ap.add_argument("--new", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    old = pd.read_csv(a.old, low_memory=False).set_index("patient_id").sort_index()
    new = pd.read_csv(a.new, low_memory=False).set_index("patient_id").sort_index()
    shared_p = old.index.intersection(new.index)
    shared_c = [c for c in old.columns if c in new.columns]

    rows = []
    for c in shared_c:
        o = pd.to_numeric(old.loc[shared_p, c], errors="coerce")
        n = pd.to_numeric(new.loc[shared_p, c], errors="coerce")
        m = o.notna() & n.notna()
        if m.sum() < 5:
            continue
        d = (n[m] - o[m]).abs()
        denom = o[m].abs().replace(0, np.nan)
        rel = (d / denom).replace([np.inf, -np.inf], np.nan)
        rows.append({
            "feature": c, "family": family_of(c), "n_compared": int(m.sum()),
            "identical": bool(np.allclose(o[m], n[m], rtol=1e-9, atol=1e-12)),
            "max_abs_diff": float(d.max()), "median_abs_diff": float(d.median()),
            "median_rel_diff": float(rel.median()) if rel.notna().any() else np.nan,
            "spearman_old_new": float(o[m].corr(n[m], method="spearman")),
        })
    cmp = pd.DataFrame(rows)
    cmp.to_csv(a.out / "V2_vs_V3_feature_comparison.csv", index=False)

    fam = cmp.groupby("family").agg(
        features=("feature", "size"),
        identical=("identical", "sum"),
        changed=("identical", lambda s: int((~s).sum())),
        median_rel_diff=("median_rel_diff", "median"),
        min_spearman=("spearman_old_new", "min")).reset_index()
    fam["expectation"] = fam.family.map(EXPECTED)
    fam["matches_expectation"] = fam.apply(
        lambda r: (("CHANGED" in str(r.expectation) and r.changed > 0)
                   or ("UNCHANGED" in str(r.expectation) and r.changed == 0)), axis=1)
    fam.to_csv(a.out / "V2_vs_V3_family_summary.csv", index=False)

    summary = {
        "patients_compared": int(len(shared_p)),
        "features_compared": int(len(cmp)),
        "features_identical": int(cmp.identical.sum()),
        "features_changed": int((~cmp.identical).sum()),
        "old_only_columns": int(len([c for c in old.columns if c not in new.columns])),
        "new_only_columns": int(len([c for c in new.columns if c not in old.columns])),
        "families": fam.to_dict("records"),
        "unexpected_families": fam.loc[~fam.matches_expectation, "family"].tolist(),
    }
    (a.out / "V2_vs_V3_summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                                 encoding="utf-8")
    print(fam.to_string(index=False))
    print(f"\npatients {summary['patients_compared']} | features {summary['features_compared']} | "
          f"identical {summary['features_identical']} | changed {summary['features_changed']}")
    if summary["unexpected_families"]:
        print("UNEXPECTED:", summary["unexpected_families"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
