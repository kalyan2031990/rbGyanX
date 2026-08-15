"""T3 - link the clinical tables to the imaging chain and record outcome availability.

Three collections reach T2 with a complete imaging chain, and they do NOT share a clinical source:

  * **Head-Neck-PET-CT** (`HN-CHUM/CHUS/HGJ/HMR-*`) - `Head-Neck-PET-CT.xlsx`, which is a FOUR-SHEET
    workbook (one per centre) plus an `Excluded` sheet. Reading only the first sheet yields 97 of 322
    records and silently drops three centres; this script reads every sheet.
  * **Head-Neck Cetuximab** (`0522c*`) - the only file shipped for this collection,
    `Head-Neck_Cetuximab.csv`, is a TCIA *series manifest* (Series UID, Modality, File Size). It carries
    no covariate and no outcome. Unless an RTOG-0522 clinical table is added, these patients are
    imaging-only.
  * **HNSCC-3DCT-RT** (`HN_P*`) - `HNSCC-3DCT-RT.xls` holds CT acquisition timing and slice counts only.
    No covariate, no outcome.

`HNSCC.csv` and `HNSCC-MDA-Data_update_20240514.xlsx` describe the MD Anderson `HNSCC-01-*` collection,
which contributes **no** chain-complete patient, so neither is used.

Nothing is imputed and no identifier is fuzzy-matched: a patient either has a clinical record under its
exact DICOM PatientID or it is recorded as having none.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

PETCT_SHEETS = ("HGJ", "CHUS", "HMR", "CHUM")


def yn(v):
    """TCIA outcome cells are 0/1, 'Yes'/'No', or blank."""
    s = str(v).strip().lower()
    if s in ("1", "1.0", "yes", "y", "true"):
        return 1.0
    if s in ("0", "0.0", "no", "n", "false"):
        return 0.0
    return np.nan


def stage_num(s):
    s = str(s or "").upper().replace("STAGE", "").strip()
    for k, v in (("IVC", 4), ("IVB", 4), ("IVA", 4), ("IV", 4), ("III", 3), ("II", 2), ("I", 1)):
        if s.startswith(k):
            return float(v)
    return np.nan


def load_petct(path: Path) -> pd.DataFrame:
    xl = pd.ExcelFile(path)
    frames = []
    for sh in xl.sheet_names:
        d = xl.parse(sh)
        if "Patient #" not in d.columns:
            continue
        d = d.copy()
        d["source_sheet"] = sh
        d["clinical_excluded_by_source"] = (sh.lower() == "excluded")
        frames.append(d)
    d = pd.concat(frames, ignore_index=True)
    d["patient_id"] = d["Patient #"].astype(str).str.strip()
    out = pd.DataFrame({
        "patient_id": d.patient_id,
        "clin_source": "Head-Neck-PET-CT.xlsx",
        "clin_sheet": d.source_sheet,
        "clinical_excluded_by_source": d.clinical_excluded_by_source,
        "clin_sex_M": d["Sex"].astype(str).str.upper().str.startswith("M").astype(float),
        "clin_age": pd.to_numeric(d["Age"], errors="coerce"),
        "clin_primary_site": d["Primary Site"].astype(str),
        "clin_t_stage": d["T-stage"].astype(str),
        "clin_n_stage": d["N-stage"].astype(str),
        "clin_m_stage": d["M-stage"].astype(str),
        "clin_stage_group": d["TNM group stage"].astype(str),
        "clin_stage_num": d["TNM group stage"].map(stage_num),
        "clin_hpv_status": d["HPV status"].astype(str),
        "clin_therapy": d["Therapy"].astype(str),
        "clin_followup_days": pd.to_numeric(
            d.get("Time – diagnosis to last follow-up(days)"), errors="coerce"),
        "outcome_locoregional": d["Locoregional"].map(yn),
        "outcome_distant": d["Distant"].map(yn),
        "outcome_death": d["Death"].map(yn),
    })
    return out.drop_duplicates("patient_id", keep="first")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chain", required=True, type=Path)
    ap.add_argument("--clinical-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    chain = pd.read_csv(a.chain, low_memory=False)
    chain["patient_id"] = chain.patient_id.astype(str).str.strip()

    pet = load_petct(a.clinical_dir / "Head-Neck-PET-CT.xlsx")
    pet.to_csv(a.out / "T3_clinical_petct_all_sheets.csv", index=False)

    # collection label from the DICOM PatientID pattern
    def collection(p: str) -> str:
        if p.startswith("0522c"):
            return "Head-Neck Cetuximab"
        if p.startswith("HN_P"):
            return "HNSCC-3DCT-RT"
        if p.startswith("HN-"):
            return "Head-Neck-PET-CT"
        if p.startswith("HNSCC-"):
            return "HNSCC (MD Anderson)"
        if p.upper().startswith("LUNG"):
            return "Lung (excluded by protocol)"
        return "other"

    chain["collection"] = chain.patient_id.map(collection)
    m = chain.merge(pet, on="patient_id", how="left")

    m["has_clinical_record"] = m.clin_source.notna()
    m["has_any_covariate"] = m[["clin_age", "clin_sex_M", "clin_stage_num"]].notna().any(axis=1)
    m["has_outcome_locoregional"] = m.outcome_locoregional.notna()
    m["has_any_outcome"] = m[["outcome_locoregional", "outcome_distant",
                              "outcome_death"]].notna().any(axis=1)

    def why(r):
        if r.has_clinical_record:
            return "" if r.has_any_outcome else "clinical record present but every outcome cell blank"
        return {
            "Head-Neck Cetuximab": "no clinical table shipped - Head-Neck_Cetuximab.csv is a series "
                                   "manifest (Series UID / Modality / File Size), not clinical data",
            "HNSCC-3DCT-RT": "HNSCC-3DCT-RT.xls holds CT acquisition timing only - no covariate, "
                             "no outcome",
            "Head-Neck-PET-CT": "PatientID absent from all four centre sheets",
            "HNSCC (MD Anderson)": "clinical exists but this collection contributes no imaging chain",
            "Lung (excluded by protocol)": "lung cohort - excluded by protocol",
        }.get(r.collection, "no clinical source for this collection")
    m["clinical_gap_reason"] = m.apply(why, axis=1)

    m.to_csv(a.out / "T3_chain_with_clinical.csv", index=False)

    ok = m[m.chain_complete]
    by = (ok.groupby("collection")
            .agg(chain_complete=("patient_id", "size"),
                 with_clinical=("has_clinical_record", "sum"),
                 with_covariates=("has_any_covariate", "sum"),
                 with_locoregional=("has_outcome_locoregional", "sum"),
                 with_any_outcome=("has_any_outcome", "sum"))
            .reset_index())
    by.to_csv(a.out / "T3_clinical_by_collection.csv", index=False)

    summary = {
        "chain_complete": int(len(ok)),
        "with_clinical_record": int(ok.has_clinical_record.sum()),
        "with_covariates": int(ok.has_any_covariate.sum()),
        "with_locoregional_outcome": int(ok.has_outcome_locoregional.sum()),
        "with_any_outcome": int(ok.has_any_outcome.sum()),
        "flagged_excluded_by_clinical_source": int(
            ok.clinical_excluded_by_source.fillna(False).astype(bool).sum()),
        "by_collection": by.to_dict("records"),
        "clinical_sources_read": {
            "Head-Neck-PET-CT.xlsx": {"sheets": list(PETCT_SHEETS) + ["Excluded"],
                                      "records": int(len(pet))},
            "Head-Neck_Cetuximab.csv": "series manifest - NOT clinical, not used",
            "HNSCC-3DCT-RT.xls": "CT timing only - no covariate/outcome, not used",
            "HNSCC.csv / HNSCC-MDA-Data_update_20240514.xlsx":
                "MD Anderson HNSCC-01-* - contributes no chain-complete patient, not used",
        },
        "outcome_gap_reasons": ok.loc[~ok.has_any_outcome, "clinical_gap_reason"]
                                 .value_counts().to_dict(),
    }
    (a.out / "T3_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
