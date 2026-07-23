"""
Headless service layer (v2 Phase 4 · Slice 1).

UI-independent orchestration and data handling extracted from ``rbgyanx_gui.py`` so the
desktop application — Tkinter today, Qt next — is a thin view over this package.

Nothing here imports a GUI toolkit, so the same code runs in the app, in a CLI, and in tests.
Scientific computation is *not* reimplemented here: these services call the validated engine,
so classical numerics stay byte-identical.
"""

from __future__ import annotations

from rbgyanx.services.dvh_service import (
    build_canonical_dvh,
    normalize_dvh,
    validate_dvh_integrity,
)
from rbgyanx.services.pipeline_state import PipelineExecutionState, WorkflowState
from rbgyanx.services.progress import (
    CallbackReporter,
    CollectingReporter,
    NullReporter,
    ProgressReporter,
)
from rbgyanx.services.run_request import (
    RunRequest,
    ValidationResult,
    validate_run_request,
)

__all__ = [
    "build_canonical_dvh",
    "normalize_dvh",
    "validate_dvh_integrity",
    "WorkflowState",
    "PipelineExecutionState",
    "ProgressReporter",
    "NullReporter",
    "CollectingReporter",
    "CallbackReporter",
    "RunRequest",
    "ValidationResult",
    "validate_run_request",
]
