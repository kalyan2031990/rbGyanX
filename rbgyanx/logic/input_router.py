"""
Unified input routing for rbGyanX Step 1 and validation.

Auto-detects DICOM RT vs TPS DVH exports and runs the appropriate ingest path.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

LogFn = Callable[[str], None]

DVH_SUFFIXES = {".txt", ".csv", ".dcm"}


def discover_dvh_files(input_path: Path, *, recursive: bool = True) -> List[Path]:
    """Find DVH candidate files under a path (flat or recursive)."""
    input_path = Path(input_path)
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in DVH_SUFFIXES else []

    patterns = ("*.txt", "*.csv", "*.dcm", "*.TXT")
    files: List[Path] = []
    if recursive:
        for pattern in patterns:
            files.extend(input_path.rglob(pattern))
    else:
        for pattern in patterns:
            files.extend(input_path.glob(pattern))

    # De-duplicate; prefer shallower paths when same name
    seen: set[str] = set()
    unique: List[Path] = []
    for p in sorted(files, key=lambda x: (len(x.parts), str(x).lower())):
        key = str(p.resolve()).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return unique


def resolve_input_kind(
    path: Path,
    source_pref: str = "auto",
) -> str:
    """
    Return 'dicom', 'dvh_txt', or 'unknown'.

    source_pref: 'auto' | 'dicom' | 'tps_txt'
    """
    path = Path(path)
    if not path.exists():
        return "unknown"

    try:
        from rbgyanx.logic.engine_bridge import detect_input_kind, is_dicom_directory
    except ImportError:
        is_dicom_directory = None
        detect_input_kind = None

    if source_pref == "dicom":
        if path.is_dir() and is_dicom_directory and is_dicom_directory(path):
            return "dicom"
        if path.is_file() and path.suffix.lower() == ".dcm":
            return "dicom"
        return "unknown"

    if source_pref == "tps_txt":
        if path.is_file() and path.suffix.lower() in {".txt", ".csv"}:
            return "dvh_txt"
        if path.is_dir() and discover_dvh_files(path, recursive=True):
            txts = [f for f in discover_dvh_files(path) if f.suffix.lower() in {".txt", ".csv"}]
            if txts:
                return "dvh_txt"
        return "unknown"

    # auto
    if detect_input_kind:
        kind = detect_input_kind(path)
        if kind in ("dicom", "dvh_txt"):
            return kind

    if path.is_file():
        if path.suffix.lower() == ".dcm":
            return "dicom"
        if path.suffix.lower() in {".txt", ".csv"}:
            return "dvh_txt"

    if path.is_dir():
        dvh_files = discover_dvh_files(path)
        txt_csv = [f for f in dvh_files if f.suffix.lower() in {".txt", ".csv"}]
        dcm_only = [f for f in dvh_files if f.suffix.lower() == ".dcm"]
        if is_dicom_directory and is_dicom_directory(path):
            if txt_csv and len(txt_csv) >= len(dcm_only):
                return "dvh_txt"
            return "dicom"
        if txt_csv:
            return "dvh_txt"
    return "unknown"


def sync_source_pref_from_path(path: Path, current: str = "auto") -> str:
    """Map detected kind to GUI input_source value ('dicom' | 'tps_txt')."""
    if current in ("dicom", "tps_txt"):
        kind = resolve_input_kind(path, current)
    else:
        kind = resolve_input_kind(path, "auto")
    if kind == "dicom":
        return "dicom"
    if kind == "dvh_txt":
        return "tps_txt"
    return current if current in ("dicom", "tps_txt") else "tps_txt"


def run_dicom_step1_placeholder(
    input_path: Path,
    output_dir: Path,
    log: Optional[LogFn] = None,
) -> Dict:
    """
    Step 1 for DICOM: no TPS DVH conversion; engine runs at Step 3.

    Writes ingest_manifest.json so downstream steps know input kind.
    """
    _log = log or logger.info
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dcm_files: List[str] = []
    if input_path.is_dir():
        for p in discover_dvh_files(input_path, recursive=True):
            if p.suffix.lower() == ".dcm":
                dcm_files.append(p.name)
    elif input_path.suffix.lower() == ".dcm":
        dcm_files.append(input_path.name)

    manifest = {
        "input_kind": "dicom",
        "input_path": str(input_path),
        "dicom_files": dcm_files[:50],
        "dicom_file_count": len(dcm_files),
        "message": "DICOM RT ingest - classical TCP/NTCP via rbgyanx-engine at Step 3",
    }
    manifest_path = output_dir / "ingest_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    _log(f"[OK] DICOM ingest: {len(dcm_files)} .dcm file(s) detected")
    _log("[OK] Step 1 complete (engine path - skip TPS DVH preprocessing)")

    return {
        "total_files": len(dcm_files) or 1,
        "processed": len(dcm_files) or 1,
        "failed": 0,
        "duplicates_skipped": 0,
        "excluded": 0,
        "patients": set(),
        "structures": {},
        "formats": {"DICOM_RT": len(dcm_files) or 1},
        "errors": [],
        "warnings": [],
        "input_kind": "dicom",
        "ingest_manifest": str(manifest_path),
    }


def run_step1_ingest(
    input_path: Path,
    output_dir: Path,
    *,
    source_pref: str = "auto",
    log: Optional[LogFn] = None,
) -> Dict:
    """Route Step 1 to DICOM placeholder or TPS intelligent preprocessing."""
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    kind = resolve_input_kind(input_path, source_pref)

    if kind == "dicom":
        return run_dicom_step1_placeholder(input_path, output_dir, log=log)

    if kind == "dvh_txt":
        from utils.dvh_parser import preprocess_dvh_intelligent

        files = discover_dvh_files(input_path)
        summary = preprocess_dvh_intelligent(input_path, output_dir, file_list=files)
        summary["input_kind"] = "dvh_txt"
        return summary

    raise ValueError(
        f"Unrecognised input at {input_path}. "
        "Expected DICOM RT folder (RTPLAN/RTDOSE/RTSTRUCT) or TPS .txt/.csv DVH exports."
    )


def validate_input_for_mode(
    path: Path,
    *,
    basic_mode: bool,
    source_pref: str = "auto",
) -> Tuple[bool, List[str]]:
    """Validation messages for GUI (empty list = OK)."""
    path = Path(path)
    errors: List[str] = []
    if not path.exists():
        errors.append(f"Input path does not exist: {path}")
        return False, errors

    kind = resolve_input_kind(path, source_pref)
    if kind == "unknown":
        errors.append(
            f"Could not detect input type at {path}\n"
            "Use a DICOM RT folder or a directory of TPS DVH .txt/.csv files."
        )
        return False, errors

    if basic_mode and kind == "dvh_txt":
        # Phase 2: BASIC allows TPS when explicitly selected or auto-detected TPS-only folder
        pass  # allowed

    if path.is_dir() and kind == "dvh_txt":
        files = discover_dvh_files(path)
        txt_csv = [f for f in files if f.suffix.lower() in {".txt", ".csv"}]
        if not txt_csv:
            errors.append(f"No TPS .txt/.csv DVH files found under {path}")

    return len(errors) == 0, errors
