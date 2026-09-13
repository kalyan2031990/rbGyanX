"""
rbgyanx.core.dvh - Dose-Volume Histogram (DVH) Processing

This module provides pure computational functions for DVH transformations.

Layer 1 (Core) Responsibilities:
- Pure DVH transformation functions (cumulative ↔ differential conversions)
- No UI dependencies (no tkinter, PyQt, matplotlib.pyplot)
- No file I/O beyond data structures
- No orchestration or governance logic

Allowed Dependencies:
- numpy, pandas (for data structures and mathematical operations)
- Standard library only

Forbidden Dependencies:
- UI frameworks (tkinter, PyQt, matplotlib.pyplot)
- File dialogs or subprocess calls
- File I/O (except data structure handling)
- Orchestration logic (belongs in logic layer)
"""

from rbgyanx.core.dvh.conversions import (
    convert_to_cumulative,
    convert_to_differential,
)

__all__ = [
    'convert_to_cumulative',
    'convert_to_differential',
]

