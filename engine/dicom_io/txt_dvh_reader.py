"""
Commercial TPS DVH text export reader (Eclipse, RayStation, Pinnacle-style).

Parses cumulative or differential DVH tables with dose/volume columns in cGy or Gy.
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from dicom_io.dvh_integrity import validate_cumulative_dvh
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


#: Reasons a TPS text export cannot support a TCP calculation (defects #4 and #5).
RX_MISSING = "RX_MISSING"
FRACTIONATION_MISSING = "FRACTIONATION_MISSING"


def _parse_dvh_text(
    text: str,
    *,
    source_name: str,
    fallback_name: str,
    default_dose_per_fraction_gy: float | None = None,
    default_target_type: str | None = None,
    preserve_canonical: bool = False,
    rx_gy: float | None = None,
    n_frac: int | None = None,
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
    is_cumulative = cumulative_hint and _is_cumulative(v)
    if is_cumulative:
        # Validate the cumulative curve and canonicalise to ascending dose. Raises on an inverted
        # or scrambled curve rather than silently accepting it. For an already-ascending valid
        # curve this is a no-op, so derived metrics are unchanged. (This reader is not on the
        # published DICOM validation path, so this cannot affect the paper's numbers.)
        d_gy, v = validate_cumulative_dvh(d_gy, v, structure=organ_raw)
        v_diff = _cum_to_diff(v)
    else:
        v_diff = v

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

    # Defects #4 and #5. The prescription used to fall back to the DVH maximum and the dose per
    # fraction to a flat 2.0 Gy, both silently (a logged warning beside a written number is not a
    # refusal). A DVH maximum is not a prescription: on a hot plan it overstates the dose the TCP
    # model is given, and on a cold one it understates it, and 2 Gy/fraction is simply a guess
    # about someone else's clinic. Neither is invented now. The caller may state them
    # (``--rx-gy`` / ``--n-frac``); otherwise TCP is refused and NTCP still runs on physical dose.
    tcp_refusal_reasons: list[str] = []

    rx_parsed = "tpd" in meta and float(meta["tpd"]) > 0
    if rx_parsed:
        rx_value = float(meta["tpd"])
        total_dose_source = "parsed"
    elif rx_gy is not None and float(rx_gy) > 0:
        rx_value = float(rx_gy)
        total_dose_source = "caller"
    else:
        rx_value = math.nan
        total_dose_source = "missing"
        tcp_refusal_reasons.append(RX_MISSING)

    nfrac_parsed = "n_frac" in meta and int(meta["n_frac"]) > 0
    dpf_parsed = "dpf" in meta and float(meta["dpf"]) > 0
    if nfrac_parsed:
        n_frac_value = int(meta["n_frac"])
        n_fractions_source = "parsed"
    elif n_frac is not None and int(n_frac) > 0:
        n_frac_value = int(n_frac)
        n_fractions_source = "caller"
    elif dpf_parsed and math.isfinite(rx_value):
        n_frac_value = max(int(round(rx_value / float(meta["dpf"]))), 1)
        n_fractions_source = "derived"
    elif default_dose_per_fraction_gy is not None and math.isfinite(rx_value):
        # an explicit caller-supplied dose per fraction, not a hidden constant
        n_frac_value = max(int(round(rx_value / float(default_dose_per_fraction_gy))), 1)
        n_fractions_source = "caller"
    else:
        n_frac_value = 0
        n_fractions_source = "missing"
        tcp_refusal_reasons.append(FRACTIONATION_MISSING)

    if dpf_parsed:
        dpf = float(meta["dpf"])
        dose_per_fraction_source = "parsed"
    elif math.isfinite(rx_value) and n_frac_value > 0:
        dpf = rx_value / n_frac_value
        dose_per_fraction_source = "derived"
    else:
        dpf = math.nan
        dose_per_fraction_source = "missing"

    if tcp_refusal_reasons:
        logger.warning(
            "%s: %s. TCP is refused for this export; NTCP still runs on physical dose. Supply "
            "--rx-gy and --n-frac to compute TCP.",
            source_name,
            " and ".join(tcp_refusal_reasons),
        )

    if preserve_canonical:
        # Keep the ROI's true canonical (Rectum, Bladder, PTV, …) for multi-structure files.
        canonical = default_target_type or canon_target(organ_raw)["canonical"]
    else:
        canonical = default_target_type or _infer_target_type(organ_raw)
        if canonical not in ("GTV", "CTV", "PTV"):
            canonical = "PTV"

    pid = str(meta.get("pid", fallback_name))
    plan_meta = {
        "prescription_dose_gy": rx_value,
        "n_fractions": n_frac_value,
        "dose_per_fraction_gy": dpf,
        "total_dose_source": total_dose_source,
        "n_fractions_source": n_fractions_source,
        "dose_per_fraction_source": dose_per_fraction_source,
        "tcp_refusal_reasons": tcp_refusal_reasons,
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
    default_dose_per_fraction_gy: float | None = None,
    default_target_type: str | None = None,
    preserve_canonical: bool = False,
    rx_gy: float | None = None,
    n_frac: int | None = None,
) -> TxtDVHResult:
    """Parse one single-structure TPS DVH text export into a TxtDVHResult.

    ``preserve_canonical=False`` (default, unchanged legacy behaviour) coerces the structure to a
    target type (GTV/CTV/PTV), which is correct for target-only DVH exports but means an OAR export
    (e.g. a single ``Parotid`` file) is treated as a PTV and can never match an NTCP organ.
    Pass ``preserve_canonical=True`` for OAR-bearing exports to keep the ROI's true canonical name
    (Parotid_R, Rectum, Bladder, …) so classical NTCP can be applied.
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    return _parse_dvh_text(
        text,
        source_name=path.name,
        fallback_name=path.stem,
        default_dose_per_fraction_gy=default_dose_per_fraction_gy,
        default_target_type=default_target_type,
        preserve_canonical=preserve_canonical,
        rx_gy=rx_gy,
        n_frac=n_frac,
    )


