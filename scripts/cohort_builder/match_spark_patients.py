import os
from pathlib import Path
import pandas as pd

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

# ==========================================================
# Workspace
# ==========================================================

ROOT = Path(
    _WORKSPACE
)

SPARK = ROOT / "01_Input_Data" / "SPARK_data"

# ==========================================================
# Helper
# ==========================================================

def norm_centre(x):

    x = str(x).strip()

    mapping = {
        "Center 1": "Center1",
        "Center 4": "Center4",
        "Center5": "Center5",
        "Center2_AllOtherData": "Center2",
        "Center3_AllOtherData": "Center3",
    }

    return mapping.get(x, x.replace(" ", ""))


# ==========================================================
# Clinical
# ==========================================================

clinical = pd.read_csv(
    ROOT
    / "02_Run_Outputs"
    / "SPARK"
    / "spark_clinical_endpoints.csv"
)

clinical["centre"] = clinical["centre"].apply(norm_centre)

clinical["Patient_No"] = (
    clinical["Patient_No"]
    .astype(str)
    .str.strip()
)

# ==========================================================
# RT patients
# ==========================================================

rt = []

for rs in SPARK.rglob("RS.dcm"):

    patient = rs.parent.name

    centre = None

    for p in rs.parts:

        if p.startswith("Center"):

            centre = norm_centre(p)

            break

    if centre is None:
        continue

    # ignore plan folders

    if not patient.lower().startswith("patient"):
        continue

    rt.append(
        {
            "centre": centre,
            "Patient_No": patient,
            "RS": str(rs),
        }
    )

rt = pd.DataFrame(rt)

rt["Patient_No"] = (
    rt["Patient_No"]
    .astype(str)
    .str.strip()
)

# ==========================================================
# Summary
# ==========================================================

print("\nRT patients by centre\n")
print(rt.groupby("centre").size())

print()

print("Clinical patients by centre\n")
print(clinical.groupby("centre").size())

# ==========================================================
# Merge
# ==========================================================

merged = rt.merge(
    clinical,
    on=["centre", "Patient_No"],
    how="outer",
    indicator=True,
)

print("\n")
print("=" * 70)
print("MERGE SUMMARY")
print("=" * 70)

print(merged["_merge"].value_counts())

print()

print("ONLY RT")
print(
    merged.loc[
        merged["_merge"] == "left_only",
        ["centre", "Patient_No"],
    ]
)

print()

print("ONLY CLINICAL")
print(
    merged.loc[
        merged["_merge"] == "right_only",
        ["centre", "Patient_No"],
    ]
)

outfile = (
    ROOT
    / "02_Run_Outputs"
    / "SPARK"
    / "spark_patient_matching.csv"
)

merged.to_csv(outfile, index=False)

print()
print("Saved:")
print(outfile)