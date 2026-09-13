"""
**The** benchmarking entry point (P2).

One documented function, `run_arm_benchmark`, dispatches to the two scientifically distinct
paths. They stay separate implementations on purpose (P1 · S5) — this module is a facade, not
a merge:

  ``kind="tcp"``   -> :mod:`validation.extval_benchmark`
                      classical tier = literature-fixed TCP on the target dose, reported as
                      P(event) = 1 - TCP. Feature tiers C1-C4.
  ``kind="ntcp"``  -> :mod:`validation.ntcp_benchmark`
                      classical tier = the engine's own NTCP model (LKB probit / LKB
                      log-logistic / relative seriality) on the OAR dose, direct polarity.
                      Tiers T1-T4.

Anything else (a logistic fitted to dose used as a "classical" tier, or the TCP predictor
applied to a toxicity endpoint) is a defect — see docs/AUDIT_REPORT.md A1/A5.

Examples
--------
Tumour-control arm::

    table, extras = run_arm_benchmark(
        df, kind="tcp", endpoint="locoregional", feature_set="dosiomics", seed=0,
    )

Toxicity arm::

    table, extras = run_arm_benchmark(
        df, kind="ntcp", endpoint="xerostomia_g2",
        model="lkb_probit", params={"TD50_gy": 39.9, "m": 0.40},
        dose_metric_col="Parotid_gEUD_gy", groups_col="centre",
    )
"""

from __future__ import annotations

from typing import Any, Literal

import pandas as pd

BenchmarkKind = Literal["tcp", "ntcp"]

__all__ = ["BenchmarkKind", "run_arm_benchmark"]


def run_arm_benchmark(
    df: pd.DataFrame,
    *,
    kind: BenchmarkKind,
    endpoint: str,
    **kwargs: Any,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run one validation arm.

    Parameters
    ----------
    df : cohort table, one row per patient (features + endpoint column).
    kind : ``"tcp"`` for tumour control, ``"ntcp"`` for a toxicity endpoint.
    endpoint : name of the binary (0/1) outcome column.
    **kwargs : forwarded to the selected path. ``ntcp`` requires ``model`` and ``params``.

    Returns
    -------
    (table, extras) — per-tier metrics and a provenance dict.
    """
    if kind == "tcp":
        from validation.extval_benchmark import run_benchmark

        return run_benchmark(df, endpoint=endpoint, **kwargs)

    if kind == "ntcp":
        from validation.ntcp_benchmark import run_ntcp_benchmark

        if "model" not in kwargs or "params" not in kwargs:
            raise ValueError(
                "the NTCP arm requires an engine model and its fixed parameters, e.g. "
                "model='lkb_probit', params={'TD50_gy': 39.9, 'm': 0.40}; "
                "a logistic fitted to dose is not a classical NTCP tier"
            )
        return run_ntcp_benchmark(df, endpoint=endpoint, **kwargs)

    raise ValueError(f"unknown benchmark kind {kind!r}; expected 'tcp' or 'ntcp'")
