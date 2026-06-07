# validation/tcp_evaluator.py

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, roc_auc_score


@dataclass
class EvaluationResult:
    auc: float
    auc_ci_lower: float
    auc_ci_upper: float
    brier_score: float
    ece: float
    overfitting_index: float | None
    cv_auc: float | None
    n_samples: int
    n_events: int
    warnings: list[str] = field(default_factory=list)


def delong_auc_ci(
    y_true: np.ndarray,
    y_score: np.ndarray,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """
    Compute AUC with DeLong 95% confidence interval.
    """
    y = np.asarray(y_true, dtype=int)
    sc = np.asarray(y_score, dtype=float)
    pos = sc[y == 1]
    neg = sc[y == 0]
    n_pos, n_neg = len(pos), len(neg)

    if n_pos == 0 or n_neg == 0:
        return math.nan, math.nan, math.nan

    auc = float(roc_auc_score(y, sc))

    theta_x = np.array(
        [
            np.mean(pos[i] > neg) + 0.5 * np.mean(pos[i] == neg)
            for i in range(n_pos)
        ]
    )
    theta_y = np.array(
        [
            np.mean(neg[j] < pos) + 0.5 * np.mean(neg[j] == pos)
            for j in range(n_neg)
        ]
    )

    V10 = np.var(theta_x, ddof=1) if n_pos > 1 else 0.0
    V01 = np.var(theta_y, ddof=1) if n_neg > 1 else 0.0
    var_auc = V10 / n_pos + V01 / n_neg

    from scipy import stats

    z = stats.norm.ppf(1 - alpha / 2)
    se = math.sqrt(max(var_auc, 0.0))
    lower = float(np.clip(auc - z * se, 0.0, 1.0))
    upper = float(np.clip(auc + z * se, 0.0, 1.0))
    return auc, lower, upper


def compute_ece(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_bins: int = 10,
) -> float:
    """
    Expected Calibration Error (ECE).
    """
    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    n = len(y)
    if n == 0:
        return math.nan

    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p >= lo) & (p < hi)
        if not mask.any():
            continue
        n_b = mask.sum()
        acc_b = y[mask].mean()
        conf_b = p[mask].mean()
        ece += (n_b / n) * abs(acc_b - conf_b)
    return float(ece)


def evaluate_model(
    y_true: np.ndarray | pd.Series,
    y_prob: np.ndarray | pd.Series,
    cv_auc: float | None = None,
    n_ece_bins: int = 10,
) -> EvaluationResult:
    """
    Compute full evaluation suite for a binary TCP model.

    y_true: 1 = local control, 0 = recurrence.
    y_prob: predicted P(local_control=1).
    """
    y = np.asarray(y_true, dtype=int)
    p = np.asarray(y_prob, dtype=float)
    warns: list[str] = []

    if len(np.unique(y)) < 2:
        warns.append("Only one class present — AUC undefined.")
        return EvaluationResult(
            auc=math.nan,
            auc_ci_lower=math.nan,
            auc_ci_upper=math.nan,
            brier_score=math.nan,
            ece=math.nan,
            overfitting_index=math.nan,
            cv_auc=cv_auc,
            n_samples=len(y),
            n_events=int(np.sum(y == 0)),
            warnings=warns,
        )

    auc, ci_lo, ci_hi = delong_auc_ci(y, p)
    brier = float(brier_score_loss(y, p))
    ece = compute_ece(y, p, n_bins=n_ece_bins)

    overfit = None
    if cv_auc is not None and math.isfinite(auc) and auc > 0:
        overfit = float((auc - cv_auc) / auc)
        if overfit > 0.10:
            warns.append(
                f"Overfitting index {overfit:.3f} > 0.10 — model may be overfit. "
                f"Apparent AUC={auc:.3f}, CV AUC={cv_auc:.3f}."
            )

    return EvaluationResult(
        auc=auc,
        auc_ci_lower=ci_lo,
        auc_ci_upper=ci_hi,
        brier_score=brier,
        ece=ece,
        overfitting_index=overfit,
        cv_auc=cv_auc,
        n_samples=len(y),
        n_events=int(np.sum(y == 0)),
        warnings=warns,
    )
