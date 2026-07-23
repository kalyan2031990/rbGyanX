"""
Bridge rbGyanX GUI/pipeline to rbgyanx-engine (rbGyanX_cdss).

Phase R2 / rbGyanX 1.0: DICOM + classical TCP/NTCP via engine; legacy code3/code6
for TPS text, FDVH, NTCP ML/SHAP, and code7 integration metrics when required.
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

SITE_REGISTRY_TO_ENGINE: dict[str, str] = {
    "HeadNeck": "HN",
    "Lung": "LUNG",
    "Breast": "BREAST",
    "Brain": "BRAIN",
}

Endpoint = Literal["tcp", "ntcp", "both"]


def get_engine_root() -> Path:
    from rbgyanx.paths import get_engine_root as _resolve

    root = _resolve()
    if root is None:
        raise FileNotFoundError(
            "rbgyanx-engine not found. Install engine_bundle beside rbGyanX or set "
            "RBGYANX_ENGINE_PATH to the rbGyanX_cdss folder."
        )
    return root


def ensure_engine_on_path(engine_root: Path | None = None) -> Path:
    root = (engine_root or get_engine_root()).resolve()
    root_str = str(root)
    if root_str not in sys.path:
        sys.path.insert(0, root_str)
    return root


def is_engine_available(engine_root: Path | None = None) -> bool:
    try:
        if engine_root is not None:
            return (Path(engine_root) / "rbgyanx_engine" / "__init__.py").is_file()
        from rbgyanx.paths import get_engine_root as _resolve

        root = _resolve()
        return root is not None and (root / "rbgyanx_engine" / "__init__.py").is_file()
    except OSError:
        return False


def is_dicom_directory(path: Path) -> bool:
    """True if folder looks like DICOM RT (RTPLAN/RTDOSE/RTSTRUCT or .dcm files)."""
    path = Path(path)
    if not path.is_dir():
        return False
    for pattern in ("*.dcm", "RP*.dcm", "RD*.dcm", "RS*.dcm"):
        if list(path.rglob(pattern)):
            return True
    for name in path.rglob("*"):
        if not name.is_file():
            continue
        try:
            with open(name, "rb") as fh:
                if fh.read(128).find(b"DICM") >= 0:
                    return True
        except OSError:
            continue
    return False


def is_tps_text_directory(path: Path) -> bool:
    path = Path(path)
    if path.is_file():
        return path.suffix.lower() in {".txt", ".csv"}
    if path.is_dir():
        return bool(list(path.glob("*.txt")) or list(path.glob("*.csv")))
    return False


def detect_input_kind(path: Path) -> str:
    if is_dicom_directory(path):
        return "dicom"
    if is_tps_text_directory(path):
        return "dvh_txt"
    return "unknown"


def needs_subprocess_fallback(
    tcp_config: dict[str, Any] | None,
    ntcp_config: dict[str, Any] | None,
) -> bool:
    """
    True when legacy code3/code6 must run instead of rbgyanx-engine alone.

    Engine handles DICOM classical TCP/NTCP, UTCP, QUANTEC, and TCP ML in ADVANCED.
    Legacy is still required for fractional DVH, NTCP ML/SHAP, and code7 P+/CFTC paths.
    """
    tcp_config = tcp_config or {}
    ntcp_config = ntcp_config or {}
    if tcp_config.get("use_fdvh"):
        return True
    if tcp_config.get("ccs_file"):
        return True
    if ntcp_config.get("enable_ml") or ntcp_config.get("enable_shap"):
        return True
    return False


def map_site_override(cancer_site_key: str | None) -> str | None:
    if not cancer_site_key:
        return None
    mapped = SITE_REGISTRY_TO_ENGINE.get(cancer_site_key)
    if mapped is None:
        logger.warning(
            "GUI site key '%s' has no engine mapping in SITE_REGISTRY_TO_ENGINE; "
            "site auto-detection will be used. Add the mapping when YAML params exist.",
            cancer_site_key,
        )
    return mapped


def _safe_copy2(src: Path, dst: Path) -> None:
    """Copy file; skip when src and dst are the same path (avoids WinError 32)."""
    src, dst = Path(src).resolve(), Path(dst).resolve()
    if src == dst:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def publish_engine_outputs(base_dir: Path, engine_out: Path, result: Any) -> None:
    """Copy engine artifacts into rbGyanX expected layout for GUI and code7."""
    base_dir = Path(base_dir)
    engine_out = Path(engine_out)

    site_src = engine_out / "site_detection.csv"
    if site_src.is_file():
        _safe_copy2(site_src, base_dir / "site_detection.csv")

    if result.tcp_benchmark_xlsx and Path(result.tcp_benchmark_xlsx).is_file():
        tcp_dir = base_dir / "tcp_analysis"
        tcp_dir.mkdir(parents=True, exist_ok=True)
        dst = tcp_dir / "tcp_benchmarking.xlsx"
        _safe_copy2(result.tcp_benchmark_xlsx, dst)
        _safe_copy2(result.tcp_benchmark_xlsx, tcp_dir / "tcp_predictions.xlsx")
        _safe_copy2(result.tcp_benchmark_xlsx, base_dir / "tcp_predictions.xlsx")

    ntcp_dir = base_dir / "ntcp_analysis"
    ntcp_dir.mkdir(parents=True, exist_ok=True)

    if result.ntcp_results_csv and Path(result.ntcp_results_csv).is_file():
        _safe_copy2(result.ntcp_results_csv, ntcp_dir / "ntcp_results.csv")
        _safe_copy2(result.ntcp_results_csv, ntcp_dir / "enhanced_ntcp_calculations.csv")
        _safe_copy2(result.ntcp_results_csv, base_dir / "ntcp_results.csv")

    if getattr(result, "ntcp_benchmark_xlsx", None) and Path(result.ntcp_benchmark_xlsx).is_file():
        _safe_copy2(result.ntcp_benchmark_xlsx, ntcp_dir / "ntcp_benchmarking.xlsx")
        _safe_copy2(result.ntcp_benchmark_xlsx, base_dir / "ntcp_benchmarking.xlsx")

    quantec_src = engine_out / "quantec_flags.csv"
    if quantec_src.is_file():
        _safe_copy2(quantec_src, base_dir / "quantec_flags.csv")
        _safe_copy2(quantec_src, ntcp_dir / "quantec_flags.csv")

    plan_dir = base_dir / "plan_quality"
    plan_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "physical_dose_metrics.csv",
        "plan_quality_flags.csv",
        "plan_quality_summary.xlsx",
        "patient_plan_summary.pdf",
    ):
        src = engine_out / name
        if src.is_file():
            _safe_copy2(src, base_dir / name)
            _safe_copy2(src, plan_dir / name)

    for name in ("provenance.json", "qa_report.json"):
        src = engine_out / name
        if src.is_file():
            _safe_copy2(src, base_dir / name)


def run_engine_analysis(
    *,
    input_dir: Path,
    output_dir: Path,
    endpoint: Endpoint,
    mode: str = "basic",
    site_override: str | None = None,
    outcome_csv: Path | None = None,
    enable_ml: bool = False,
    cohort: bool = True,
    engine_root: Path | None = None,
    no_uncertainty: bool | None = None,
) -> tuple[Any, list[str]]:
    """
    Run rbgyanx-engine and publish outputs.

    Returns (EngineResult, log_lines).
    """
    logs: list[str] = []
    root = ensure_engine_on_path(engine_root)

    from rbgyanx_engine import RunConfig, run_analysis

    input_dir = Path(input_dir).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    kind = detect_input_kind(input_dir)
    if kind == "unknown":
        raise ValueError(f"Unrecognised input at {input_dir} (expected DICOM RT or TPS text)")

    if no_uncertainty is None:
        no_uncertainty = mode == "basic"

    cfg = RunConfig(
        endpoint=endpoint,
        input_kind=kind,  # type: ignore[arg-type]
        input_dir=input_dir,
        output_dir=output_dir,
        site=site_override,
        outcome_csv=outcome_csv,
        enable_ml=enable_ml and mode == "advanced",
        mode=mode if mode in ("basic", "advanced") else "basic",  # type: ignore[arg-type]
        cohort=cohort,
        no_uncertainty=no_uncertainty,
        no_ml_augment=True,
        figures=False,
    )

    logs.append(f"[engine] root={root}")
    logs.append(f"[engine] endpoint={endpoint} input={kind} mode={cfg.mode}")
    result = run_analysis(cfg)
    publish_engine_outputs(output_dir, output_dir, result)

    logs.append(
        f"[engine] exit_code={result.exit_code} "
        f"tcp_rows={len(result.tcp_results)} ntcp_rows={len(result.ntcp_results)}"
    )
    if result.site_detection_csv:
        logs.append(f"[engine] site_detection={result.site_detection_csv}")
    if getattr(result, "ntcp_benchmark_xlsx", None):
        logs.append(f"[engine] ntcp_benchmark={result.ntcp_benchmark_xlsx}")
    qpath = output_dir / "quantec_flags.csv"
    if qpath.is_file():
        logs.append(f"[engine] quantec_flags={qpath}")
    pq = output_dir / "plan_quality_summary.xlsx"
    if pq.is_file():
        logs.append(f"[engine] plan_quality={pq}")
    pdf = output_dir / "patient_plan_summary.pdf"
    if pdf.is_file():
        logs.append(f"[engine] patient_pdf={pdf}")
    return result, logs
