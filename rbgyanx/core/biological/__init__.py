"""
Module: rbgyanx/core/biological
Layer: 1 (Core - Deterministic Analytical)
Purpose: Biological dose transformations (BED, EQD2, FDVH)

Allowed Dependencies:
- numpy, scipy, pandas
- Standard library

Forbidden Dependencies:
- UI frameworks (tkinter, PyQt, matplotlib.pyplot)
- AI/ML inference engines
- Mode controllers
- File I/O beyond data structures

Assumptions:
- All transformations assume photon therapy unless stated
- Parameters must be pre-validated by caller
- No applicability checking at this layer
"""

from rbgyanx.core.biological.transforms import FractionationAwareDVH

__all__ = ['FractionationAwareDVH']

