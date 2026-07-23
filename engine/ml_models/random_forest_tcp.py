# ml_models/random_forest_tcp.py

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GridSearchCV, StratifiedGroupKFold, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ml_models.xgboost_tcp import MIN_COHORT_SIZE

RF_PARAM_GRID = {
    "rf__n_estimators": [100, 200],
    "rf__max_depth": [None, 5, 10],
    "rf__min_samples_leaf": [2, 5],
    "rf__max_features": ["sqrt", 0.5],
}


@dataclass
class RandomForestTCPResult:
    model: Any
    feature_names: list[str]
    feature_importances: dict[str, float]
    outer_fold_aucs: list[float]
    inner_fold_aucs: list[float]
    auc_outer_mean: float
    auc_outer_sd: float
    auc_inner_mean: float
    shap_values: np.ndarray | None
    shap_expected_value: float | None
    n_samples: int
    best_params: dict
    warnings: list[str] = field(default_factory=list)


def _make_rf_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "rf",
                RandomForestClassifier(
                    class_weight="balanced",
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ]
    )


def fit_random_forest_tcp(
    X: pd.DataFrame | np.ndarray,
    y: np.ndarray | pd.Series,
    feature_names: list[str] | None = None,
    param_grid: dict | None = None,
    outer_folds: int = 5,
    inner_folds: int = 5,
    random_state: int = 42,
    compute_shap: bool = True,
    patient_ids: np.ndarray | None = None,
) -> RandomForestTCPResult:
    """
    Random Forest with nested cross-validation for TCP binary outcome prediction.
    """
    X_arr = np.asarray(X, dtype=float)
    y_arr = np.asarray(y, dtype=int)
    n, n_f = X_arr.shape
    fname = list(feature_names) if feature_names else [f"feat_{i}" for i in range(n_f)]
    pg = param_grid or RF_PARAM_GRID
    warns: list[str] = []

    if n < MIN_COHORT_SIZE:
        raise ValueError(
            f"Cohort size {n} < minimum {MIN_COHORT_SIZE} required for ML models."
        )

    use_groups = patient_ids is not None
    groups = np.asarray(patient_ids) if use_groups else None
    if use_groups:
        outer_cv = StratifiedGroupKFold(
            n_splits=outer_folds, shuffle=True, random_state=random_state
        )
        inner_cv = StratifiedGroupKFold(
            n_splits=inner_folds, shuffle=True, random_state=random_state
        )
    else:
        outer_cv = StratifiedKFold(
            n_splits=outer_folds, shuffle=True, random_state=random_state
        )
        inner_cv = StratifiedKFold(
            n_splits=inner_folds, shuffle=True, random_state=random_state
        )

    outer_aucs: list[float] = []
    inner_aucs: list[float] = []
    best_params_last: dict = {}

    outer_splits = (
        outer_cv.split(X_arr, y_arr, groups=groups)
        if use_groups
        else outer_cv.split(X_arr, y_arr)
    )
    for fold_idx, (train_idx, test_idx) in enumerate(outer_splits):
        X_tr, X_te = X_arr[train_idx], X_arr[test_idx]
        y_tr, y_te = y_arr[train_idx], y_arr[test_idx]

        if len(np.unique(y_te)) < 2:
            warns.append(f"Outer fold {fold_idx}: test set has only one class; skipped.")
            continue

        pipe = _make_rf_pipeline()
        gs = GridSearchCV(
            pipe, pg, cv=inner_cv, scoring="roc_auc", refit=True, n_jobs=-1
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if use_groups:
                gs.fit(X_tr, y_tr, groups=groups[train_idx])
            else:
                gs.fit(X_tr, y_tr)

        best_params_last = gs.best_params_
        inner_aucs.append(float(gs.best_score_))

        prob_te = gs.best_estimator_.predict_proba(X_te)[:, 1]
        outer_auc = float(roc_auc_score(y_te, prob_te))
        outer_aucs.append(outer_auc)

    for i, (inn, out) in enumerate(zip(inner_aucs, outer_aucs)):
        if out > inn + 0.15:
            warns.append(
                f"Outer fold {i}: outer AUC {out:.3f} > inner AUC {inn:.3f} + 0.15 "
                f"— possible data leakage."
            )

    final_pipe = _make_rf_pipeline()
    gs_final = GridSearchCV(
        final_pipe, pg, cv=inner_cv, scoring="roc_auc", refit=True, n_jobs=-1
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if use_groups:
            gs_final.fit(X_arr, y_arr, groups=groups)
        else:
            gs_final.fit(X_arr, y_arr)

    final_model = gs_final.best_estimator_

    rf_step = final_model.named_steps["rf"]
    importances = dict(zip(fname, rf_step.feature_importances_.tolist()))

    shap_values, shap_ev = None, None
    if compute_shap:
        try:
            import shap

            X_scaled = final_model.named_steps["scaler"].transform(X_arr)
            explainer = shap.TreeExplainer(rf_step)
            sv = explainer.shap_values(X_scaled)
            if isinstance(sv, list):
                sv = sv[1]
            shap_values = sv
            shap_ev = float(
                explainer.expected_value
                if not isinstance(explainer.expected_value, (list, np.ndarray))
                else explainer.expected_value[1]
            )
        except Exception as exc:
            warns.append(f"SHAP computation failed: {exc}")

    return RandomForestTCPResult(
        model=final_model,
        feature_names=fname,
        feature_importances=importances,
        outer_fold_aucs=outer_aucs,
        inner_fold_aucs=inner_aucs,
        auc_outer_mean=float(np.mean(outer_aucs)) if outer_aucs else math.nan,
        auc_outer_sd=float(np.std(outer_aucs, ddof=1)) if len(outer_aucs) > 1 else math.nan,
        auc_inner_mean=float(np.mean(inner_aucs)) if inner_aucs else math.nan,
        shap_values=shap_values,
        shap_expected_value=shap_ev,
        n_samples=n,
        best_params=best_params_last,
        warnings=warns,
    )
