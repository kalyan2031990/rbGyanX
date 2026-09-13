"""NumPy 2.x compatibility helpers."""

from __future__ import annotations

import numpy as np


def trapz(y, x=None):
    """Trapezoidal integration (NumPy 1.x trapz / 2.x trapezoid)."""
    if hasattr(np, "trapezoid"):
        return np.trapezoid(y, x)
    if hasattr(np, "trapz"):
        return np.trapz(y, x)
    try:
        from scipy.integrate import trapezoid

        return trapezoid(y, x)
    except ImportError as exc:
        raise RuntimeError("No trapezoid implementation available") from exc
