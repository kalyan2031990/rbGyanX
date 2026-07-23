"""
Commercial TPS DVH text export reader (Eclipse, RayStation, Pinnacle-style).

Parses cumulative or differential DVH tables with dose/volume columns in cGy or Gy.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from dicom_io.structure_mapper import canon_target

_HEADER_PATTERNS = {
    "pid": re.compile(r"Patient\s+ID\s*[:=]\s*(.+)", re.I),
    "pname": re.compile(r"Patient\s+Name\s*[:=]\s*(.+)", re.I),
    "mean": re.compile(r"Mean\s*dose.*[:=]\s*([\d.]+)", re.I),
    "tpd": re.compile(
        r"(?:Prescribed|Target|Rx).*(?:dose|prescription).*\[?c?Gy\]?\s*[:=]\s*([\d.]+)",
        re.I,
    ),
    "volume": re.compile(r"Volume\s*\[?cm", re.I),
    "n_frac": re.compile(r"(?:Number\s+of\s+)?fractions?\s*[:=]\s*(\d+)", re.I),
    "dpf": re.compile(r"(?:Dose\s+per\s+fraction|DPF).*\[?c?Gy\]?\s*[:=]\s*([\d.]+)", re.I),
    "dvh_type": re.compile(r"cumulative|differential", re.I),
}


# Dose units are taken from the file's own declarations (e.g. "Mean Dose [cGy]:",
# "Dose [Gy]" column header) — never guessed from magnitude. A plan legitimately above
# 150 Gy, or a Gy file with large values, would be mis-scaled 100x by a magnitude rule.
_CGY_RE = re.compile(r"c\s*Gy", re.I)
_GY_RE = re.compile(r"(?<!c)\bGy\b", re.I)

logger = logging.getLogger(__name__)


def _unit_scale(line: str) -> float | None:
    """Multiplier converting this line's dose values to Gy, or None if undeclared."""
    if _CGY_RE.search(line):
        return 0.01
    if _GY_RE.search(line):
        return 1.0
    return None


def _to_gy_legacy(value: float) -> float:
    """Magnitude fallback used ONLY when the file declares no dose unit."""
    return value / 100.0 if value > 150 else value


def _is_cumulative(vol: np.ndarray) -> bool:
    if len(vol) < 2:
        return True
    return bool(np.all(np.diff(vol) <= 1e-6))


def _cum_to_diff(vol_cum: np.ndarray) -> np.ndarray:
    diff = np.empty_like(vol_cum)
    diff[:-1] = vol_cum[:-1] - vol_cum[1:]
    diff[-1] = vol_cum[-1]
    return np.asarray(np.clip(diff, 0, None))


def _infer_target_type(structure_name: str) -> str:
    canonical = canon_target(structure_name)["canonical"]
    if canonical in ("GTV", "CTV", "PTV", "ITV", "BOOST"):
        return "PTV" if canonical in ("ITV", "BOOST") else canonical
    upper = structure_name.upper()
    for token in ("GTV", "CTV", "PTV"):
        if token in upper:
            return token
    return "PTV"


class _TxtDVHProxy:
    """Minimal dicompyler-like differential DVH for dvh_object_to_dataframe."""

    dvh_type = "differential"
    dose_units = "Gy"

    def __init__(self, dvh_df: pd.DataFrame, total_vol: float):
        self._df = dvh_df
        self._total = max(float(total_vol), 1.0)

    @property
    def differential(self):
        return self

    @property
    def counts(self):
        return self._df["volume_frac"].values * self._total

    @property
    def bins(self):
        d = self._df["dose_gy"].values
        w = float(np.median(np.diff(d))) if len(d) > 1 else 0.1
        return np.r_[d[0] - w / 2, d + w / 2]


@dataclass
class TxtDVHResult:
    """DVH result compatible with TCPCalculator."""

    canonical_name: str
    raw_name: str
    quality_flag: str
    dmean_gy: float
    total_volume_cc: float
    dvh_object: _TxtDVHProxy
    patient_id: str
    plan_metadata: dict
    header_text: str = ""


