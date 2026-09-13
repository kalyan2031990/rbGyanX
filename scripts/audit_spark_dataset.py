"""
SPARK Dataset Audit
rbGyanX Validation Pipeline

Step 1:
    - Discover centres
    - Count files
    - Verify RT objects
"""

import os
from pathlib import Path


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

ROOT = Path(_WORKSPACE / "01_Input_Data" / "SPARK_data")

print("=" * 60)
print("SPARK DATASET AUDIT")
print("=" * 60)

print(f"\nDataset root:\n{ROOT}")

centres = sorted([p for p in ROOT.iterdir() if p.is_dir()])

print(f"\nCentres found: {len(centres)}\n")

for c in centres:
    print(" -", c.name)
print("\n" + "=" * 60)
print("FILE INVENTORY")
print("=" * 60)

from collections import Counter

for centre in centres:

    counter = Counter()

    for f in centre.rglob("*"):
        if f.is_file():
            counter[f.suffix.lower()] += 1

    print(f"\n{centre.name}")

    for ext, n in sorted(counter.items(), key=lambda x: x[1], reverse=True):
        ext = ext if ext else "[no extension]"
        print(f"   {ext:<15} {n:6d}")
print("\n" + "=" * 60)
print("RT OBJECT INVENTORY")
print("=" * 60)

for centre in centres:

    rs = list(centre.rglob("RS*.dcm"))
    rp = list(centre.rglob("RP*.dcm"))
    rd = list(centre.rglob("RD*.dcm"))

    print(f"\n{centre.name}")
    print(f"   RTSTRUCT : {len(rs)}")
    print(f"   RTPLAN   : {len(rp)}")
    print(f"   RTDOSE   : {len(rd)}")
print("\n" + "=" * 60)
print("PATIENT DIRECTORY STRUCTURE")
print("=" * 60)

for centre in centres:

    print(f"\n{centre.name}")

    rs_files = sorted(centre.rglob("RS*.dcm"))

    for rs in rs_files[:3]:   # first three patients only
        print()
        print("Patient folder:")
        print(rs.parent)
print("\n" + "=" * 60)
print("PATIENT DISCOVERY")
print("=" * 60)

patients = []

for rs in ROOT.rglob("RS*.dcm"):

    patient_dir = rs.parent

    rp = list(patient_dir.glob("RP*.dcm"))
    rd = list(patient_dir.glob("RD*.dcm"))

    patients.append(
        {
            "centre": patient_dir.parts[-3],
            "patient": patient_dir.name,
            "folder": str(patient_dir),
            "rtstruct": rs.name,
            "rtplan": rp[0].name if rp else "",
            "rtdose": rd[0].name if rd else "",
        }
    )

print(f"\nPatients discovered : {len(patients)}")

print("\nFirst 10 patients:\n")

for p in patients[:10]:
    print(
        f"{p['centre']:22} "
        f"{p['patient']:10} "
        f"{p['rtstruct']:18} "
        f"{p['rtplan']:18} "
        f"{p['rtdose']}"
    )
print("\n" + "=" * 60)
print("CLINICAL FILES")
print("=" * 60)

clinical = []

for ext in ("*.csv", "*.xls", "*.xlsx"):

    clinical.extend(ROOT.rglob(ext))

clinical = sorted(clinical)

print(f"\nClinical spreadsheets found : {len(clinical)}\n")

for f in clinical:
    print(f.relative_to(ROOT))
