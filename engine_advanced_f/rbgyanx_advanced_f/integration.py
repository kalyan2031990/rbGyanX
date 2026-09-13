"""Wire Part F (Bayesian NTCP + PINN training) into ADVANCED engine runs."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from rbgyanx_advanced_f.bayesian.ntcp_bayesian import (
    fit_lkb_bayesian,
    load_posterior,
    propagate_ntcp_uncertainty_bayesian,
    save_posterior,
)

logger = logging.getLogger(__name__)

_ORGAN_PRIORS: dict[str, tuple[float, float]] = {
    "parotid": (28.0, 0.18),
    "lung": (24.0, 0.28),
    "spinal cord": (45.0, 0.12),
}


def _merge_ntcp_outcomes(ntcp_results: list[dict], outcome_csv: Path) -> pd.DataFrame:
    df = pd.DataFrame(
        [{k: v for k, v in r.items() if not str(k).startswith("_")} for r in ntcp_results]
    )
    if df.empty:
        return df
    out = pd.read_csv(outcome_csv)
    id_col = next(
        (c for c in out.columns if c.lower() in ("anonpatientid", "patientid", "id")),
        None,
    )
    if id_col and id_col != "AnonPatientID":
        out = out.rename(columns={id_col: "AnonPatientID"})
    if "ntcp_outcome" not in out.columns:
        for alt in ("Toxicity", "Observed_Toxicity", "toxicity", "ntcp"):
            if alt in out.columns:
                out = out.rename(columns={alt: "ntcp_outcome"})
                break
    if "ntcp_outcome" not in out.columns:
        return pd.DataFrame()
    return df.merge(
        out[["AnonPatientID", "ntcp_outcome"]].drop_duplicates("AnonPatientID"),
        on="AnonPatientID",
        how="inner",
    )


def run_bayesian_ntcp(
    cfg,
    ntcp_results: list[dict],
    output_dir: Path,
) -> pd.DataFrame | None:
    if not getattr(cfg, "enable_bayesian_ntcp", False):
        return None
    if not ntcp_results:
        return None

    trace_dir = Path(
        getattr(cfg, "bayesian_ntcp_trace_dir", None) or output_dir / "bayesian_traces"
    )
    trace_dir.mkdir(parents=True, exist_ok=True)

    prefit_dir = getattr(cfg, "bayesian_ntcp_trace_dir", None)
    summary_rows: list[dict] = []

    if cfg.outcome_csv:
        merged = _merge_ntcp_outcomes(ntcp_results, Path(cfg.outcome_csv))
        if merged.empty or "gEUD_gy" not in merged.columns:
            logger.warning("Bayesian NTCP: no merged gEUD/outcome rows.")
        else:
            for organ, grp in merged.groupby("structure"):
                geud = grp["gEUD_gy"].astype(float).values
                y = grp["ntcp_outcome"].astype(float).values
                if len(grp) < 10 or np.unique(y).size < 2:
                    continue
                prior = _ORGAN_PRIORS.get(str(organ).lower(), (50.0, 0.15))
                post = fit_lkb_bayesian(
                    geud,
                    y,
                    str(organ),
                    prior_td50_mean=prior[0],
                    prior_m_mean=prior[1],
                    n_samples=getattr(cfg, "bayesian_n_samples", 500),
                    n_tune=getattr(cfg, "bayesian_n_tune", 500),
                    prefer_pymc=False,
                )
                save_posterior(post, trace_dir / f"{organ.replace(' ', '_')}.npz")
                summary_rows.append(post.summary_dict())
                for r in ntcp_results:
                    if str(r.get("structure")) != str(organ):
                        continue
                    geud_v = r.get("gEUD_gy")
                    if geud_v is None:
                        continue
                    unc = propagate_ntcp_uncertainty_bayesian(float(geud_v), post)
                    r.update({f"bayesian_{k}": v for k, v in unc.items()})
                    r["bayesian_td50_mean"] = post.td50_mean
                    r["bayesian_m_mean"] = post.m_mean

    elif prefit_dir and Path(prefit_dir).is_dir():
        for r in ntcp_results:
            organ = str(r.get("structure", ""))
            path = Path(prefit_dir) / f"{organ.replace(' ', '_')}.npz"
            post = load_posterior(path)
            if post is None or r.get("gEUD_gy") is None:
                continue
            unc = propagate_ntcp_uncertainty_bayesian(float(r["gEUD_gy"]), post)
            r.update({f"bayesian_{k}": v for k, v in unc.items()})

    if not summary_rows:
        return None
    summary_df = pd.DataFrame(summary_rows)
    out_csv = output_dir / "bayesian_ntcp_summary.csv"
    summary_df.to_csv(out_csv, index=False)
    logger.info("Bayesian NTCP summary: %s", out_csv)
    return summary_df


def run_pinn_training(cfg, feat_df: pd.DataFrame, output_dir: Path, site: str) -> Path | None:
    if not getattr(cfg, "pinn_train", False):
        return None

    model_dir = Path(getattr(cfg, "pinn_model_dir", None) or output_dir / "pinn_models")
    from rbgyanx_advanced_f.pinn.train_pinn import train_pinn, train_pinn_from_df

    epochs = getattr(cfg, "pinn_epochs", 200)
    lam_p = getattr(cfg, "pinn_lambda_physics", 1.0)
    lam_b = getattr(cfg, "pinn_lambda_boundary", 0.5)

    if not feat_df.empty and (
        "tcp_outcome" in feat_df.columns or "LocalControl" in feat_df.columns
    ):
        _, _ = train_pinn_from_df(
            feat_df,
            site,
            model_dir,
            epochs=epochs,
            lambda_physics=lam_p,
            lambda_boundary=lam_b,
            min_patients=20,
        )
    elif cfg.outcome_csv and getattr(cfg, "cohort_features_csv", None):
        _, _ = train_pinn(
            Path(cfg.cohort_features_csv),
            Path(cfg.outcome_csv),
            site,
            model_dir,
            epochs=epochs,
            lambda_physics=lam_p,
            lambda_boundary=lam_b,
        )
    elif cfg.outcome_csv:
        feat_csv = output_dir / "cohort_features.csv"
        if feat_csv.is_file():
            _, _ = train_pinn(
                feat_csv,
                Path(cfg.outcome_csv),
                site,
                model_dir,
                epochs=epochs,
                lambda_physics=lam_p,
                lambda_boundary=lam_b,
            )
        else:
            logger.warning("PINN train: cohort_features.csv missing.")
            return None
    else:
        return None

    ckpt = model_dir / f"tcp_pinn_{site.lower()}.pt"
    if ckpt.is_file():
        try:
            from rbgyanx_advanced.integration import register_pinn_models

            register_pinn_models(model_dir, site)
        except Exception as exc:
            logger.warning("PINN registry update failed: %s", exc)
        return ckpt
    return None


def enable_part_f_analysis(
    cfg,
    tcp_results: list[dict],
    ntcp_results: list[dict],
    feat_df: pd.DataFrame,
    output_dir: Path,
) -> tuple[pd.DataFrame, dict]:
    """
    Bayesian NTCP fits and/or PINN training (ADVANCED only).
    Returns updated feat_df and metadata dict.
    """
    meta: dict = {}
    site = cfg.site or "HN"
    if tcp_results:
        site = str(tcp_results[0].get("site_params_key") or tcp_results[0].get("site") or site)

    if getattr(cfg, "enable_bayesian_ntcp", False):
        summary = run_bayesian_ntcp(cfg, ntcp_results, output_dir)
        if summary is not None:
            meta["bayesian_summary_csv"] = str(output_dir / "bayesian_ntcp_summary.csv")

    if getattr(cfg, "pinn_train", False):
        if not feat_df.empty and "tcp_outcome" not in feat_df.columns and "LocalControl" in feat_df.columns:
            feat_df = feat_df.rename(columns={"LocalControl": "tcp_outcome"})
        ckpt = run_pinn_training(cfg, feat_df, output_dir, site)
        if ckpt:
            meta["pinn_checkpoint"] = str(ckpt)

    return feat_df, meta
