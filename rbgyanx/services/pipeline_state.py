"""
Pipeline execution state — headless, UI-independent (v2 Phase 4 · Slice 1).

Extracted from ``rbgyanx_gui`` so workflow state lives with the orchestration layer rather
than the widget tree. Behaviour is unchanged; ``WorkflowState`` and ``PipelineExecutionState``
keep their original members and semantics (see the equivalence tests).
"""

from __future__ import annotations

from enum import Enum

__all__ = ["WorkflowState", "PipelineExecutionState"]


class WorkflowState(Enum):
    """Workflow state enumeration for pipeline synchronisation."""

    IDLE = 0
    PREPROCESSING = 1
    PREPROCESSING_COMPLETE = 2
    TCP_RUNNING = 3
    TCP_COMPLETE = 4
    NTCP_RUNNING = 5
    NTCP_COMPLETE = 6
    INTEGRATION_RUNNING = 7
    INTEGRATION_COMPLETE = 8
    ERROR = 99


class PipelineExecutionState:
    """Shared execution state: mode, per-step completion, and gating rules.

    Deliberately free of any widget/toolkit reference so the same object drives the Tkinter
    app, the Qt app, and headless runs.
    """

    def __init__(self) -> None:
        self.mode = None  # "TCP", "NTCP", "BOTH"
        self.step1_complete = False
        self.step2_complete = False
        self.tcp_step3_complete = False
        self.ntcp_step3_complete = False
        self.step4_complete = False
        self.step5_complete = False
        self.step6_complete = False
        self.tcp_enabled = False
        self.ntcp_enabled = False
        self.current_step = None

    def reset(self) -> None:
        """Reset all step-completion flags (mode and enables are preserved)."""
        self.step1_complete = False
        self.step2_complete = False
        self.tcp_step3_complete = False
        self.ntcp_step3_complete = False
        self.step4_complete = False
        self.step5_complete = False
        self.step6_complete = False
        self.current_step = None

    def can_run_step6(self) -> bool:
        """Step 6 (TCP/NTCP integration) needs both arms complete."""
        return self.tcp_step3_complete and self.ntcp_step3_complete
