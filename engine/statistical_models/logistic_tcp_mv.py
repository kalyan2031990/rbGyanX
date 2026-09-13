"""L2-regularised multivariate logistic TCP regression with cross-validation."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import LeaveOneOut, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from statistical_models.epv_guard import EPV_MINIMUM, compute_epv


@dataclass
class MVLResult:
    """Results from multivariate logistic TCP regression."""

    pipeline: Any
    feature_names: list[str]
    coefficients: dict[str, float]
    intercept: float
    auc_apparent: float
    brier_apparent: float
    auc_loo: float
    auc_loo_sd: float
    auc_5fold: float
    auc_5fold_sd: float
    epv: float
    n_events: int
    n_samples: int
    prob_train: np.ndarray
    warnings: list[str] = field(default_factory=list)


def _make_pipeline(C: float = 1.0) -> Pipeline:
    """StandardScaler + L2 logistic regression pipeline."""
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "lr",
                LogisticRegression(
                    penalty="l2",
                    C=C,
                    solver="lbfgs",
                    max_iter=1000,
                    class_weight="balanced",
                ),
            ),
        ]
    )


def fit_mvl_tcp(
    X: pd.DataFrame | np.ndarray,
    y: np.ndarray | pd.Series,
    feature_names: list[str] | None = None,
    C: float = 1.0,
    epv_threshold: float = EPV_MINIMUM,
    random_state: int = 42,
) -> MVLResult:
    """
    Fit EPV-gated L2-regularised logistic regression for TCP prediction.

    y: 1 = local control (majority), 0 = recurrence (minority = event).
    """
    X_arr = np.asarray(X, dtype=float)
    y_arr = np.asarray(y, dtype=int)
    n_samples, n_features = X_arr.shape
    fname = feature_names or [f"feat_{i}" for i in range(n_features)]

    epv_result = compute_epv(y_arr, n_features, epv_threshold)
    warns: list[str] = []
    if not epv_result.passes:
        raise ValueError(epv_result.warning_message)

    pipe = _make_pipeline(C=C)
    pipe.fit(X_arr, y_arr)
    prob_train = pipe.predict_proba(X_arr)[:, 1]
    auc_app = float(roc_auc_score(y_arr, prob_train))
    brier_app = float(brier_score_loss(y_arr, prob_train))

    lr = pipe.named_steps["lr"]
    coefs = {fname[i]: float(lr.coef_[0][i]) for i in range(n_features)}

    loo = LeaveOneOut()
    loo_probs = np.full(n_samples, math.nan)
    for train_idx, test_idx in loo.split(X_arr):
        p = _make_pipeline(C=C)
        p.fit(X_arr[train_idx], y_arr[train_idx])
        loo_probs[test_idx] = p.predict_proba(X_arr[test_idx])[:, 1]

    auc_loo = float(roc_auc_score(y_arr, loo_probs))
    rng = np.random.default_rng(random_state)
    boot_aucs = []
    for _ in range(200):
        idx = rng.integers(0, n_samples, size=n_samples)
        if len(np.unique(y_arr[idx])) < 2:
            continue
        boot_aucs.append(roc_auc_score(y_arr[idx], loo_probs[idx]))
    auc_loo_sd = float(np.std(boot_aucs, ddof=1)) if boot_aucs else math.nan

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=random_state)
    fold_aucs = []
    for train_idx, test_idx in skf.split(X_arr, y_arr):
        if len(np.unique(y_arr[test_idx])) < 2:
            warns.append("5-fold: a fold had only one class; skipped.")
            continue
        p = _make_pipeline(C=C)
        p.fit(X_arr[train_idx], y_arr[train_idx])
        probs = p.predict_proba(X_arr[test_idx])[:, 1]
        fold_aucs.append(roc_auc_score(y_arr[test_idx], probs))

    auc_5fold = float(np.mean(fold_aucs)) if fold_aucs else math.nan
    auc_5fold_sd = float(np.std(fold_aucs, ddof=1)) if len(fold_aucs) > 1 else math.nan

    return MVLResult(
        pipeline=pipe,
        feature_names=fname,
        coefficients=coefs,
        intercept=float(lr.intercept_[0]),
        auc_apparent=auc_app,
        brier_apparent=brier_app,
        auc_loo=auc_loo,
        auc_loo_sd=auc_loo_sd,
        auc_5fold=auc_5fold,
        auc_5fold_sd=auc_5fold_sd,
        epv=epv_result.epv,
        n_events=epv_result.n_events,
        n_samples=n_samples,
        prob_train=prob_train,
        warnings=warns,
    )


def predict_tcp_mvl(
    pipeline: Any,
    X_new: pd.DataFrame | np.ndarray,
) -> np.ndarray:
    """Apply fitted MVL pipeline to new patients. Returns P(local_control=1)."""
    return pipeline.predict_proba(np.asarray(X_new, dtype=float))[:, 1]