def parse_multi_structure_dvh_text(
    path: Path,
    *,
    default_dose_per_fraction_gy: float | None = None,
    preserve_canonical: bool = True,
    rx_gy: float | None = None,
    n_frac: int | None = None,
) -> list[TxtDVHResult]:
    """Parse a multi-structure DVH text export (all ROIs in one file, e.g. an Eclipse
    plan-level export) into one TxtDVHResult per structure.

    The file's global preamble (patient id, prescribed dose, fractions) is prepended to
    each per-structure block so shared metadata is preserved. Single-structure files fall
    back to :func:`parse_dvh_text_file`. Degenerate / empty structure blocks are skipped.

    ``preserve_canonical`` controls only whether each block keeps the ROI's true canonical name
    (Rectum, Bladder, PTV, …) or is coerced to a target type (GTV/CTV/PTV) — the same distinction
    :func:`parse_dvh_text_file` makes for a single structure. It does NOT control whether multiple
    ROIs are kept separate: every structure block in the file always becomes its own
    :class:`TxtDVHResult`, regardless of this flag. (Before this fix, the caller in
    ``rbgyanx_engine.pipeline._read_txt_structures`` routed ``preserve_canonical=False`` requests
    to :func:`parse_dvh_text_file` directly on the whole multi-structure file instead of through
    here — that single-structure reader has no per-block boundary reset, so it silently accumulated
    every structure's rows together and returned only the last block's name over the merged data.
    A real cohort had 6 ROIs per file (PTV, CTV, Bladder, Rectum, Urethra, Urethra_PRV); 5 were
    discarded and the survivor's DVH was contaminated by rows from the others. See
    docs/KNOWN_LIMITATIONS.md.)
    """
    text = path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    struct_idx = [i for i, ln in enumerate(lines) if ln.strip().lower().startswith("structure:")]
    if len(struct_idx) <= 1:
        # Single-ROI file: parse_dvh_text_file is safe here (no second boundary for it to miss).
        return [
            parse_dvh_text_file(
                path,
                default_dose_per_fraction_gy=default_dose_per_fraction_gy,
                preserve_canonical=preserve_canonical,
                rx_gy=rx_gy,
                n_frac=n_frac,
            )
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
                    preserve_canonical=preserve_canonical,
                    rx_gy=rx_gy,
                    n_frac=n_frac,
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
