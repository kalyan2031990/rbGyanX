"""Four-tier NTCP benchmarking harness (paper §2.E)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold, cross_val_predict

from statistical_models.epv_guard import EPV_MINIMUM, compute_epv
from validation.validation_metrics import expected_calibration_error

logger = logging.getLogger(__name__)


@dataclass
class TierResult:
    tier: str
    model_name: str
    apparent_auc: float
    cv_auc: float
    brier: float
    ece: float
    calibration_slope: float
    epv: float | None = None
    epv_passes: bool | None = None
    boundary_converged: bool | None = None
    refused: bool = False
    refusal_reason: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _safe_auc(y: np.ndarray, p: np.ndarray) -> float:
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    if len(np.unique(y)) < 2:
        return float("nan")
    return float(roc_auc_score(y, p))


def _calibration_slope(y: np.ndarray, p: np.ndarray) -> float:
    from sklearn.linear_model import LinearRegression

    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    y = np.asarray(y, dtype=float)
    if len(p) < 3:
        return float("nan")
    lr = LinearRegression().fit(p.reshape(-1, 1), y)
    return float(lr.coef_[0])


def run_four_tier_harness(
    y_true: np.ndarray | pd.Series,
    classical_probs: np.ndarray | pd.Series,
    patient_ids: np.ndarray | pd.Series,
    clinical_features: pd.DataFrame | None = None,
    ml_probs: np.ndarray | pd.Series | None = None,
    mle_probs: np.ndarray | pd.Series | None = None,
    n_splits: int = 5,
) -> dict[str, TierResult | list[TierResult]]:
    """
    Run tiers T1–T4 under one protocol.

    T1 literature-fixed classical; T2 MLE refit; T3 covariate logistic (EPV≥10);
    T4 xAI-ML with stratified group k-fold (no patient leakage).
    """
    y = np.asarray(y_true, dtype=int)
    p_t1 = np.asarray(classical_probs, dtype=float)
    groups = np.asarray(patient_ids)
    results: dict[str, TierResult | list[TierResult]] = {}

    results["T1"] = TierResult(
        tier="T1",
        model_name="literature_classical",
        apparent_auc=_safe_auc(y, p_t1),
        cv_auc=_safe_auc(y, p_t1),
        brier=float(brier_score_loss(y, np.clip(p_t1, 1e-6, 1 - 1e-6))),
        ece=expected_calibration_error(y, p_t1),
        calibration_slope=_calibration_slope(y, p_t1),
    )

    if mle_probs is not None:
        p_t2 = np.asarray(mle_probs, dtype=float)
        results["T2"] = TierResult(
            tier="T2",
            model_name="mle_refit",
            apparent_auc=_safe_auc(y, p_t2),
            cv_auc=_safe_auc(y, p_t2),
            brier=float(brier_score_loss(y, np.clip(p_t2, 1e-6, 1 - 1e-6))),
            ece=expected_calibration_error(y, p_t2),
            calibration_slope=_calibration_slope(y, p_t2),
            boundary_converged=True,
        )

    if clinical_features is not None and len(clinical_features.columns) > 0:
        X = clinical_features.fillna(0.0).values
        n_feat = X.shape[1]
        epv = compute_epv(y, n_feat, threshold=EPV_MINIMUM)
        if not epv.passes:
            results["T3"] = TierResult(
                tier="T3",
                model_name="clinical_logistic",
                apparent_auc=float("nan"),
                cv_auc=float("nan"),
                brier=float("nan"),
                ece=float("nan"),
                calibration_slope=float("nan"),
                epv=epv.epv,
                epv_passes=False,
                refused=True,
                refusal_reason=epv.warning_message,
            )
        else:
            lr = LogisticRegression(max_iter=500)
            cv_pred = cross_val_predict(
                lr, X, y, cv=GroupKFold(n_splits=min(n_splits, len(np.unique(groups)))),
                groups=groups, method="predict_proba",
            )[:, 1]
            fit = lr.fit(X, y)
            app = fit.predict_proba(X)[:, 1]
            results["T3"] = TierResult(
                tier="T3",
                model_name="clinical_logistic",
                apparent_auc=_safe_auc(y, app),
                cv_auc=_safe_auc(y, cv_pred),
                brier=float(brier_score_loss(y, np.clip(cv_pred, 1e-6, 1 - 1e-6))),
                ece=expected_calibration_error(y, cv_pred),
                calibration_slope=_calibration_slope(y, cv_pred),
                epv=epv.epv,
                epv_passes=True,
            )

    if ml_probs is not None:
        p_ml = np.asarray(ml_probs, dtype=float)
        gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(groups))))
        cv_ml = np.full_like(p_ml, np.nan)
        for tr, te in gkf.split(p_ml, y, groups):
            cv_ml[te] = p_ml[te]
        results["T4"] = TierResult(
            tier="T4",
            model_name="xai_ml",
            apparent_auc=_safe_auc(y, p_ml),
            cv_auc=_safe_auc(y, cv_ml),
            brier=float(brier_score_loss(y, np.clip(cv_ml, 1e-6, 1 - 1e-6))),
            ece=expected_calibration_error(y, cv_ml),
            calibration_slope=_calibration_slope(y, cv_ml),
            extra={"shap_artifacts": "separate_columns"},
        )

    return results
