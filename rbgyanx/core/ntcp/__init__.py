"""
rbgyanx.core.ntcp - Normal Tissue Complication Probability (NTCP) Models

This module provides pure computational functions for NTCP calculations.

Layer 1 (Core) Responsibilities:
- Pure NTCP model calculations (LKB Log-Logistic, LKB Probit, RS Poisson)
- No UI dependencies (no tkinter, PyQt, matplotlib.pyplot)
- No file I/O beyond data structures
- No orchestration or governance logic

Allowed Dependencies:
- numpy, pandas, scipy (for mathematical operations)
- Standard library only

Forbidden Dependencies:
- UI frameworks (tkinter, PyQt, matplotlib.pyplot)
- File dialogs or subprocess calls
- Orchestration logic (belongs in logic layer)
"""

from rbgyanx.core.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from rbgyanx.core.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from rbgyanx.core.ntcp.rs_poisson import calculate_ntcp_rs_poisson

__all__ = [
    'calculate_ntcp_lkb_loglogit',
    'calculate_ntcp_lkb_probit',
    'calculate_ntcp_rs_poisson',
]