def _parse_dvh_text(
    text: str,
    *,
    source_name: str,
    fallback_name: str,
    default_dose_per_fraction_gy: float = 2.0,
    default_target_type: str | None = None,
    preserve_canonical: bool = False,
) -> TxtDVHResult:
    """Core parser over DVH text. ``preserve_canonical`` keeps the true per-structure
    canonical (Rectum/Bladder/…) instead of coercing everything to a target type."""
    meta: dict = {}
    dose_vals: list[float] = []
    vol_vals: list[float] = []
    organ_raw = fallback_name
    cumulative_hint = True

    header_lines: list[str] = []
    table_scale: float | None = None  # dose-column -> Gy, from the declared column unit
    for raw in text.splitlines():
        if len(header_lines) < 40 and not re.match(r"^\s*[\d.\-]", raw.lstrip()):
            header_lines.append(raw)
        for key, rx in _HEADER_PATTERNS.items():
            if m := rx.search(raw):
                # Each dose-bearing header carries its own unit (e.g. "Mean Dose [cGy]:").
                scale = _unit_scale(raw)
                if key == "mean":
                    val = float(m.group(1))
                    meta["mean"] = val * scale if scale is not None else _to_gy_legacy(val)
                elif key == "tpd":
                    val = float(m.group(1))
                    meta["tpd"] = val * scale if scale is not None else _to_gy_legacy(val)
                elif key == "n_frac":
                    meta["n_frac"] = int(m.group(1))
                elif key == "dpf":
                    val = float(m.group(1))
                    meta["dpf"] = val * scale if scale is not None else _to_gy_legacy(val)
                elif key == "pid":
                    meta["pid"] = m.group(1).strip()
                elif key == "dvh_type":
                    cumulative_hint = "cumulative" in m.group(0).lower()

        if raw.lower().startswith("structure"):
            organ_raw = raw.split(":", 1)[-1].strip()
            continue

        # Dose-table column header, e.g. "Dose [cGy]  Structure Volume [cm3]".
        if (
            table_scale is None
            and re.search(r"\bdose\b", raw, re.I)
            and not raw.lstrip()[:1].isdigit()
        ):
            table_scale = _unit_scale(raw)

        line = raw.lstrip()
        if not line or (line[0] not in "0123456789-"):
            continue
        parts = re.split(r"[,\t\s]+", line.strip())
        if len(parts) < 2:
            continue
        try:
            dose_vals.append(float(parts[0]))
            vol_vals.append(float(parts[-1]))
        except ValueError:
            continue

    if not dose_vals:
        raise ValueError(f"No DVH data rows found in {source_name}")

    d_gy = np.asarray(dose_vals, dtype=float)
    if table_scale is not None:
        d_gy = d_gy * table_scale
    else:
        # No declared unit anywhere: fall back to the magnitude rule, but say so.
        logger.warning(
            "%s: dose unit not declared in header or column label; "
            "falling back to magnitude heuristic (>150 -> cGy). Declare [Gy] or [cGy].",
            source_name,
        )
        if d_gy.max() > 150:
            d_gy = d_gy / 100.0

    v = np.asarray(vol_vals, dtype=float)
    v_diff = v if not cumulative_hint or not _is_cumulative(v) else _cum_to_diff(v)

    if len(d_gy) > 1:
        centres = 0.5 * (d_gy[:-1] + d_gy[1:])
        v_use = v_diff[:-1]
    else:
        centres = d_gy.copy()
        v_use = v_diff.copy()

    v_use = np.clip(v_use, 0, None)
    total = float(v_use.sum())
    if total <= 0:
        raise ValueError(f"Zero differential volume in {source_name}")
    vf = v_use / total

    dvh_df = pd.DataFrame({"dose_gy": centres, "volume_frac": vf})

    rx_gy = float(meta.get("tpd", d_gy.max()))
    if rx_gy <= 0:
        rx_gy = float(d_gy.max())
    dpf = float(meta.get("dpf", default_dose_per_fraction_gy))
    n_frac = int(meta.get("n_frac", max(int(round(rx_gy / dpf)), 1)))

    if preserve_canonical:
        # Keep the ROI's true canonical (Rectum, Bladder, PTV, …) for multi-structure files.
        canonical = default_target_type or canon_target(organ_raw)["canonical"]
    else:
        canonical = default_target_type or _infer_target_type(organ_raw)
        if canonical not in ("GTV", "CTV", "PTV"):
            canonical = "PTV"

    pid = str(meta.get("pid", fallback_name))
    plan_meta = {
        "prescription_dose_gy": rx_gy,
        "n_fractions": n_frac,
        "dose_per_fraction_gy": rx_gy / n_frac,
        "plan_label": organ_raw,
    }

    return TxtDVHResult(
        canonical_name=canonical,
        raw_name=organ_raw,
        quality_flag="OK",
        dmean_gy=float(meta.get("mean", np.sum(centres * vf))),
        total_volume_cc=float(v[0]) if len(v) else float("nan"),
        dvh_object=_TxtDVHProxy(dvh_df, float(v[0]) if len(v) else 1.0),
        patient_id=pid,
        plan_metadata=plan_meta,
        header_text="\n".join(header_lines),
    )


