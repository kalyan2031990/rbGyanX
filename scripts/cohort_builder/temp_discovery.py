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

ROOT = Path(
    _WORKSPACE / "01_Input_Data" / "SPARK_data"
)

print("=" * 70)
print("CENTER 1 OUTCOME FILES")
print("=" * 70)

centre = ROOT / "Center 1"

for f in sorted(centre.rglob("*.csv")):
    print(f.relative_to(centre))