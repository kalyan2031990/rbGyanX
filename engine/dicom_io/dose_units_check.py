"""
Dose units / scaling sanity checks (Phase 2.5) — where silent errors live.

Delegates the actual DVH dose computation to dicompylercore (which applies DoseGridScaling and DoseUnits),
and adds explicit, machine-readable guards around the things that silently corrupt results: missing
DoseGridScaling, cGy-vs-Gy confusion, unexpected DoseSummationType, and grid-vs-DVH mean-dose disagreement.

None of these change any radiobiological number; they only emit reason codes for the QA log.
"""

from __future__ import annotations

import math

# A dose grid whose scaled maximum exceeds this (Gy) is almost certainly mislabelled cGy.
_IMPLAUSIBLE_MAX_GY = 200.0


def _s(ds, tag: str, default: str = "") -> str:
    return str(getattr(ds, tag, default) or default).strip()


def check_dose_units(rt_dose_ds) -> dict:
    """Return {'reason_codes': [...], 'dose_units': str, 'summation': str, 'grid_scaling': float|None,
    'scaled_max_gy': float|None}. Never raises."""
    codes: list[str] = []
    units = _s(rt_dose_ds, "DoseUnits").upper()
    summation = _s(rt_dose_ds, "DoseSummationType").upper()
    scaling = getattr(rt_dose_ds, "DoseGridScaling", None)
    scaled_max: float | None = None

    if units and units != "GY":
        codes.append("DOSE_UNITS_NOT_GY")  # e.g. RELATIVE — DVH would be meaningless
    if scaling is None:
        codes.append("MISSING_DOSE_GRID_SCALING")
    else:
        try:
            arr = rt_dose_ds.pixel_array
            scaled_max = float(arr.max()) * float(scaling)
            if scaled_max > _IMPLAUSIBLE_MAX_GY:
                codes.append("CGY_SUSPECTED")  # scaled max implausibly high for Gy
        except Exception:
            codes.append("DOSE_PIXELS_UNREADABLE")

    if summation and summation not in ("PLAN", "BEAM", "FRACTION", "MULTI_PLAN"):
        codes.append("UNEXPECTED_DOSE_SUMMATION")

    return {
        "reason_codes": codes,
        "dose_units": units,
        "summation": summation,
        "grid_scaling": float(scaling) if scaling is not None else None,
        "scaled_max_gy": scaled_max,
    }


def mean_dose_agreement(mean_a_gy: float, mean_b_gy: float, rel_tol: float = 0.05) -> dict:
    """2.5 assertion: two independent estimates of a structure's mean dose (e.g. TPS-embedded DVH vs
    grid-recomputed DVH) must agree within ``rel_tol``. Returns {'ok', 'rel_diff', 'reason'}.

    NaN inputs are treated as 'not comparable' (ok=True, reason=NONE) rather than a failure — a missing
    estimate is not a disagreement."""
    a, b = float(mean_a_gy), float(mean_b_gy)
    if math.isnan(a) or math.isnan(b):
        return {"ok": True, "rel_diff": math.nan, "reason": "NONE"}
    denom = max(abs(a), abs(b), 1e-6)
    rel = abs(a - b) / denom
    if rel > rel_tol:
        return {"ok": False, "rel_diff": rel, "reason": "DOSE_DVH_MISMATCH"}
    return {"ok": True, "rel_diff": rel, "reason": "NONE"}
