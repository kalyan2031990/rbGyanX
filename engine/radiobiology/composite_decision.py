"""Therapeutic index, therapeutic window, UTCP (P+), and ΔNTCP utilities."""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

import numpy as np


def therapeutic_index(td50_gy: float, tcd50_gy: float) -> float:
    """TI = TD50 / TCD50 (OAR tolerance / tumour control dose)."""
    if not math.isfinite(td50_gy) or not math.isfinite(tcd50_gy) or tcd50_gy <= 0:
        return float("nan")
    return float(td50_gy / tcd50_gy)


def therapeutic_window(
    doses_gy: Sequence[float],
    utcp_values: Sequence[float],
    untcp_values: Sequence[float],
    tau_t: float = 0.5,
    tau_n: float = 0.1,
) -> dict:
    """
    Doses where uTCP(D) ≥ τ_T and uNTCP(D) ≤ τ_N.

    Inputs are parallel dose–response curves (e.g. from MC bands).
    """
    d = np.asarray(doses_gy, dtype=float)
    tcp = np.asarray(utcp_values, dtype=float)
    ntcp = np.asarray(untcp_values, dtype=float)
    mask = (
        np.isfinite(d)
        & np.isfinite(tcp)
        & np.isfinite(ntcp)
        & (tcp >= tau_t)
        & (ntcp <= tau_n)
    )
    window_doses = d[mask].tolist()
    return {
        "doses_gy": window_doses,
        "n_points": int(np.sum(mask)),
        "tau_tcp": tau_t,
        "tau_ntcp": tau_n,
        "empty": len(window_doses) == 0,
    }


def compute_utcp_p_plus(
    utcp: float,
    untcp_by_oar: Mapping[str, float] | Iterable[float],
) -> float:
    """P+ = uTCP × Π_k (1 − uNTCP_k)."""
    if not math.isfinite(utcp):
        return float("nan")
    survival = 1.0
    if isinstance(untcp_by_oar, Mapping):
        values = untcp_by_oar.values()
    else:
        values = untcp_by_oar
    for p in values:
        if math.isfinite(p):
            survival *= 1.0 - float(np.clip(p, 0.0, 1.0))
    return float(np.clip(utcp * survival, 0.0, 1.0))


def delta_ntcp(
    ntcp_a: Mapping[str, float],
    ntcp_b: Mapping[str, float],
    threshold: float = 0.05,
) -> dict[str, dict]:
    """
    Per-OAR NTCP change between two plans; flag when degradation exceeds threshold.

    Degradation = increase in NTCP (plan_b − plan_a).
    """
    rows: dict[str, dict] = {}
    for oar in sorted(set(ntcp_a) | set(ntcp_b)):
        a = float(ntcp_a.get(oar, math.nan))
        b = float(ntcp_b.get(oar, math.nan))
        delta = b - a if math.isfinite(a) and math.isfinite(b) else math.nan
        flagged = math.isfinite(delta) and delta > threshold
        rows[oar] = {
            "ntcp_a": a,
            "ntcp_b": b,
            "delta": delta,
            "degradation_flag": flagged,
        }
    return {
        "per_oar": rows,
        "threshold": threshold,
        "any_degradation": any(r["degradation_flag"] for r in rows.values()),
    }
