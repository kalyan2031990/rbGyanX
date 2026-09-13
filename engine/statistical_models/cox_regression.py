"""Cox proportional hazards regression for time-to-event analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

try:
    from lifelines import CoxPHFitter  # noqa: F401
    _LIFELINES_AVAILABLE = True
except ImportError:
    _LIFELINES_AVAILABLE = False


@dataclass
class CoxResult:
    """Results from Cox proportional hazards model."""

    model: Any
    feature_names: list[str]
    hazard_ratios: dict[str, float]
    coef_pvalues: dict[str, float]
    harrell_c: float
    harrell_c_ci_lower: float
    harrell_c_ci_upper: float
    n_events: int
    n_samples: int
    log_likelihood: float
    warnings: list[str] = field(default_factory=list)


def fit_cox_tcp(
    df: pd.DataFrame,
    feature_cols: list[str],
    duration_col: str = "FollowUp_months",
    event_col: str = "Recurrence",
    penalizer: float = 0.1,
) -> CoxResult:
    """
    Fit L2-penalised Cox proportional hazards model.

    Recurrence=1 marks the event; Recurrence=0 marks censoring.
    """
    if not _LIFELINES_AVAILABLE:
        raise ImportError(
            "lifelines>=0.27 required for Cox regression. "
            "Install with: pip install lifelines"
        )
    from lifelines import CoxPHFitter
    from lifelines.utils import concordance_index

    warns: list[str] = []
    df_fit = df[feature_cols + [duration_col, event_col]].copy().dropna()
    n_samples = len(df_fit)
    n_events = int(df_fit[event_col].sum())

    if n_events < 5:
        warns.append(f"Only {n_events} events — Cox model may be unstable.")

    cph = CoxPHFitter(penalizer=penalizer)
    cph.fit(df_fit, duration_col=duration_col, event_col=event_col, show_progress=False)

    summary = cph.summary
    hr = {
        f: float(summary.loc[f, "exp(coef)"])
        for f in feature_cols
        if f in summary.index
    }
    pvals = {
        f: float(summary.loc[f, "p"]) for f in feature_cols if f in summary.index
    }

    predicted_partial_hazard = cph.predict_partial_hazard(df_fit).values
    c_index = float(
        concordance_index(
            df_fit[duration_col], -predicted_partial_hazard, df_fit[event_col]
        )
    )

    rng = np.random.default_rng(42)
    boot_c = []
    for _ in range(200):
        idx = rng.integers(0, n_samples, size=n_samples)
        sub = df_fit.iloc[idx]
        ph = cph.predict_partial_hazard(sub).values
        if sub[event_col].sum() < 2:
            continue
        boot_c.append(concordance_index(sub[duration_col], -ph, sub[event_col]))
    c_lower = float(np.percentile(boot_c, 2.5)) if boot_c else math.nan
    c_upper = float(np.percentile(boot_c, 97.5)) if boot_c else math.nan

    return CoxResult(
        model=cph,
        feature_names=feature_cols,
        hazard_ratios=hr,
        coef_pvalues=pvals,
        harrell_c=c_index,
        harrell_c_ci_lower=c_lower,
        harrell_c_ci_upper=c_upper,
        n_events=n_events,
        n_samples=n_samples,
        log_likelihood=float(cph.log_likelihood_),
        warnings=warns,
    )
