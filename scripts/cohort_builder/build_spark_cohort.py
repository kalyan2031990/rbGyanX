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

OUTPUT = ROOT / "02_Run_Outputs" / "SPARK"
OUTPUT.mkdir(parents=True, exist_ok=True)


# ==========================================================
# Discover AE files
# ==========================================================

ae_files = []

for f in SPARK.rglob("*.csv"):

    name = f.name.lower().replace(" ", "")

    if "adverseevents" in name:
        ae_files.append(f)

ae_files = sorted(ae_files)

print("=" * 70)
print("SPARK CLINICAL COHORT BUILDER")
print("=" * 70)
print()

print(f"Found {len(ae_files)} adverse-event files\n")


# ==========================================================
# Parse centres
# ==========================================================

cohort_frames = []

for f in ae_files:

    # ----------------------------
    # robust centre detection
    # ----------------------------

    centre = None

    for p in f.parts:

        if p.startswith("Center"):

            centre = p

            break

    if centre is None:
        raise RuntimeError(f"Cannot determine centre for\n{f}")

    print("=" * 60)
    print(centre)
    print("=" * 60)

    # ----------------------------
    # Read REDCap export
    # ----------------------------

    df = pd.read_csv(f, header=27)

    df.columns = df.columns.str.strip()

    # ----------------------------
    # Toxicity columns
    # ----------------------------

    gu_cols = [
        c
        for c in df.columns
        if c.startswith("UrinaryAeGrade")
        or c.startswith("CystitisAeGrade")
    ]

    gi_cols = [
        c
        for c in df.columns
        if c.startswith("RectalAeGrade")
        or c.startswith("ProctitisAeGrade")
        or c.startswith("DiarrhoeaAeGrade")
    ]

    for c in gu_cols + gi_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # ----------------------------
    # Maximum toxicity
    # ----------------------------

    df["GU_max_grade"] = df[gu_cols].max(axis=1)

    df["GI_max_grade"] = df[gi_cols].max(axis=1)

    df["GU_event"] = (df["GU_max_grade"] >= 2).astype(int)

    df["GI_event"] = (df["GI_max_grade"] >= 2).astype(int)

    # ----------------------------
    # Build output dataframe
    # ----------------------------

    out = df[
        [
            "Patient No.",
            "GU_max_grade",
            "GI_max_grade",
            "GU_event",
            "GI_event",
        ]
    ].copy()

    out.rename(
        columns={
            "Patient No.": "Patient_No",
        },
        inplace=True,
    )

    # convert IDs to Patient01 format if necessary
    out["Patient_No"] = (
        pd.to_numeric(out["Patient_No"], errors="coerce")
        .fillna(0)
        .astype(int)
        .map(lambda x: f"Patient{x:02d}")
    )

    out["centre"] = centre

    out = out[
        [
            "centre",
            "Patient_No",
            "GU_max_grade",
            "GI_max_grade",
            "GU_event",
            "GI_event",
        ]
    ]

    cohort_frames.append(out)

    print(f"Patients : {len(out)}")
    print(f"GU events: {int(out.GU_event.sum())}")
    print(f"GI events: {int(out.GI_event.sum())}")
    print()

# ==========================================================
# Merge
# ==========================================================

cohort = pd.concat(
    cohort_frames,
    ignore_index=True,
)

outfile = OUTPUT / "spark_clinical_endpoints.csv"

cohort.to_csv(outfile, index=False)

print("=" * 70)
print("FINAL COHORT")
print("=" * 70)

print()

print(f"Patients : {len(cohort)}")
print(f"GU events: {int(cohort.GU_event.sum())}")
print(f"GI events: {int(cohort.GI_event.sum())}")

print()

print(cohort.head())

print()

print("Saved to:")
print(outfile)