"""
Commercial TPS DVH text export reader (Eclipse, RayStation, Pinnacle-style).

Parses cumulative or differential DVH tables with dose/volume columns in cGy or Gy.
"""

from __future__ import annotations

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


def _to_gy(value: float) -> float:
    return value / 100.0 if value > 150 else value


def _is_cumulative(vol: np.ndarray) -> bool:
    if len(vol) < 2:
        return True
    return bool(np.all(np.diff(vol) <= 1e-6))


def _cum_to_diff(vol_cum: np.ndarray) -> np.ndarray:
    diff = np.empty_like(vol_cum)
    diff[:-1] = vol_cum[:-1] - vol_cum[1:]
    diff[-1] = vol_cum[-1]
    return np.clip(diff, 0, None)


def _infer_target_type(structure_name: str) -> str:
    canonical = canon_target(structure_name)
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


def parse_dvh_text_file(
    path: Path,
    *,
    default_dose_per_fraction_gy: float = 2.0,
    default_target_type: str | None = None,
) -> TxtDVHResult:
    """Parse one TPS DVH text export into a TxtDVHResult."""
    meta: dict = {}
    dose_vals: list[float] = []
    vol_vals: list[float] = []
    organ_raw = path.stem
    cumulative_hint = True

    text = path.read_text(encoding="utf-8", errors="ignore")
    header_lines: list[str] = []
    for raw in text.splitlines():
        if len(header_lines) < 40 and not re.match(r"^\s*[\d.\-]", raw.lstrip()):
            header_lines.append(raw)
        for key, rx in _HEADER_PATTERNS.items():
            if m := rx.search(raw):
                if key == "mean":
                    meta["mean"] = _to_gy(float(m.group(1)))
                elif key == "tpd":
                    meta["tpd"] = _to_gy(float(m.group(1)))
                elif key == "n_frac":
                    meta["n_frac"] = int(m.group(1))
                elif key == "dpf":
                    meta["dpf"] = _to_gy(float(m.group(1)))
                elif key == "pid":
                    meta["pid"] = m.group(1).strip()
                elif key == "dvh_type":
                    cumulative_hint = "cumulative" in m.group(0).lower()

        if raw.lower().startswith("structure"):
            organ_raw = raw.split(":", 1)[-1].strip()
            continue

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
        raise ValueError(f"No DVH data rows found in {path.name}")

    d_gy = np.asarray(dose_vals, dtype=float)
    if d_gy.max() > 150:
        d_gy = d_gy / 100.0

    v = np.asarray(vol_vals, dtype=float)
    if not cumulative_hint or not _is_cumulative(v):
        v_diff = v
    else:
        v_diff = _cum_to_diff(v)

    if len(d_gy) > 1:
        centres = 0.5 * (d_gy[:-1] + d_gy[1:])
        v_use = v_diff[:-1]
    else:
        centres = d_gy.copy()
        v_use = v_diff.copy()

    v_use = np.clip(v_use, 0, None)
    total = float(v_use.sum())
    if total <= 0:
        raise ValueError(f"Zero differential volume in {path.name}")
    vf = v_use / total

    dvh_df = pd.DataFrame({"dose_gy": centres, "volume_frac": vf})

    rx_gy = float(meta.get("tpd", d_gy.max()))
    if rx_gy <= 0:
        rx_gy = float(d_gy.max())
    dpf = float(meta.get("dpf", default_dose_per_fraction_gy))
    n_frac = int(meta.get("n_frac", max(int(round(rx_gy / dpf)), 1)))

    target = default_target_type or _infer_target_type(organ_raw)
    if target not in ("GTV", "CTV", "PTV"):
        target = "PTV"

    pid = str(meta.get("pid", path.stem))
    plan_meta = {
        "prescription_dose_gy": rx_gy,
        "n_fractions": n_frac,
        "dose_per_fraction_gy": rx_gy / n_frac,
        "plan_label": organ_raw,
    }

    return TxtDVHResult(
        canonical_name=target,
        raw_name=organ_raw,
        quality_flag="OK",
        dmean_gy=float(meta.get("mean", np.sum(centres * vf))),
        total_volume_cc=float(v[0]) if len(v) else float("nan"),
        dvh_object=_TxtDVHProxy(dvh_df, float(v[0]) if len(v) else 1.0),
        patient_id=pid,
        plan_metadata=plan_meta,
        header_text="\n".join(header_lines),
    )


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
    return files
