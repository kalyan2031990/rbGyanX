# validation/external_val.py

from __future__ import annotations

import numpy as np
from scipy import stats


def check_covariate_shift(
    X_train: np.ndarray,
    X_external: np.ndarray,
    feature_names: list[str],
    alpha: float = 0.05,
) -> dict:
    """
    Check for covariate shift between training and external cohort.
    """
    results: dict = {}
    n_shifted = 0
    for i, feat in enumerate(feature_names):
        ks, pval = stats.ks_2samp(X_train[:, i], X_external[:, i])
        shifted = bool(pval < alpha)
        if shifted:
            n_shifted += 1
        results[feat] = {
            "ks_statistic": float(ks),
            "pvalue": float(pval),
            "shifted": shifted,
        }
    results["n_shifted"] = n_shifted
    results["shift_detected"] = n_shifted > 0
    return results


def validate_on_external(
    model,
    X_external: np.ndarray,
    y_external: np.ndarray,
    feature_names: list[str],
    X_train: np.ndarray | None = None,
) -> dict:
    """
    Evaluate a frozen model on an external validation cohort.
    """
    from validation.calibration import hosmer_lemeshow_test
    from validation.tcp_evaluator import evaluate_model

    y_prob = model.predict_proba(X_external)[:, 1]
    eval_r = evaluate_model(y_external, y_prob)
    cal_r = hosmer_lemeshow_test(y_external, y_prob)

    result = {
        "auc": eval_r.auc,
        "auc_ci": (eval_r.auc_ci_lower, eval_r.auc_ci_upper),
        "brier_score": eval_r.brier_score,
        "ece": eval_r.ece,
        "calibration_slope": cal_r.slope,
        "calibration_intercept": cal_r.intercept,
        "hl_pvalue": cal_r.hl_pvalue,
        "n_patients": len(y_external),
        "n_events": eval_r.n_events,
    }
    if X_train is not None:
        shift = check_covariate_shift(X_train, X_external, feature_names)
        result["covariate_shift"] = shift

    return result
