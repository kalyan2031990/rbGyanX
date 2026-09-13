import os
from pathlib import Path

import pydicom


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

ROOT = Path(
    _WORKSPACE
)

DATA = ROOT / "01_Input_Data" / "SPARK_data"

patient = (
    DATA /
    "Center2_AllOtherData" /
    "Treatment plans" /
    "Patient01"
)

print("=" * 70)
print("PATIENT")
print("=" * 70)
print(patient)
print()

for f in sorted(patient.glob("*.dcm")):

    ds = pydicom.dcmread(
        f,
        stop_before_pixels=True,
        force=True,
    )

    print(f.name)

    print("  Modality :", getattr(ds, "Modality", ""))

    print("  SOPClass :", getattr(ds, "SOPClassUID", ""))

    print("  Series   :", getattr(ds, "SeriesDescription", ""))

    print("  Study    :", getattr(ds, "StudyDescription", ""))

    print()