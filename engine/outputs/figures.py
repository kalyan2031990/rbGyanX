# outputs/figures.py

from __future__ import annotations

import pathlib

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def plot_dose_response_curves(
    site_params,
    dose_range_gy: tuple[float, float] = (20.0, 90.0),
    n_fractions: int = 30,
    output_path: str | pathlib.Path = "dose_response.png",
    dpi: int = 600,
) -> pathlib.Path:
    """
    Plot classical TCP vs total dose for all four models.
    """
    from radiobiology.geud_tcp import GEUDTCPCalculator
    from radiobiology.logistic_tcp import LogisticTCPCalculator
    from radiobiology.poisson_tcp import PoissonTCPCalculator
    from radiobiology.zaider_minerbo import ZMTCPCalculator

    doses = np.linspace(dose_range_gy[0], dose_range_gy[1], 60)
    tcp_p, tcp_zm, tcp_g, tcp_l = [], [], [], []

    poisson = PoissonTCPCalculator()
    zm = ZMTCPCalculator()
    geud = GEUDTCPCalculator()
    logistic = LogisticTCPCalculator()

    for d in doses:
        dvh = pd.DataFrame({"dose_gy": [d], "volume_frac": [1.0]})
        try:
            tcp_p.append(poisson.compute_tcp_dvh(dvh, n_fractions, site_params)["tcp"])
        except Exception:
            tcp_p.append(float("nan"))
        try:
            tcp_zm.append(zm.compute_tcp_dvh(dvh, n_fractions, site_params)["tcp"])
        except Exception:
            tcp_zm.append(float("nan"))
        try:
            tcp_g.append(geud.compute_tcp(dvh, site_params)["tcp"])
        except Exception:
            tcp_g.append(float("nan"))
        try:
            tcp_l.append(logistic.compute_tcp(dvh, site_params)["tcp"])
        except Exception:
            tcp_l.append(float("nan"))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(doses, tcp_p, label="Poisson-LQ", linewidth=2.0)
    ax.plot(doses, tcp_zm, label="Zaider-Minerbo", linewidth=2.0, linestyle="--")
    ax.plot(doses, tcp_g, label="gEUD-TCP", linewidth=2.0, linestyle="-.")
    ax.plot(doses, tcp_l, label="Logistic", linewidth=2.0, linestyle=":")
    ax.axvline(
        site_params.TCD50_gy,
        color="grey",
        linewidth=0.8,
        linestyle="--",
        label=f"TCD50={site_params.TCD50_gy} Gy",
    )
    ax.set_xlabel("Total Dose (Gy)")
    ax.set_ylabel("TCP (probability)")
    ax.set_ylim(0, 1)
    ax.set_title(f"TCP Dose-Response Curves — {site_params.site}")
    ax.legend(fontsize=8)
    plt.tight_layout()
    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_uncertainty_bands(
    doses_gy: np.ndarray,
    tcp_mean: np.ndarray,
    tcp_p5: np.ndarray,
    tcp_p95: np.ndarray,
    model_label: str,
    output_path: str | pathlib.Path,
    dpi: int = 600,
) -> pathlib.Path:
    """
    TCP dose-response with MC uncertainty band (P5–P95 shaded).
    """
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(doses_gy, tcp_mean, linewidth=2.0, label=f"{model_label} (mean)")
    ax.fill_between(doses_gy, tcp_p5, tcp_p95, alpha=0.25, label="90% CI (P5–P95)")
    ax.set_xlabel("Total Dose (Gy)")
    ax.set_ylabel("TCP (probability)")
    ax.set_ylim(0, 1)
    ax.set_title(f"TCP with Parameter Uncertainty — {model_label}")
    ax.legend(fontsize=8)
    plt.tight_layout()
    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_model_comparison_bar(
    patient_ids: list[str],
    tcp_dict: dict[str, np.ndarray],
    output_path: str | pathlib.Path,
    dpi: int = 600,
    max_patients: int = 20,
) -> pathlib.Path:
    """
    Side-by-side bar chart: all models compared per patient.
    """
    ids = patient_ids[:max_patients]
    n = len(ids)
    models = list(tcp_dict.keys())
    x = np.arange(n)
    width = 0.8 / len(models)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.6), 4.5))
    for i, model in enumerate(models):
        vals = np.asarray(tcp_dict[model][:max_patients], dtype=float)
        ax.bar(x + i * width, vals, width, label=model, alpha=0.8)

    ax.set_xticks(x + width * (len(models) - 1) / 2)
    ax.set_xticklabels(ids, rotation=45, ha="right", fontsize=7)
    ax.set_ylabel("TCP (probability)")
    ax.set_ylim(0, 1)
    ax.set_title("TCP Model Comparison (per patient)")
    ax.legend(fontsize=7)
    plt.tight_layout()
    out = pathlib.Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out
