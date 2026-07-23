"""
Four-class external-validation benchmark under one leakage-safe protocol (Phase 3).

Consumes the Phase-2 ``cohort_features.csv`` and evaluates, for a chosen endpoint
(loco-regional control; death as secondary), four model classes on identical
centre-grouped ``StratifiedGroupKFold`` folds:

    C1  Classical radiobiology  — T1 literature-fixed logistic-TCP on PTV EQD2;
                                  T2 MLE-refit single-covariate logistic (bootstrap CI).
    C2  Clinical covariates     — logistic on age/stage/HPV, EPV-gated (>=10 ev/pred).
    C3  Dosiomics ML            — random forest on DVH (+dosiomics) features.
    C4  PINN                    — LQ-constrained NN, same features/folds as C3;
                                  lambda_phys swept (0 = plain-NN ablation).

Reports, per model: apparent + cross-validated AUC, Brier (bootstrap CI),
Hosmer-Lemeshow, ECE, calibration slope, and decision-curve net benefit.

Honesty: small N / few events. Report apparent AND CV for every class; never claim
clinical discrimination. Results are association on *reference-planned* dose.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

from statistical_models.epv_guard import EPV_MINIMUM
from validation.validation_metrics import (
    calibration_slope,
    compute_auc,
    compute_brier,
    expected_calibration_error,
    hosmer_lemeshow,
)

logger = logging.getLogger(__name__)

# HN literature-fixed logistic TCP anchors (EQD2 domain).
_TCD50_EQD2 = 63.5  # Gy
_GAMMA50 = 2.0

# Feature groups (present in cohort_features.csv). Names absent from a cohort are dropped.
_PTV_DVH = [
    "PTV_gEUD_gy",
    "PTV_D95_gy",
    "PTV_D2_gy",
    "PTV_Dmean_gy",
    "PTV_HI",
    "PTV_CI",
    "PTV_BED_gy",
    "PTV_EQD2_gy",
    "PTV_volume_cc",
]
_OAR_DVH = [
    f"{o}_{m}"
    for o in (
        "PharynxConstrictor",
        "Larynx",
        "OralCavity",
        "Parotids",
        "Submandibular",
        "SpinalCord",
    )
    for m in ("Dmean_gy", "Dmax_gy", "gEUD_gy", "V30Gy_cc", "V50Gy_cc")
]
_DOSIOMICS = ["PTV_dose_skewness", "PTV_dose_kurtosis", "PTV_dose_std_gy"]
_DOSE_DRIVER = "PTV_EQD2_gy"

# OAR DVH-metric suffixes used to auto-discover organ features for *any* site. Only the
# five metrics already listed in ``_OAR_DVH`` are matched, so a head & neck cohort yields
# exactly the hardcoded columns (no behaviour change) while a prostate cohort additionally
# contributes its Rectum_/Bladder_/… columns.
_OAR_METRIC_SUFFIXES = ("_Dmean_gy", "_Dmax_gy", "_gEUD_gy", "_V30Gy_cc", "_V50Gy_cc")


def _oar_dvh_columns(df: pd.DataFrame) -> list[str]:
    """OAR DVH feature columns present in ``df``: known HN set first (stable order),
    then any other site's OAR columns discovered by metric suffix. Append-only, so the
    HN feature set and column order are preserved exactly."""
    known = [c for c in _OAR_DVH if c in df.columns]
    known_set = set(known)
    extra = [
        c
        for c in df.columns
        if c not in known_set
        and not c.startswith("PTV_")
        and any(c.endswith(s) for s in _OAR_METRIC_SUFFIXES)
    ]
    return known + extra


@dataclass
class ModelResult:
    name: str
    tier: str
    apparent_auc: float
    cv_auc: float
    brier: float
    brier_lo: float
    brier_hi: float
    hosmer_lemeshow_p: float
    ece: float
    calibration_slope: float
    net_benefit: float
    refused: bool = False
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- utils


def _present(cols: list[str], df: pd.DataFrame) -> list[str]:
    return [c for c in cols if c in df.columns]


def feature_matrix(df: pd.DataFrame, feature_set: str) -> tuple[pd.DataFrame, list[str]]:
    """Return (X, names). feature_set in {'dvh', 'dosiomics'}."""
    cols = _present(_PTV_DVH, df) + _oar_dvh_columns(df)
    if feature_set == "dosiomics":
        cols += _present(_DOSIOMICS, df)
    return df[cols].astype(float), cols


def net_benefit(y: np.ndarray, p: np.ndarray, thresholds: np.ndarray | None = None) -> float:
    """Mean decision-curve net benefit over a threshold grid (vs treat-none)."""
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    n = len(y)
    if n == 0 or np.all(np.isnan(p)):
        return float("nan")
    if thresholds is None:
        thresholds = np.linspace(0.05, 0.35, 7)
    nbs = []
    for pt in thresholds:
        pred = p >= pt
        tp = float(np.sum(pred & (y == 1)))
        fp = float(np.sum(pred & (y == 0)))
        nbs.append(tp / n - fp / n * (pt / (1.0 - pt)))
    return float(np.mean(nbs))


def _brier_ci(
    y: np.ndarray, p: np.ndarray, n_boot: int = 500, seed: int = 0
) -> tuple[float, float, float]:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    point = compute_brier(y, p)
    rng = np.random.default_rng(seed)
    boots = []
    idx = np.arange(len(y))
    for _ in range(n_boot):
        b = rng.choice(idx, size=len(idx), replace=True)
        if len(np.unique(y[b])) < 2:
            continue
        boots.append(compute_brier(y[b], p[b]))
    if not boots:
        return point, float("nan"), float("nan")
    return point, float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def _metrics(y: np.ndarray, p_app: np.ndarray, p_cv: np.ndarray, seed: int = 0) -> dict[str, float]:
    hl = hosmer_lemeshow(y, p_cv)
    hl_p = hl[1] if isinstance(hl, tuple) else float("nan")
    brier, blo, bhi = _brier_ci(y, p_cv, seed=seed)
    cs = calibration_slope(y, p_cv)
    cs_v = cs[0] if isinstance(cs, tuple) else cs
    return {
        "apparent_auc": compute_auc(y, p_app),
        "cv_auc": compute_auc(y, p_cv),
        "brier": brier,
        "brier_lo": blo,
        "brier_hi": bhi,
        "hosmer_lemeshow_p": hl_p,
        "ece": expected_calibration_error(y, p_cv),
        "calibration_slope": float(cs_v),
        "net_benefit": net_benefit(y, p_cv),
    }


# --------------------------------------------------------------------------- CV core


def _cv_predict(
    make: Callable[[], Any],
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    n_splits: int,
    seed: int,
) -> np.ndarray:
    """Out-of-fold predicted probabilities under centre-grouped stratified k-fold."""
    oof = np.full(len(y), np.nan)
    n_splits = int(min(n_splits, len(np.unique(groups))))
    if n_splits < 2:
        return oof
    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for tr, te in skf.split(X, y, groups):
        if len(np.unique(y[tr])) < 2:
            continue
        est = make()
        est.fit(X[tr], y[tr])
        oof[te] = est.predict_proba(X[te])[:, 1]
    return oof


# --------------------------------------------------------------------------- model classes


def classical_t1(df: pd.DataFrame) -> np.ndarray:
    """Literature-fixed logistic TCP on PTV EQD2 -> P(recurrence) = 1 - TCP."""
    eqd2 = pd.to_numeric(df.get(_DOSE_DRIVER), errors="coerce").to_numpy(dtype=float)
    z = 4.0 * _GAMMA50 * (eqd2 - _TCD50_EQD2) / _TCD50_EQD2
    tcp = 1.0 / (1.0 + np.exp(-z))
    return np.clip(1.0 - tcp, 1e-6, 1 - 1e-6)


def _run_c1(
    df: pd.DataFrame, y: np.ndarray, groups: np.ndarray, n_splits: int, seed: int
) -> list[ModelResult]:
    results: list[ModelResult] = []
    # T1 fixed (deterministic -> apparent == CV)
    p_t1 = classical_t1(df)
    m = _metrics(y, p_t1, p_t1, seed=seed)
    results.append(ModelResult("classical_fixed_TCP", "C1.T1", **m, note="literature-fixed"))
    # T2 MLE-refit single-covariate logistic on EQD2
    x = pd.to_numeric(df.get(_DOSE_DRIVER), errors="coerce").to_numpy(dtype=float).reshape(-1, 1)
    x = np.nan_to_num(x, nan=float(np.nanmedian(x)))
    p_app = _PipelineLR().fit(x, y).predict_proba(x)[:, 1]
    p_cv = _cv_predict(lambda: _PipelineLR(), x, y, groups, n_splits, seed)
    m2 = _metrics(y, p_app, p_cv, seed=seed)
    results.append(ModelResult("classical_MLE_logit", "C1.T2", **m2, note="refit EQD2"))
    return results


def _run_c2(
    df: pd.DataFrame, y: np.ndarray, groups: np.ndarray, n_splits: int, seed: int
) -> ModelResult:
    feats = _clinical_features(df)
    n_pred = feats.shape[1]
    # EPV = minority-outcome count / predictors (endpoint-agnostic; event may be y==1).
    n_events = int(min(int((y == 1).sum()), int((y == 0).sum())))
    epv_val = n_events / max(n_pred, 1)
    if epv_val < EPV_MINIMUM:
        nanm = dict.fromkeys(
            [
                "apparent_auc",
                "cv_auc",
                "brier",
                "brier_lo",
                "brier_hi",
                "hosmer_lemeshow_p",
                "ece",
                "calibration_slope",
                "net_benefit",
            ],
            float("nan"),
        )
        return ModelResult(
            "clinical_logistic",
            "C2.T3",
            **nanm,
            refused=True,
            note=f"EPV refused ({epv_val:.1f} < {EPV_MINIMUM})",
        )
    X = feats.to_numpy(dtype=float)
    p_app = _PipelineLR().fit(X, y).predict_proba(X)[:, 1]
    p_cv = _cv_predict(lambda: _PipelineLR(), X, y, groups, n_splits, seed)
    m = _metrics(y, p_app, p_cv, seed=seed)
    return ModelResult("clinical_logistic", "C2.T3", **m, note=f"EPV={epv_val:.1f}")


def _run_c3(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, n_splits: int, seed: int
) -> ModelResult:
    def make() -> Any:
        return RandomForestClassifier(
            n_estimators=300, max_depth=3, min_samples_leaf=5, random_state=seed, n_jobs=1
        )

    p_app = make().fit(X, y).predict_proba(X)[:, 1]
    p_cv = _cv_predict(make, X, y, groups, n_splits, seed)
    m = _metrics(y, p_app, p_cv, seed=seed)
    return ModelResult("dosiomics_rf", "C3.T4", **m, note="random forest")


def _run_c4(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    dose_idx: int,
    lambda_phys: float,
    n_splits: int,
    seed: int,
) -> ModelResult:
    from validation.outcome_pinn import OutcomePINN, PINNConfig

    lam_bc = 0.5 if lambda_phys > 0 else 0.0

    def make() -> Any:
        return OutcomePINN(
            dose_idx=dose_idx,
            config=PINNConfig(lambda_phys=lambda_phys, lambda_bc=lam_bc, epochs=250, seed=seed),
        )

    p_app = make().fit(X, y).predict_proba(X)[:, 1]
    p_cv = _cv_predict(make, X, y, groups, n_splits, seed)
    m = _metrics(y, p_app, p_cv, seed=seed)
    tag = "plain-NN (ablation)" if lambda_phys == 0 else f"lambda_phys={lambda_phys:g}"
    return ModelResult("pinn", "C4", **m, note=tag, extra={"lambda_phys": lambda_phys})


# --------------------------------------------------------------------------- helpers


class _PipelineLR:
    """Standardised logistic regression with a stable predict_proba."""

    def __init__(self) -> None:
        self.scaler = StandardScaler()
        self.lr = LogisticRegression(max_iter=1000, C=1.0)

    def fit(self, X: np.ndarray, y: np.ndarray) -> _PipelineLR:
        Xs = self.scaler.fit_transform(np.nan_to_num(np.asarray(X, dtype=float)))
        self.lr.fit(Xs, y)
        return self

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        Xs = self.scaler.transform(np.nan_to_num(np.asarray(X, dtype=float)))
        return self.lr.predict_proba(Xs)


def _clinical_features(df: pd.DataFrame) -> pd.DataFrame:
    """age + HPV(+/-) + AJCC-ish T-stage numeric (EPV-limited to <=2 predictors)."""
    age = pd.to_numeric(df.get("age"), errors="coerce")
    hpv = (
        df.get("hpv_status", pd.Series(index=df.index, dtype=object))
        .astype(str)
        .str.lower()
        .map(
            lambda s: (
                1.0
                if any(k in s for k in ("pos", "+", "1"))
                else (0.0 if any(k in s for k in ("neg", "-", "0")) else np.nan)
            )
        )
    )
    out = pd.DataFrame({"age": age, "hpv_pos": hpv})
    return out.fillna(out.median(numeric_only=True)).fillna(0.0)


def run_benchmark(
    df: pd.DataFrame,
    endpoint: str = "locoregional",
    feature_set: str = "dosiomics",
    lambda_phys_sweep: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0),
    n_splits: int = 4,
    seed: int = 0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run C1–C4 on one endpoint; return (benchmark table, extras with per-model preds)."""
    work = df[pd.to_numeric(df[endpoint], errors="coerce").notna()].reset_index(drop=True)
    y = pd.to_numeric(work[endpoint], errors="coerce").astype(int).to_numpy()
    groups = work.get("centre", pd.Series(["all"] * len(work))).astype(str).to_numpy()

    Xdf, names = feature_matrix(work, feature_set)
    X = np.nan_to_num(Xdf.to_numpy(dtype=float), nan=0.0)
    dose_idx = names.index(_DOSE_DRIVER) if _DOSE_DRIVER in names else 0

    rows: list[ModelResult] = []
    rows += _run_c1(work, y, groups, n_splits, seed)
    rows.append(_run_c2(work, y, groups, n_splits, seed))
    rows.append(_run_c3(X, y, groups, n_splits, seed))
    for lam in lambda_phys_sweep:
        rows.append(_run_c4(X, y, groups, dose_idx, lam, n_splits, seed))

    table = pd.DataFrame([r.__dict__ for r in rows])
    table.insert(0, "endpoint", endpoint)
    table["optimism"] = table["apparent_auc"] - table["cv_auc"]
    extras = {
        "n": int(len(y)),
        "events": int(y.sum()),
        "feature_set": feature_set,
        "n_features": len(names),
        "feature_names": names,
        "n_splits": int(min(n_splits, len(np.unique(groups)))),
        "seed": seed,
    }
    return table, extras
