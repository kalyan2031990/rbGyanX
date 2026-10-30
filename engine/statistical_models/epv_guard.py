"""EPV check and feature selection gate for logistic regression."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

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
    event_label: Any = None


def _event_count(y: np.ndarray | pd.Series, event_label: Any) -> tuple[np.ndarray, int]:
    """Count occurrences of ``event_label`` in ``y``, refusing anything not binary.

    Defect #36: the guard used to hard-code ``sum(y == 0)``. That is right only for the one
    coding convention this project happened to use (0 = recurrence); on a cohort labelled the
    other way round it silently counted the majority class and waved through a model fitted on
    a handful of events. The label is now named by the caller and never inferred.
    """
    y_arr = np.asarray(y)
    if y_arr.size == 0:
        raise ValueError("y is empty; EPV is undefined")

    finite = y_arr[~pd.isna(y_arr)] if y_arr.dtype.kind not in "US" else y_arr
    levels = pd.unique(np.asarray(finite).ravel())
    if len(levels) > 2:
        raise ValueError(
            f"y is not binary: {len(levels)} distinct values {sorted(map(str, levels))}. "
            "EPV is defined for a binary outcome only."
        )
    if not bool(np.any(y_arr == event_label)):
        raise ValueError(
            f"event_label={event_label!r} does not occur in y (values present: "
            f"{sorted(map(str, levels))}). Name the label that marks an event."
        )
    return y_arr, int(np.sum(y_arr == event_label))


def compute_epv(
    y: np.ndarray | pd.Series,
    n_features: int,
    *,
    event_label: Any,
    threshold: float = EPV_MINIMUM,
) -> EPVResult:
    """
    Compute Events Per Variable for logistic regression.

    ``event_label`` is the value in ``y`` that marks an event and is required: there is no
    default and nothing is inferred from class sizes (defect #36).
    """
    if n_features <= 0:
        raise ValueError("n_features must be > 0")
    _y, n_events = _event_count(y, event_label)
    epv = n_events / n_features
    passes = epv >= threshold
    msg = "" if passes else (
        f"EPV={epv:.3g} < {threshold} (n_events={n_events}, event_label={event_label!r}, "
        f"n_features={n_features}). Reduce features or collect more events."
    )
    return EPVResult(
        epv=epv,
        n_events=n_events,
        n_features=n_features,
        threshold=threshold,
        passes=passes,
        warning_message=msg,
        event_label=event_label,
    )


def select_features_by_epv(
    feature_names: list[str],
    y: np.ndarray | pd.Series,
    priority_order: list[str] | None = None,
    *,
    event_label: Any,
    threshold: float = EPV_MINIMUM,
) -> tuple[list[str], EPVResult]:
    """
    Automatically reduce feature set until EPV >= threshold.

    Features are dropped from the END of priority_order (lowest priority first).
    """
    y_arr, n_events = _event_count(y, event_label)
    if n_events < threshold:
        raise RuntimeError(
            f"Only {n_events} events (event_label={event_label!r}) — even 1 feature gives "
            f"EPV={n_events:.3g} < {threshold}. Cannot fit logistic regression safely."
        )

    order = list(priority_order) if priority_order else list(feature_names)
    max_features = int(n_events // threshold)
    max_features = max(max_features, 1)

    selected = [f for f in order if f in feature_names][:max_features]
    epv_result = compute_epv(
        y_arr, len(selected), event_label=event_label, threshold=threshold
    )
    return selected, epv_result
