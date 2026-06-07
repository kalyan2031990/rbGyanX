"""Bayesian LKB NTCP inference (PyMC when available; bootstrap emulation otherwise)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import ndtr

logger = logging.getLogger(__name__)

try:
    import pymc as pm  # noqa: F401

    _PYMC_AVAILABLE = True
except ImportError:
    _PYMC_AVAILABLE = False


@dataclass
class BayesianPosterior:
    """Posterior samples for LKB probit (TD50, m). Works without PyMC."""

    organ: str
    td50_samples: np.ndarray
    m_samples: np.ndarray
    n_patients: int = 0
    n_events: int = 0
    rhat_max: float = 1.0
    converged: bool = True
    method: str = "emulation"
    pymc_trace: object | None = field(default=None, repr=False)

    @property
    def td50_mean(self) -> float:
        return float(self.td50_samples.mean())

    @property
    def td50_sd(self) -> float:
        return float(self.td50_samples.std())

    @property
    def m_mean(self) -> float:
        return float(self.m_samples.mean())

    @property
    def m_sd(self) -> float:
        return float(self.m_samples.std())

    def summary_dict(self) -> dict:
        return {
            "organ": self.organ,
            "td50_mean": self.td50_mean,
            "td50_sd": self.td50_sd,
            "td50_hdi_lower": float(np.percentile(self.td50_samples, 2.5)),
            "td50_hdi_upper": float(np.percentile(self.td50_samples, 97.5)),
            "m_mean": self.m_mean,
            "m_sd": self.m_sd,
            "m_hdi_lower": float(np.percentile(self.m_samples, 2.5)),
            "m_hdi_upper": float(np.percentile(self.m_samples, 97.5)),
            "n_patients": self.n_patients,
            "n_events": self.n_events,
            "rhat_max": self.rhat_max,
            "converged": self.converged,
            "method": self.method,
        }


def _lkb_ntcp(geud: np.ndarray, td50: float, m: float) -> np.ndarray:
    t = (geud - td50) / (m * td50)
    return np.clip(ndtr(t), 1e-9, 1 - 1e-9)


def _fit_emulation(
    geud: np.ndarray,
    outcomes: np.ndarray,
    organ: str,
    prior_td50_mean: float,
    prior_m_mean: float,
    n_bootstrap: int = 400,
) -> BayesianPosterior:
    geud = np.asarray(geud, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    valid = np.isfinite(geud) & np.isfinite(y)
    geud, y = geud[valid], y[valid]
    n = len(geud)

    def nll(params, g: np.ndarray = geud, yy: np.ndarray = y):
        td50, m = params
        if td50 <= 5 or m <= 0.01 or m >= 0.8:
            return 1e10
        p = _lkb_ntcp(g, td50, m)
        return -float(np.sum(yy * np.log(p) + (1 - yy) * np.log(1 - p)))

    res = minimize(
        nll,
        x0=[prior_td50_mean, prior_m_mean],
        method="L-BFGS-B",
        bounds=[(5.0, 120.0), (0.02, 0.6)],
    )
    td50_hat, m_hat = (res.x[0], res.x[1]) if res.success else (prior_td50_mean, prior_m_mean)

    rng = np.random.default_rng(42)
    td50_boot: list[float] = []
    m_boot: list[float] = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n) if n > 1 else np.arange(n)
        g_b, y_b = geud[idx], y[idx]
        if len(np.unique(y_b)) < 2:
            td50_boot.append(td50_hat)
            m_boot.append(m_hat)
            continue
        r2 = minimize(
            nll,
            x0=[td50_hat, m_hat],
            method="L-BFGS-B",
            bounds=[(5.0, 120.0), (0.02, 0.6)],
            args=(g_b, y_b),
        )
        try:
            td50_boot.append(r2.x[0])
            m_boot.append(r2.x[1])
        except Exception:
            td50_boot.append(td50_hat)
            m_boot.append(m_hat)

    return BayesianPosterior(
        organ=organ,
        td50_samples=np.asarray(td50_boot, dtype=float),
        m_samples=np.asarray(m_boot, dtype=float),
        n_patients=n,
        n_events=int(y.sum()),
        rhat_max=1.0,
        converged=True,
        method="bootstrap_emulation",
    )


def _fit_pymc(
    geud: np.ndarray,
    outcomes: np.ndarray,
    organ: str,
    prior_td50_mean: float,
    prior_td50_sd: float,
    prior_m_mean: float,
    prior_m_sd: float,
    n_samples: int,
    n_tune: int,
    target_accept: float,
) -> BayesianPosterior:
    import pymc as pm

    geud = np.asarray(geud, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    valid = np.isfinite(geud) & np.isfinite(y)
    geud, y = geud[valid], y[valid]

    with pm.Model() as model:
        td50 = pm.TruncatedNormal("TD50", mu=prior_td50_mean, sigma=prior_td50_sd, lower=5.0)
        m = pm.TruncatedNormal("m", mu=prior_m_mean, sigma=prior_m_sd, lower=0.01, upper=0.8)
        t = (geud - td50) / (m * td50)
        ntcp_prob = pm.math.sigmoid(t * 1.7)
        pm.Bernoulli("obs", p=ntcp_prob, observed=y)
        trace = pm.sample(
            draws=min(n_samples, 800),
            tune=min(n_tune, 400),
            target_accept=target_accept,
            progressbar=False,
            return_inferencedata=True,
            chains=2,
            cores=1,
        )

    try:
        import arviz as az

        summary = az.summary(trace, var_names=["TD50", "m"], hdi_prob=0.95)
        rhat_max = float(summary["r_hat"].max())
    except Exception:
        rhat_max = 1.0

    td50_post = trace.posterior["TD50"].values.flatten()
    m_post = trace.posterior["m"].values.flatten()

    return BayesianPosterior(
        organ=organ,
        td50_samples=td50_post,
        m_samples=m_post,
        n_patients=len(geud),
        n_events=int(y.sum()),
        rhat_max=rhat_max,
        converged=rhat_max <= 1.05,
        method="pymc",
        pymc_trace=trace,
    )


def fit_lkb_bayesian(
    geud_values: np.ndarray,
    outcomes: np.ndarray,
    organ: str,
    prior_td50_mean: float = 50.0,
    prior_td50_sd: float = 15.0,
    prior_m_mean: float = 0.15,
    prior_m_sd: float = 0.05,
    n_samples: int = 500,
    n_tune: int = 500,
    target_accept: float = 0.9,
    prefer_pymc: bool = True,
) -> BayesianPosterior:
    geud = np.asarray(geud_values, dtype=float)
    y = np.asarray(outcomes, dtype=float)
    valid = np.isfinite(geud) & np.isfinite(y)
    geud, y = geud[valid], y[valid]

    if len(geud) < 10:
        logger.warning("Bayesian NTCP: n=%d for %s — weak fit.", len(geud), organ)

    if prefer_pymc and _PYMC_AVAILABLE and len(geud) >= 15 and y.sum() >= 3:
        try:
            return _fit_pymc(
                geud,
                y,
                organ,
                prior_td50_mean,
                prior_td50_sd,
                prior_m_mean,
                prior_m_sd,
                n_samples,
                n_tune,
                target_accept,
            )
        except Exception as exc:
            logger.warning("PyMC fit failed for %s (%s); using emulation.", organ, exc)

    return _fit_emulation(geud, y, organ, prior_td50_mean, prior_m_mean)


def propagate_ntcp_uncertainty_bayesian(
    geud: float,
    posterior: BayesianPosterior,
    n_draws: int = 500,
) -> dict[str, float]:
    if not math.isfinite(geud):
        nan = math.nan
        return {
            "ntcp_mean": nan,
            "ntcp_sd": nan,
            "ntcp_ci_lower": nan,
            "ntcp_ci_upper": nan,
        }
    rng = np.random.default_rng(42)
    n = len(posterior.td50_samples)
    idx = rng.integers(0, n, size=n_draws)
    samples = _lkb_ntcp(
        np.full(n_draws, geud),
        posterior.td50_samples[idx],
        posterior.m_samples[idx],
    )
    return {
        "ntcp_mean": float(samples.mean()),
        "ntcp_sd": float(samples.std()),
        "ntcp_ci_lower": float(np.percentile(samples, 2.5)),
        "ntcp_ci_upper": float(np.percentile(samples, 97.5)),
    }


def save_posterior(posterior: BayesianPosterior, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        organ=posterior.organ,
        td50_samples=posterior.td50_samples,
        m_samples=posterior.m_samples,
        n_patients=posterior.n_patients,
        n_events=posterior.n_events,
        method=posterior.method,
        rhat_max=posterior.rhat_max,
        converged=posterior.converged,
    )
    return path


def load_posterior(path: Path) -> BayesianPosterior | None:
    path = Path(path)
    if not path.is_file():
        return None
    data = np.load(path, allow_pickle=True)
    return BayesianPosterior(
        organ=str(data["organ"]),
        td50_samples=data["td50_samples"],
        m_samples=data["m_samples"],
        n_patients=int(data["n_patients"]),
        n_events=int(data["n_events"]),
        rhat_max=float(data["rhat_max"]),
        converged=bool(data["converged"]),
        method=str(data["method"]),
    )
