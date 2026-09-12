"""
Build the de-identified parotid NTCP cohort table (B1).

Reads the PHI-stripped DVH copies + clinical xlsx, computes DVH features and the tool's
classical NTCP via rbGyanX, and writes a pseudonymised derived table (no PHI):

  derived/parotid_cohort.csv

Columns: pseudonym, Parotid_Dmean_gy, Parotid_gEUD_gy, DVH-shape dosiomics,
classical NTCP (log-logistic + relative-seriality, tool's HN parotid params),
covariates (age/sex/tobacco), endpoint xerostomia_grade2plus.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from dicom_io.dvh_shape_features import compute_dvh_shape_features
from dicom_io.txt_dvh_reader import parse_dvh_text_file
from radiobiology import dvh_object_to_dataframe
from radiobiology.geud_tcp import compute_geud
from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson


def _default_workspace() -> Path:
    """First rbGyanX_Manuscript_Workspace found walking up from this file."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "rbGyanX_Manuscript_Workspace"
        if candidate.is_dir():
            return candidate
    return Path("rbGyanX_Manuscript_Workspace")


# Workspace root. Was an absolute path into the author's home directory; de-localised when this
# script was committed retrospectively (FINAL_V3.2 consolidation). Set RBGYANX_WORKSPACE to
# point elsewhere. No computation, constant, parameter or threshold was changed.
_WORKSPACE = Path(os.environ.get("RBGYANX_WORKSPACE") or _default_workspace())

DEID = Path(_WORKSPACE / "01_Input_Data" / "PAROTID" / "parotid_deid")
MAP = Path(_WORKSPACE / "01_Input_Data" / "PAROTID" / "parotid_pseudonym_map.csv")
CLINICAL = Path(_WORKSPACE / "01_Input_Data" / "PAROTID" / "clinical" / "py_ntcpx_clinical_v1.1.0.xlsx")
OUT = Path(_WORKSPACE / "02_Run_Outputs" / "PAROTID" / "parotid_cohort.csv")

# Tool's shipped HN parotid NTCP params (site_params_ntcp_default.yaml).
GEUD_A = 3.0
LL_TD50, LL_GAMMA50 = 28.4, 0.6
RS_D50, RS_GAMMA, RS_S = 28.4, 1.0, 0.25


def main() -> None:
    pmap = pd.read_csv(MAP).set_index("coded_id")
    clin = pd.read_excel(CLINICAL)
    clin["patient_id"] = clin["patient_id"].astype(str)

    rows = []
    for coded, r in pmap.iterrows():
        coded = str(coded)
        dvh_path = DEID / str(r["dvh_file"])
        res = parse_dvh_text_file(dvh_path)
        diff = dvh_object_to_dataframe(res.dvh_object)
        geud = compute_geud(diff, GEUD_A) if diff is not None else float("nan")
        shape = compute_dvh_shape_features(diff, "Parotid") if diff is not None else {}
        ntcp_ll = calculate_ntcp_lkb_loglogit(geud, LL_TD50, LL_GAMMA50)
        ntcp_rs = calculate_ntcp_rs_poisson(diff, RS_D50, RS_GAMMA, RS_S) if diff is not None else float("nan")
        rows.append(
            {
                "pseudonym": r["pseudonym"],
                "coded_id": coded,
                "Parotid_Dmean_gy": res.dmean_gy,
                "Parotid_gEUD_gy": geud,
                "Parotid_dose_skewness": shape.get("dose_skewness", float("nan")),
                "Parotid_dose_kurtosis": shape.get("dose_kurtosis", float("nan")),
                "Parotid_dose_std_gy": shape.get("dose_std_gy", float("nan")),
                "NTCP_LL": ntcp_ll,
                "NTCP_RS": ntcp_rs,
            }
        )
    feat = pd.DataFrame(rows)

    keep = ["patient_id", "age", "sex", "tobacco_exposure", "xerostomia_grade2plus"]
    merged = feat.merge(clin[keep], left_on="coded_id", right_on="patient_id", how="left")
    merged["sex_M"] = (merged["sex"].astype(str).str.upper() == "M").astype(int)
    assert merged["xerostomia_grade2plus"].notna().all(), "unlinked patients!"

    # De-identified output: drop coded_id and raw patient_id (keep pseudonym only).
    out = merged.drop(columns=["coded_id", "patient_id", "sex"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    n, ev = len(out), int(out["xerostomia_grade2plus"].sum())
    print(f"parotid cohort -> {OUT}: n={n}, events={ev}")
    print("NTCP_LL range:", round(out.NTCP_LL.min(), 3), "-", round(out.NTCP_LL.max(), 3))
    print("Dmean Gy range:", round(out.Parotid_Dmean_gy.min(), 1), "-", round(out.Parotid_Dmean_gy.max(), 1))


if __name__ == "__main__":
    main()

