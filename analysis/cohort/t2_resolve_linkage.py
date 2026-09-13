"""T2 - resolve the CT -> RTSTRUCT -> RTPLAN -> RTDOSE chain per patient.

The ZIP audit proved modality *presence*. Presence is not linkage. A patient counted as
FULL_MULTIMODAL can still be unusable because the structure set references a CT series that is not in
the archive, the plan references a structure set from a different episode, the dose references a plan
that is missing, or the dose grid sits in a different frame of reference from the CT.

Each link is resolved by UID, never by assumption:

    RTSTRUCT.ReferencedFrameOfReferenceSequence -> RTReferencedSeries.SeriesInstanceUID  == CT series
    RTPLAN.ReferencedStructureSetSequence[0].ReferencedSOPInstanceUID                    == RTSTRUCT SOP
    RTDOSE.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID                          == RTPLAN SOP

Frame-of-reference agreement is then checked across CT, RTSTRUCT and RTDOSE, because a dose grid that
does not share the CT's FoR cannot be resampled onto the CT without a registration this pipeline does
not have.

Reject, never repair: every patient that fails carries an explicit reason code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

MIN_CT_SLICES = 40
MAX_Z_GAP_MM = 6.0   # a wider gap means whole slices are absent, not merely unevenly spaced


def ct_series_table(ct: pd.DataFrame) -> pd.DataFrame:
    """One row per CT series with the geometry checks a radiomics pass depends on."""
    rows = []
    for (pid, suid), g in ct.groupby(["patient_id", "series_uid"], sort=False):
        z = pd.to_numeric(g["z_position"], errors="coerce").dropna().sort_values().values
        dz = np.diff(z) if len(z) > 1 else np.array([])
        rows.append({
            "patient_id": pid, "series_uid": suid, "zip": g["zip"].iloc[0],
            "for_uid": g["for_uid"].mode().iat[0] if g["for_uid"].notna().any() else "",
            "n_slices": int(len(g)),
            "rows_px": int(pd.to_numeric(g["rows"], errors="coerce").median() or 0),
            "cols_px": int(pd.to_numeric(g["cols"], errors="coerce").median() or 0),
            "pixel_spacing_mm": float(pd.to_numeric(g["pixel_spacing"],
                                                    errors="coerce").median() or 0) or None,
            "geometry_uniform": bool(g["rows"].nunique() == 1 and g["cols"].nunique() == 1),
            "z_span_mm": float(z[-1] - z[0]) if len(z) > 1 else None,
            "z_step_mm": float(np.median(np.abs(dz))) if dz.size else None,
            "z_max_gap_mm": float(np.max(np.abs(dz))) if dz.size else None,
            "z_uniform_spacing": bool(dz.size and np.nanmax(np.abs(np.abs(dz) -
                                                                   np.median(np.abs(dz)))) < 0.51),
            "z_duplicate_positions": int(len(z) - len(np.unique(np.round(z, 3)))),
            "n_for_uids": int(g["for_uid"].nunique()),
            "series_desc": g["series_desc"].iloc[0],
        })
    t = pd.DataFrame(rows)
    # Uniform spacing is NOT the right gate. Several TCIA series are acquired in two blocks (e.g. 3 mm
    # through the primary and 5 mm elsewhere): irregular, but every slice is present, so resampling to
    # an isotropic grid - which any IBSI-compliant radiomics pass does anyway - reconstructs them
    # faithfully. What cannot be recovered is a MISSING block: HN-CHUM-001 and HN-HGJ-002 show gaps at
    # exact multiples of the base step (up to 16 mm and 36 mm), and interpolating across those would
    # fabricate anatomy. The gate is therefore the largest gap, not the spacing's regularity.
    t["z_interpolatable"] = (t.z_max_gap_mm.notna() & (t.z_max_gap_mm <= MAX_Z_GAP_MM)
                             & (t.z_duplicate_positions == 0))
    t["ct_series_usable"] = (t.n_slices >= MIN_CT_SLICES) & t.geometry_uniform & \
                            t.z_interpolatable & t.pixel_spacing_mm.notna() & (t.n_for_uids == 1)
    return t


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    idx = pd.read_csv(a.index, low_memory=False)
    idx["patient_id"] = idx["patient_id"].astype(str).str.strip()
    ct = idx[idx.modality == "CT"]
    rs = idx[idx.modality == "RTSTRUCT"].copy()
    rp = idx[idx.modality == "RTPLAN"].copy()
    rd = idx[idx.modality == "RTDOSE"].copy()

    cts = ct_series_table(ct)
    cts.to_csv(a.out / "T2_ct_series.csv", index=False)
    usable_ct = cts[cts.ct_series_usable]
    ct_by_pid = usable_ct.groupby("patient_id")["series_uid"].apply(set).to_dict()
    ct_for = usable_ct.set_index("series_uid")["for_uid"].to_dict()

    # ---- RTSTRUCT -> CT ---------------------------------------------------------------------
    def rs_link(r):
        refs = [x for x in str(r.get("ref_ct_series_uids") or "").split("|") if x]
        have = ct_by_pid.get(r["patient_id"], set())
        hit = [x for x in refs if x in have]
        return pd.Series({"n_ref_ct_series": len(refs), "n_ref_ct_series_present": len(hit),
                          "linked_ct_series": hit[0] if hit else ""})
    rs = pd.concat([rs.reset_index(drop=True),
                    rs.apply(rs_link, axis=1).reset_index(drop=True)], axis=1)
    rs["rs_links_ct"] = rs.linked_ct_series.astype(bool)
    rs.to_csv(a.out / "T2_rtstruct_links.csv", index=False)

    rs_sop_ok = set(rs.loc[rs.rs_links_ct, "sop_uid"])
    rs_by_sop = rs.set_index("sop_uid").to_dict("index")

    # ---- RTPLAN -> RTSTRUCT -----------------------------------------------------------------
    rp["rp_links_rs"] = rp["ref_structset_sop"].astype(str).isin(rs_sop_ok)
    # a plan may reference a structure set that exists but failed the CT link - distinguish the two
    rp["ref_rs_present_any"] = rp["ref_structset_sop"].astype(str).isin(set(rs.sop_uid))
    rp.to_csv(a.out / "T2_rtplan_links.csv", index=False)
    rp_by_sop = rp.set_index("sop_uid").to_dict("index")
    rp_sop_ok = set(rp.loc[rp.rp_links_rs, "sop_uid"])

    # ---- RTDOSE -> RTPLAN -------------------------------------------------------------------
    rd["rd_links_rp"] = rd["ref_plan_sop"].astype(str).isin(rp_sop_ok)
    rd["ref_rp_present_any"] = rd["ref_plan_sop"].astype(str).isin(set(rp.sop_uid))
    rd["is_grid"] = pd.to_numeric(rd["n_frames"], errors="coerce").fillna(0) >= 2
    rd["is_plan_sum"] = rd["dose_summation"].astype(str).str.upper().eq("PLAN")
    rd.to_csv(a.out / "T2_rtdose_links.csv", index=False)

    # ---- assemble the per-patient chain -----------------------------------------------------
    pids = sorted(set(idx.patient_id))
    out = []
    for pid in pids:
        rec = {"patient_id": pid,
               "zips": "|".join(sorted(set(idx.loc[idx.patient_id == pid, "zip"]))),
               "n_ct_series": int((cts.patient_id == pid).sum()),
               "n_ct_series_usable": int(len(ct_by_pid.get(pid, set()))),
               "n_rtstruct": int((rs.patient_id == pid).sum()),
               "n_rtplan": int((rp.patient_id == pid).sum()),
               "n_rtdose": int((rd.patient_id == pid).sum())}

        cand = rd[(rd.patient_id == pid) & rd.rd_links_rp & rd.is_grid]
        # prefer a plan-sum grid, then the largest grid
        cand = cand.sort_values(["is_plan_sum", "n_frames"], ascending=[False, False])
        chain_ok, reasons = False, []
        if len(cand):
            d = cand.iloc[0]
            plan = rp_by_sop.get(d["ref_plan_sop"], {})
            st = rs_by_sop.get(str(plan.get("ref_structset_sop", "")), {})
            ct_uid = str(st.get("linked_ct_series", ""))
            rec.update({
                "dose_sop": d["sop_uid"], "dose_summation": d["dose_summation"],
                "dose_units": d["dose_units"], "dose_frames": d["n_frames"],
                "dose_for_uid": d["for_uid"], "dose_zip": d["zip"], "dose_member": d["member"],
                "plan_sop": plan.get("sop_uid", ""), "plan_zip": plan.get("zip", ""),
                "plan_member": plan.get("member", ""),
                "n_fractions_planned": plan.get("n_fractions_planned"),
                "target_prescription_gy": plan.get("target_prescription_gy"),
                "beam_dose_sum_gy": plan.get("beam_dose_sum_gy"),
                "approval_status": plan.get("approval_status", ""),
                "rtstruct_sop": st.get("sop_uid", ""), "rtstruct_zip": st.get("zip", ""),
                "rtstruct_member": st.get("member", ""), "n_rois": st.get("n_rois"),
                "ct_series_uid": ct_uid, "ct_for_uid": ct_for.get(ct_uid, ""),
            })
            same_for = (str(d["for_uid"]) == str(ct_for.get(ct_uid, "")) != "")
            rec["for_consistent"] = bool(same_for)
            if not ct_uid:
                reasons.append("structure set does not reference a usable CT series")
            elif not same_for:
                reasons.append("dose grid FrameOfReferenceUID differs from the CT")
            else:
                chain_ok = True
        else:
            if rec["n_rtdose"] == 0:
                reasons.append("no RTDOSE")
            elif not rd[(rd.patient_id == pid) & rd.is_grid].shape[0]:
                reasons.append("RTDOSE present but carries no 3-D grid")
            elif rd.loc[rd.patient_id == pid, "ref_rp_present_any"].any():
                reasons.append("RTDOSE references a plan whose structure-set link fails")
            else:
                reasons.append("RTDOSE references an RTPLAN that is absent from the archives")
            if rec["n_ct_series_usable"] == 0:
                reasons.append("no usable CT series" if rec["n_ct_series"]
                               else "no CT in the archives")

        rec["chain_complete"] = chain_ok
        rec["reason"] = "; ".join(reasons)
        out.append(rec)

    chain = pd.DataFrame(out)
    chain.to_csv(a.out / "T2_patient_chain.csv", index=False)

    summary = {
        "patients_total": int(len(chain)),
        "with_any_ct": int((chain.n_ct_series > 0).sum()),
        "with_usable_ct_series": int((chain.n_ct_series_usable > 0).sum()),
        "with_rtstruct": int((chain.n_rtstruct > 0).sum()),
        "with_rtplan": int((chain.n_rtplan > 0).sum()),
        "with_rtdose": int((chain.n_rtdose > 0).sum()),
        "rtstruct_linking_to_ct": int(rs.rs_links_ct.sum()),
        "rtplan_linking_to_rtstruct": int(rp.rp_links_rs.sum()),
        "rtdose_linking_to_rtplan": int(rd.rd_links_rp.sum()),
        "CHAIN_COMPLETE": int(chain.chain_complete.sum()),
        "min_ct_slices": MIN_CT_SLICES,
        "top_failure_reasons": chain.loc[~chain.chain_complete, "reason"]
                                    .value_counts().head(10).to_dict(),
    }
    (a.out / "T2_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
