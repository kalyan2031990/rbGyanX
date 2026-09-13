"""
DVH integrity validation — applied at every ingest path.

A cumulative DVH is a physical object: volume(>= dose) is finite, non-negative, and
monotonically non-increasing in dose. This module enforces that once, so no reader silently
accepts an inverted or scrambled curve. It **never repairs** a physically impossible curve — it
sorts deterministically by dose and then raises a clear, actionable error naming the structure
and the offending rows (mirroring the project's NaN-not-zero / SITE_UNKNOWN "fail loudly"
precedent).

Used by the TPS text reader today; importable by any future reader.
"""

from __future__ import annotations

import numpy as np

__all__ = ["DVHIntegrityError", "validate_cumulative_dvh"]


class DVHIntegrityError(ValueError):
    """A DVH curve is not a physically valid cumulative histogram."""


def validate_cumulative_dvh(
    dose: np.ndarray,
    volume: np.ndarray,
    *,
    structure: str,
    tol: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray]:
    """Validate a *cumulative* DVH and return it sorted by ascending dose.

    Checks, in order:
      * dose and volume are finite and non-negative;
      * dose has no duplicate values (ambiguous cumulative volume);
      * after a deterministic sort by dose, cumulative volume is monotonically non-increasing
        within ``tol`` — i.e. it never *rises* with dose (the inverted case).

    Raises :class:`DVHIntegrityError` naming ``structure`` and the first offending rows.
    Returns the (dose, volume) arrays sorted by ascending dose so downstream code sees a
    canonical curve. Does not convert differential<->cumulative — that decision stays with the
    caller, which must pass a cumulative curve here.
    """
    dose = np.asarray(dose, dtype=float)
    volume = np.asarray(volume, dtype=float)
    if dose.shape != volume.shape:
        raise DVHIntegrityError(
            f"{structure}: dose and volume differ in length ({dose.size} vs {volume.size})"
        )
    if dose.size == 0:
        raise DVHIntegrityError(f"{structure}: empty DVH (no dose/volume rows)")

    if not np.all(np.isfinite(dose)) or not np.all(np.isfinite(volume)):
        raise DVHIntegrityError(f"{structure}: DVH contains non-finite dose or volume values")
    if np.any(dose < -tol) or np.any(volume < -tol):
        raise DVHIntegrityError(f"{structure}: DVH has negative dose or volume values")

    order = np.argsort(dose, kind="stable")
    d = dose[order]
    v = volume[order]

    dup = np.where(np.diff(d) <= tol)[0]
    if dup.size and dose.size > 1:
        i = int(dup[0])
        raise DVHIntegrityError(
            f"{structure}: duplicate/*non-increasing* dose at rows {i} and {i + 1} "
            f"(dose {d[i]:.4g} == {d[i + 1]:.4g}); a cumulative DVH needs distinct doses"
        )

    rises = np.where(np.diff(v) > tol)[0]
    if rises.size:
        i = int(rises[0])
        raise DVHIntegrityError(
            f"{structure}: cumulative volume RISES with dose — not a valid DVH. "
            f"At dose {d[i]:.4g}->{d[i + 1]:.4g} Gy the volume goes {v[i]:.4g}->{v[i + 1]:.4g} cm^3. "
            "The curve is inverted or the columns are swapped; this cannot be silently repaired."
        )

    return d, v
