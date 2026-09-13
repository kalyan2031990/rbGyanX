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


def find_rt_files(input_dir: Path | None) -> tuple[Path | None, Path | None]:
    """Locate the RTDOSE and RTSTRUCT in a staged single-patient input directory.

    The cohort runner stages exactly one RTPLAN/RTDOSE/RTSTRUCT per patient, so a modality scan is
    sufficient and avoids a dependency on the engine's discovery layer. Returns ``(None, None)``
    when either is absent - which is a legitimate answer, not a failure to paper over.
    """
    if not input_dir:
        return None, None
    try:
        import pydicom
    except ImportError:
        return None, None
    root = Path(input_dir)
    if not root.is_dir():
        return None, None
    rtdose: Path | None = None
    rtstruct: Path | None = None
    for path in sorted(root.rglob("*.dcm")):
        try:
            modality = str(pydicom.dcmread(str(path), stop_before_pixels=True).Modality)
        except Exception:
            continue
        if modality == "RTDOSE" and rtdose is None:
            rtdose = path
        elif modality == "RTSTRUCT" and rtstruct is None:
            rtstruct = path
        if rtdose and rtstruct:
            break
    return rtdose, rtstruct


def attach_dosiomics_to_ntcp_results(
    ntcp_results: list[dict],
    input_dir: Path | None,
) -> bool:
    """Attach first-order dosiomics computed from the patient's REAL RTDOSE grid.

    Production pathway: real dose only. This function used to call the extractor with
    ``(None, None, organ, fallback_mean_dose_gy=...)``, which meant every ADVANCED run silently
    populated ``dosio_*`` columns from generated voxels. Those surrogates were retracted. Now, when
    no real grid resolves, the row is marked NOT_AVAILABLE and no ``dosio_*`` feature is written.

    Returns True only if at least one ROI yielded real RTDOSE-derived features.
    """
    from rbgyanx_advanced.dose3d.dose_grid_extractor import (
        SOURCE_NOT_AVAILABLE,
        SOURCE_REAL_RTDOSE,
        extract_oar_dose_volume_with_source,
    )
    from rbgyanx_advanced.dose3d.dosiomics import extract_dosiomics_features

    rtdose_path, rtstruct_path = find_rt_files(input_dir)
    if not (rtdose_path and rtstruct_path):
        logger.warning(
            "dosiomics: no RTDOSE+RTSTRUCT pair found under %s - dosiomics NOT_AVAILABLE for this "
            "patient. No synthetic substitute is generated.",
            input_dir,
        )

    any_real = False
    for row in ntcp_results:
        organ = str(row.get("structure", ""))
        voxels, source = extract_oar_dose_volume_with_source(
            rtdose_path,
            rtstruct_path,
            organ,
            allow_synthetic=False,  # production: never
        )
        if source != SOURCE_REAL_RTDOSE or voxels is None:
            row["dosiomics_status"] = SOURCE_NOT_AVAILABLE
            row["dosiomics_source"] = source
            continue
        feats = extract_dosiomics_features(
            voxels, oar_name=organ, dose_source=source, production=True
        )
        row.update(feats)
        row["dosiomics_status"] = "OK"
        row["dosiomics_source"] = source
        any_real = True
    return any_real


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
