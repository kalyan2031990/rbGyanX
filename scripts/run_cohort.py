"""
One-command cohort runner launcher (Phase 5) — PowerShell-friendly.

Adds the engine to sys.path (so no editable install is required) and delegates to
``rbgyanx_engine.cohort_runner.main``. Run one cohort, resumable and pseudonymised:

    python scripts/run_cohort.py --input-root <DICOM_or_DVHtxt> --cohort <NAME> `
        --output-root <ROOT> --validation ExternalValidation --input-kind dicom `
        --pseudonym-map-dir <OUTSIDE_THE_REPO>

Re-running resumes (skips completed patients). The pseudonym map MUST live outside the repository.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from rbgyanx_engine.cohort_runner import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