def parse_dvh_text_file(
    path: Path,
    *,
    default_dose_per_fraction_gy: float = 2.0,
    default_target_type: str | None = None,
) -> TxtDVHResult:
    """Parse one single-structure TPS DVH text export into a TxtDVHResult."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _parse_dvh_text(
        text,
        source_name=path.name,
        fallback_name=path.stem,
        default_dose_per_fraction_gy=default_dose_per_fraction_gy,
        default_target_type=default_target_type,
    )


def parse_multi_structure_dvh_text(
    path: Path,
    *,
    default_dose_per_fraction_gy: float = 2.0,
) -> list[TxtDVHResult]:
    """Parse a multi-structure DVH text export (all ROIs in one file, e.g. an Eclipse
    plan-level export) into one TxtDVHResult per structure.

    The file's global preamble (patient id, prescribed dose, fractions) is prepended to
    each per-structure block so shared metadata is preserved. Single-structure files fall
    back to :func:`parse_dvh_text_file`. Degenerate / empty structure blocks are skipped.
    Each result keeps the ROI's true canonical name (Rectum, Bladder, PTV, …).
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    struct_idx = [i for i, ln in enumerate(lines) if ln.strip().lower().startswith("structure:")]
    if len(struct_idx) <= 1:
        return [
            parse_dvh_text_file(path, default_dose_per_fraction_gy=default_dose_per_fraction_gy)
        ]

    preamble = lines[: struct_idx[0]]
    results: list[TxtDVHResult] = []
    for k, start in enumerate(struct_idx):
        end = struct_idx[k + 1] if k + 1 < len(struct_idx) else len(lines)
        struct_name = lines[start].split(":", 1)[-1].strip() or f"Structure_{k+1}"
        block_text = "\n".join(preamble + lines[start:end])
        try:
            results.append(
                _parse_dvh_text(
                    block_text,
                    source_name=f"{path.name}::{struct_name}",
                    fallback_name=struct_name,
                    default_dose_per_fraction_gy=default_dose_per_fraction_gy,
                    preserve_canonical=True,
                )
            )
        except ValueError:
            continue  # empty / zero-volume structure block — skip, don't fail the file
    return results


def iter_dvh_text_files(
    directory: Path,
    glob_pattern: str = "*.txt",
) -> list[Path]:
    """Return sorted DVH text files under directory matching glob."""
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"DVH directory not found: {directory}")
    files = sorted(directory.glob(glob_pattern))
    if not files and glob_pattern.lower() == "*.txt":
        files = sorted(directory.glob("*.TXT"))
    if not files:
        raise FileNotFoundError(
            f"No DVH files matching {glob_pattern!r} in {directory} "
            f"(found {len(list(directory.iterdir()))} other entries); "
            "check --dvh-dir and --dvh-glob"
        )
    return files
