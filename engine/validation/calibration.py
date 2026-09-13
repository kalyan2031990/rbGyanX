# validation/calibration.py

from __future__ import annotations

import pathlib
from dataclasses import dataclass

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from sklearn.calibration import calibration_curve


@dataclass
class CalibrationResult:
    slope: float
    intercept: float
    hl_statistic: float
    hl_pvalue: float
    hl_dof: int
    n_groups: int


def compute_calibration_slope_intercept(
    y_true: np.ndarray,
    y_prob: np.ndarray,
) -> tuple[float, float]:
    """
    Logistic calibration: fit logit(y_prob) → y_true.
    """
    from sklearn.linear_model import LogisticRegression

    logit_p = np.log(
        np.clip(y_prob, 1e-9, 1 - 1e-9) / (1 - np.clip(y_prob, 1e-9, 1 - 1e-9))
    )
    lr = LogisticRegression(penalty=None, solver="lbfgs", max_iter=500)
    lr.fit(logit_p.reshape(-1, 1), y_true)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


def hosmer_lemeshow_test(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    n_groups: int = 10,
) -> CalibrationResult:
    """
    Hosmer-Lemeshow goodness-of-fit test.
    """
    from scipy import stats as sp_stats

    y = np.asarray(y_true, dtype=float)
    p = np.asarray(y_prob, dtype=float)
    n = len(y)

    order = np.argsort(p)
    y_s, p_s = y[order], p[order]
    groups = np.array_split(np.arange(n), n_groups)

    hl_stat = 0.0
    for grp in groups:
        if len(grp) == 0:
            continue
        obs_1 = y_s[grp].sum()
        exp_1 = p_s[grp].sum()
        obs_0 = len(grp) - obs_1
        exp_0 = len(grp) - exp_1
        if exp_1 > 0:
            hl_stat += (obs_1 - exp_1) ** 2 / exp_1
        if exp_0 > 0:
            hl_stat += (obs_0 - exp_0) ** 2 / exp_0

    dof = n_groups - 2
    pvalue = float(1 - sp_stats.chi2.cdf(hl_stat, df=max(dof, 1)))
    slope, intercept = compute_calibration_slope_intercept(y, p)

    return CalibrationResult(
        slope=slope,
        intercept=intercept,
        hl_statistic=float(hl_stat),
        hl_pvalue=pvalue,
        hl_dof=dof,
        n_groups=n_groups,
    )


def plot_calibration(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    model_label: str,
    output_path: str | pathlib.Path,
    n_bins: int = 10,
    dpi: int = 600,
) -> pathlib.Path:
    """
    Calibration plot: fraction of positives vs mean predicted probability.
    """
    frac_pos, mean_pred = calibration_curve(
        y_true, y_prob, n_bins=n_bins, strategy="uniform"
    )
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, label="Perfect calibration")
    ax.plot(mean_pred, frac_pos, "o-", color="steelblue", label=model_label)
    ax.set_xlabel("Mean predicted probability")
    ax.set_ylabel("Fraction of positives (local control)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8)
    ax.set_title("Calibration Plot")
    plt.tight_layout()
    out = pathlib.Path(output_path)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out
