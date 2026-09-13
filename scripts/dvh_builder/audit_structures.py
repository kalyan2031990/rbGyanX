import os
from collections import Counter
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

counter = Counter()

patients = 0

for rs in DATA.rglob("RS.dcm"):

    patients += 1

    ds = pydicom.dcmread(rs, force=True)

    print("=" * 70)
    print(rs.parent)
    print("=" * 70)

    if not hasattr(ds, "StructureSetROISequence"):
        continue

    for roi in ds.StructureSetROISequence:

        name = roi.ROIName.strip()

        counter[name] += 1

        print(name)

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)

for name, n in counter.most_common():

    print(f"{name:40s} {n}")