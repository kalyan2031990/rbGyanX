"""T4 - eligibility waterfall and the locked analysis cohorts.

Two tiers, because they need different things and conflating them is how a cohort count drifts:

  **Tier A - dose-only.** RTDOSE 3-D grid -> RTPLAN -> RTSTRUCT. This is all that DVH extraction,
  TCP/NTCP, and *dose* dosiomics require. A CT is not needed: the dose grid carries its own geometry
  and the structure set rasterises onto it.

  **Tier B - multimodal.** Tier A **plus** a usable CT series that the structure set actually
  references, in the same frame of reference as the dose grid. Only Tier B supports CT radiomics and
  CT-dose fusion.

Each tier is then split by outcome availability, since supervised modelling may only use the labelled
subset. Every excluded patient carries a reason code; nothing is dropped silently.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True, type=Path, help="results_v3_multimodal")
    a = ap.parse_args()
    D = a.dir

    idx = pd.read_csv(D / "T1_dicom_index.csv", low_memory=False)
    rs = pd.read_csv(D / "T2_rtstruct_links.csv", low_memory=False)
    rp = pd.read_csv(D / "T2_rtplan_links.csv", low_memory=False)
    rd = pd.read_csv(D / "T2_rtdose_links.csv", low_memory=False)
    clin = pd.read_csv(D / "T3_chain_with_clinical.csv", low_memory=False)
    for f in (idx, rs, rp, rd, clin):
        f["patient_id"] = f["patient_id"].astype(str).str.strip()

    # ---- Tier A: dose grid -> plan -> structure set (CT NOT required) -----------------------
    rs_sops = set(rs.sop_uid.astype(str))
    plan_ok = rp[rp["ref_structset_sop"].astype(str).isin(rs_sops)]
    plan_ok_sops = set(plan_ok.sop_uid.astype(str))
    doseA = rd[rd.is_grid & rd["ref_plan_sop"].astype(str).isin(plan_ok_sops)]
    tierA = set(doseA.patient_id)

    tierB = set(clin.loc[clin.chain_complete, "patient_id"])

    # ---- per-patient record ------------------------------------------------------------------
    # Protocol exclusion of the lung cohort is decided by SOURCE ARCHIVE, not by an ID pattern: the
    # lung PatientIDs are '0617-xxxxxx', which no prefix rule would have caught, and 70 of them
    # would otherwise have been carried forward as "other".
    lung_zip = "Lung_valid_RTPLAN+RTDOSE.zip"
    lung_only = (set(idx.loc[idx.zip == lung_zip, "patient_id"])
                 - set(idx.loc[idx.zip != lung_zip, "patient_id"]))

    rows = []
    for pid, g in clin.groupby("patient_id"):
        r = g.iloc[0]
        coll = "Lung (excluded by protocol)" if pid in lung_only else r.collection
        excl_protocol = pid in lung_only
        rec = {
            "patient_id": pid, "collection": coll,
            "excluded_by_protocol": excl_protocol,
            "tierA_dose_only": pid in tierA,
            "tierB_multimodal": pid in tierB,
            "has_clinical_record": bool(r.has_clinical_record),
            "has_locoregional_outcome": bool(r.has_outcome_locoregional),
            "has_any_outcome": bool(r.has_any_outcome),
            "n_ct_series_usable": int(r.n_ct_series_usable),
            "n_rois": r.n_rois, "n_fractions_planned": r.n_fractions_planned,
            "target_prescription_gy": r.target_prescription_gy,
            "chain_reason": r.reason, "clinical_gap_reason": r.clinical_gap_reason,
        }
        if excl_protocol:
            rec["exclusion"] = "EX0 lung cohort - excluded by protocol"
        elif not rec["tierA_dose_only"]:
            rec["exclusion"] = "EX1 no linked RTDOSE grid -> RTPLAN -> RTSTRUCT chain"
        elif not rec["tierB_multimodal"]:
            rec["exclusion"] = "EX2 Tier A only - " + (r.reason or "no usable CT link")
        else:
            rec["exclusion"] = ""
        rows.append(rec)
    pat = pd.DataFrame(rows).sort_values(["collection", "patient_id"])
    pat.to_csv(D / "T4_patient_eligibility.csv", index=False)

    # ---- waterfall ---------------------------------------------------------------------------
    nonlung = pat[~pat.excluded_by_protocol]
    steps = [
        ("S0  unique PatientIDs in the archives", int(len(pat))),
        ("S1  after protocol exclusion of the lung cohort", int(len(nonlung))),
        ("S2  with any RTDOSE instance", int(nonlung.patient_id.isin(
            set(rd.patient_id)).sum())),
        ("S3  RTDOSE carries a 3-D grid", int(nonlung.patient_id.isin(
            set(rd[rd.is_grid].patient_id)).sum())),
        ("S4  dose grid links to an RTPLAN present in the archives", int(nonlung.patient_id.isin(
            set(rd[rd.is_grid & rd.ref_rp_present_any].patient_id)).sum())),
        ("S5  that plan links to an RTSTRUCT present in the archives  = TIER A",
         int(nonlung.tierA_dose_only.sum())),
        ("S6  Tier A and the patient has a CT in the archives", int(
            nonlung[nonlung.tierA_dose_only].patient_id.isin(
                set(idx[idx.modality == "CT"].patient_id)).sum())),
        ("S7  that CT forms a usable series (>=40 slices, uniform in-plane geometry, no duplicate "
         "slice positions, largest z gap <=6 mm)",
         int(((nonlung.tierA_dose_only) & (nonlung.n_ct_series_usable > 0)).sum())),
        ("S8  the RTSTRUCT actually references that CT series and the dose shares its "
         "FrameOfReferenceUID  = TIER B", int(nonlung.tierB_multimodal.sum())),
        ("S9  Tier B and a clinical record exists", int(
            (nonlung.tierB_multimodal & nonlung.has_clinical_record).sum())),
        ("S10 Tier B and a loco-regional outcome exists  = SUPERVISED COHORT", int(
            (nonlung.tierB_multimodal & nonlung.has_locoregional_outcome).sum())),
    ]
    wf = pd.DataFrame(steps, columns=["step", "n"])
    wf["lost"] = [0] + [steps[i - 1][1] - steps[i][1] for i in range(1, len(steps))]
    wf.to_csv(D / "T4_eligibility_waterfall.csv", index=False)

    # ---- locked cohort lists ------------------------------------------------------------------
    for name, sel in (
            ("TIER_A_dose_only", nonlung[nonlung.tierA_dose_only]),
            ("TIER_B_multimodal", nonlung[nonlung.tierB_multimodal]),
            ("TIER_B_supervised", nonlung[nonlung.tierB_multimodal &
                                          nonlung.has_locoregional_outcome])):
        sel[["patient_id", "collection", "n_ct_series_usable", "n_rois",
             "n_fractions_planned", "target_prescription_gy",
             "has_clinical_record", "has_locoregional_outcome"]].to_csv(
            D / f"T4_cohort_{name}.csv", index=False)

    summary = {
        "waterfall": wf.to_dict("records"),
        "locked_cohorts": {
            "TIER_A_dose_only": int(nonlung.tierA_dose_only.sum()),
            "TIER_B_multimodal": int(nonlung.tierB_multimodal.sum()),
            "TIER_B_supervised": int((nonlung.tierB_multimodal &
                                      nonlung.has_locoregional_outcome).sum()),
            "TIER_A_supervised": int((nonlung.tierA_dose_only &
                                      nonlung.has_locoregional_outcome).sum()),
        },
        "by_collection": nonlung.groupby("collection").agg(
            n=("patient_id", "size"), tierA=("tierA_dose_only", "sum"),
            tierB=("tierB_multimodal", "sum"),
            with_outcome=("has_locoregional_outcome", "sum")).reset_index().to_dict("records"),
        "exclusion_codes": pat.loc[pat.exclusion != "", "exclusion"]
                              .str.slice(0, 3).value_counts().to_dict(),
    }
    (D / "T4_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(wf.to_string(index=False))
    print()
    print(json.dumps(summary["locked_cohorts"], indent=2))
    print()
    print(pd.DataFrame(summary["by_collection"]).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
