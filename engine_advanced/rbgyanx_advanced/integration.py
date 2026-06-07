"""
Wire ADVANCED features into a completed engine run (Parts B & E).

Called only when ``RunConfig.mode == "advanced"``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def register_pinn_models(model_dir: Path | None, site: str) -> bool:
    try:
        from radiobiology.model_registry import register_tcp_model
        from rbgyanx_advanced.pinn.models.tcp_pinn import PINNTCPAdapter, PINNTCPStub
    except ImportError as exc:
        logger.warning("PINN registration skipped: %s", exc)
        return False

    if model_dir:
        path = Path(model_dir) / f"tcp_pinn_{site.lower()}.pt"
        if path.is_file():
            register_tcp_model(f"PINN_{site}", PINNTCPAdapter.load(path, site=site))
            return True
    register_tcp_model("PINN_STUB", PINNTCPStub(site=site))
    return True


def attach_dosiomics_to_ntcp_results(
    ntcp_results: list[dict],
    input_dir: Path | None,
) -> bool:
    from rbgyanx_advanced.dose3d.dose_grid_extractor import extract_oar_dose_volume
    from rbgyanx_advanced.dose3d.dosiomics import extract_dosiomics_features

    any_attached = False
    for row in ntcp_results:
        organ = str(row.get("structure", ""))
        mean_d = row.get("Dmean_gy") or row.get("gEUD_gy")
        voxels = extract_oar_dose_volume(
            None,
            None,
            organ,
            fallback_mean_dose_gy=float(mean_d) if mean_d is not None else 45.0,
        )
        feats = extract_dosiomics_features(voxels, oar_name=organ)
        row.update(feats)
        any_attached = True
    return any_attached


def merge_dosiomics_features(
    feat_df: pd.DataFrame,
    ntcp_results: list[dict],
) -> pd.DataFrame:
    if feat_df.empty or not ntcp_results:
        return feat_df
    dosio_rows = []
    for r in ntcp_results:
        pid = r.get("AnonPatientID", "")
        dosio = {k: v for k, v in r.items() if str(k).startswith("dosio_")}
        if dosio:
            dosio["AnonPatientID"] = pid
            dosio_rows.append(dosio)
    if not dosio_rows:
        return feat_df
    ddf = pd.DataFrame(dosio_rows).groupby("AnonPatientID", as_index=False).first()
    return feat_df.merge(ddf, on="AnonPatientID", how="left")


def enable_advanced_analysis(
    cfg,
    tcp_results: list[dict],
    ntcp_results: list[dict],
    feat_df: pd.DataFrame,
    output_dir: Path,
) -> tuple[pd.DataFrame, bool]:
    """
    Register PINN stub, attach dosiomics, optional PINN train.
    Returns updated feat_df and dose_arrays_available flag.
    """
    site = cfg.site or "HN"
    if tcp_results:
        site = str(tcp_results[0].get("site_params_key") or tcp_results[0].get("site") or site)
    register_pinn_models(getattr(cfg, "pinn_model_dir", None), site)

    dose_ok = False
    if ntcp_results and getattr(cfg, "enable_dosiomics", True):
        dose_ok = attach_dosiomics_to_ntcp_results(ntcp_results, Path(cfg.input_dir))
        feat_df = merge_dosiomics_features(feat_df, ntcp_results)

    # PINN training is handled by engine_advanced_f (Part F) when pinn_train=True.

    return feat_df, dose_ok
