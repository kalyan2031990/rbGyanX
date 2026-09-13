"""EPV check and feature selection gate for logistic regression."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

EPV_MINIMUM = 10.0


@dataclass
class EPVResult:
    epv: float
    n_events: int
    n_features: int
    threshold: float
    passes: bool
    warning_message: str = ""


def compute_epv(
    y: np.ndarray | pd.Series,
    n_features: int,
    threshold: float = EPV_MINIMUM,
) -> EPVResult:
    """
    Compute Events Per Variable for logistic regression.

    Events = minority class = recurrences = sum(y == 0).
    """
    y_arr = np.asarray(y, dtype=int)
    n_events = int(np.sum(y_arr == 0))
    if n_features <= 0:
        raise ValueError("n_features must be > 0")
    epv = n_events / n_features
    passes = epv >= threshold
    msg = "" if passes else (
        f"EPV={epv:.1f} < {threshold} (n_recurrences={n_events}, "
        f"n_features={n_features}). Reduce features or collect more recurrence events."
    )
    return EPVResult(
        epv=epv,
        n_events=n_events,
        n_features=n_features,
        threshold=threshold,
        passes=passes,
        warning_message=msg,
    )


def select_features_by_epv(
    feature_names: list[str],
    y: np.ndarray | pd.Series,
    priority_order: list[str] | None = None,
    threshold: float = EPV_MINIMUM,
) -> tuple[list[str], EPVResult]:
    """
    Automatically reduce feature set until EPV >= threshold.

    Features are dropped from the END of priority_order (lowest priority first).
    """
    y_arr = np.asarray(y, dtype=int)
    n_events = int(np.sum(y_arr == 0))
    if n_events < threshold:
        raise RuntimeError(
            f"Only {n_events} recurrence events — even 1 feature gives EPV={n_events:.1f} "
            f"< {threshold}. Cannot fit logistic regression safely."
        )

    order = list(priority_order) if priority_order else list(feature_names)
    max_features = int(n_events // threshold)
    max_features = max(max_features, 1)

    selected = [f for f in order if f in feature_names][:max_features]
    epv_result = compute_epv(y_arr, len(selected), threshold)
    return selected, epv_result
