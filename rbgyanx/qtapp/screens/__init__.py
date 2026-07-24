"""
Qt screens (v2 Phase 4).

Each screen is a self-contained ``QWidget`` that reads widgets and paints results. Policy comes
from :mod:`rbgyanx.services.ui_policy`; orchestration from :mod:`rbgyanx.services`. Screens
never compute science and never decide BASIC/ADVANCED locally.
"""

from __future__ import annotations

from rbgyanx.qtapp.screens.workflow import STEPS, WorkflowScreen

__all__ = ["WorkflowScreen", "STEPS"]
