"""dicompyler-core DVH extraction wrapper."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from dicompylercore import dvhcalc
from dicompylercore.dvh import DVH

from dicom_io.structure_mapper import canon_target

logger = logging.getLogger(__name__)

_NAN_METRICS: dict[str, float | None] = {
    "D98_gy": math.nan,
    "D95_gy": math.nan,
    "D90_gy": math.nan,
    "D50_gy": math.nan,
    "D10_gy": math.nan,
    "D5_gy": math.nan,
    "D2_gy": math.nan,
    "D1_gy": math.nan,
    "Dmin_gy": math.nan,
    "Dmean_gy": math.nan,
    "Dmax_gy": math.nan,
    "V5Gy_cc": math.nan,
    "V10Gy_cc": math.nan,
    "V20Gy_cc": math.nan,
    "V30Gy_cc": math.nan,
    "V40Gy_cc": math.nan,
    "V50Gy_cc": math.nan,
    "V60Gy_cc": math.nan,
    "V95pct": math.nan,
    "V100pct": math.nan,
    "V105pct": math.nan,
    "V107pct": math.nan,
    "HI": math.nan,
    "CI": math.nan,
    "GI_pct": math.nan,
    "integral_dose_gy_cm3": math.nan,
    "EQD2_mean": None,
    "BED_mean": None,
}


@dataclass
class DVHResult:
    roi_number: int
    raw_name: str
    canonical_name: str
    category: str
    total_volume_cc: float
    dmin_gy: float
    dmean_gy: float
    dmax_gy: float
    dose_metrics: dict = field(default_factory=dict)
    dvh_object: object | None = None
    extraction_mode: str = "COMPUTED"
    quality_flag: str = "OK"


def _dvh_value(value) -> float:
    if hasattr(value, "value"):
        return float(value.value)
    return float(value)


def _dose_at_volume_percent(cumulative: DVH, volume_percent: float, total_vol: float) -> float:
    """Dose received by at least volume_percent of the structure (Dx metric)."""
    if total_vol <= 0:
        return math.nan
    target = total_vol * volume_percent / 100.0
    counts = np.asarray(cumulative.counts, dtype=float)
    bins = np.asarray(cumulative.bins, dtype=float)
    for idx in range(len(counts) - 1, -1, -1):
        if counts[idx] >= target:
            return float(bins[idx + 1])
    return float(bins[1]) if len(bins) > 1 else math.nan


def _volume_at_least_dose(cumulative: DVH, dose_gy: float) -> float:
    """Absolute volume (cm³) receiving at least dose_gy."""
    counts = np.asarray(cumulative.counts, dtype=float)
    bins = np.asarray(cumulative.bins, dtype=float)
    edge_doses = bins[1:]
    idx = int(np.searchsorted(edge_doses, dose_gy, side="left"))
    idx = max(0, min(idx, len(counts) - 1))
    return float(counts[idx])


def _embedded_dvh_for_roi(rt_dose_ds, roi_number: int) -> DVH | None:
    if not hasattr(rt_dose_ds, "DVHSequence"):
        return None
    for item in rt_dose_ds.DVHSequence:
        refs = getattr(item, "DVHReferencedROISequence", None)
        if not refs:
            continue
        ref = refs[0]
        if int(getattr(ref, "ReferencedROINumber", -1)) == int(roi_number):
            return DVH.from_dicom_dvh(rt_dose_ds, int(roi_number))
    return None


def _tag_dose_gy(item, tag: str) -> float | None:
    if hasattr(item, tag):
        raw = getattr(item, tag)
        if raw is not None:
            return float(raw)
    return None


def _quality_flag(dvh_obj: DVH, total_volume: float) -> str:
    if total_volume == 0:
        return "EMPTY"
    n_bins = len(dvh_obj.counts)
    if n_bins < 10:
        return "LOW_BINS"
    return "OK"


class DVHExtractor:
    """Extract DVHs via dicompyler-core and compute dose metrics."""

    def extract_all_dvhs(
        self,
        rt_dose_ds,
        rt_struct_ds,
        structure_list: list[dict],
    ) -> dict[int, DVHResult]:
        results: dict[int, DVHResult] = {}

        for structure in structure_list:
            roi_number = int(structure["roi_number"])
            raw_name = str(structure["raw_name"])
            mapped = canon_target(raw_name, structure.get("roi_type") or None)

            try:
                dvh_obj: DVH | None = None
                mode = "COMPUTED"
                embedded_item = None

                if hasattr(rt_dose_ds, "DVHSequence"):
                    for item in rt_dose_ds.DVHSequence:
                        refs = getattr(item, "DVHReferencedROISequence", None)
                        if refs and int(refs[0].ReferencedROINumber) == roi_number:
                            embedded_item = item
                            break

                if embedded_item is not None:
                    dvh_obj = DVH.from_dicom_dvh(rt_dose_ds, roi_number)
                    mode = "EMBEDDED"
                else:
                    dvh_obj = dvhcalc.get_dvh(rt_struct_ds, rt_dose_ds, roi_number)

                if dvh_obj.volume_units == "%" and dvh_obj.volume > 0:
                    struct_volume = float(dvh_obj.volume)
                else:
                    struct_volume = float(dvh_obj.volume)

                dmin = _tag_dose_gy(embedded_item, "DVHMinimumDose") if embedded_item else None
                dmean = _tag_dose_gy(embedded_item, "DVHMeanDose") if embedded_item else None
                dmax = _tag_dose_gy(embedded_item, "DVHMaximumDose") if embedded_item else None

                if dmin is None:
                    dmin = float(dvh_obj.min)
                if dmean is None:
                    dmean = float(dvh_obj.mean)
                if dmax is None:
                    dmax = float(dvh_obj.max)

                flag = _quality_flag(dvh_obj, struct_volume)
                results[roi_number] = DVHResult(
                    roi_number=roi_number,
                    raw_name=raw_name,
                    canonical_name=mapped["canonical"],
                    category=mapped["category"],
                    total_volume_cc=struct_volume,
                    dmin_gy=dmin,
                    dmean_gy=dmean,
                    dmax_gy=dmax,
                    dvh_object=dvh_obj,
                    extraction_mode=mode,
                    quality_flag=flag,
                )
            except Exception as exc:
                logger.warning(
                    "DVH extraction failed for ROI %s (%s): %s",
                    roi_number,
                    raw_name,
                    exc,
                )
                results[roi_number] = DVHResult(
                    roi_number=roi_number,
                    raw_name=raw_name,
                    canonical_name=mapped["canonical"],
                    category=mapped["category"],
                    total_volume_cc=0.0,
                    dmin_gy=math.nan,
                    dmean_gy=math.nan,
                    dmax_gy=math.nan,
                    quality_flag="FAILED",
                )

        return results

    def compute_dose_metrics(
        self, dvh_result: DVHResult, prescription_gy: float
    ) -> dict:
        if dvh_result.quality_flag != "OK" or dvh_result.dvh_object is None:
            return dict(_NAN_METRICS)

        dvh_obj: DVH = dvh_result.dvh_object
        cumulative = dvh_obj if dvh_obj.dvh_type == "cumulative" else dvh_obj.cumulative
        if cumulative.dose_units == "%":
            cumulative = cumulative.absolute_dose(prescription_gy)
        total_vol = float(dvh_result.total_volume_cc or cumulative.volume)
        if cumulative.volume_units != "cm3" and total_vol > 0:
            cumulative = cumulative.absolute_volume(total_vol)

        def d_metric(volume_pct: float) -> float:
            return _dose_at_volume_percent(cumulative, volume_pct, total_vol)

        def v_metric(dose_gy: float) -> float:
            return _volume_at_least_dose(cumulative, dose_gy)

        def v_rx_pct(rx_pct: float) -> float:
            dose = prescription_gy * rx_pct / 100.0
            vol = v_metric(dose)
            total = dvh_result.total_volume_cc
            if total <= 0:
                return math.nan
            return 100.0 * vol / total

        d50 = d_metric(50.0)
        d98 = d_metric(98.0)
        d2 = d_metric(2.0)

        is_target = dvh_result.canonical_name in {"GTV", "CTV", "PTV", "ITV", "BOOST"}
        hi = (d2 - d98) / d50 if is_target and d50 > 0 else math.nan
        v100 = v_rx_pct(100.0)
        ci = v100 / 100.0 if is_target and not math.isnan(v100) else math.nan
        gi_pct = (
            100.0 * (d2 - d50) / prescription_gy
            if is_target and prescription_gy > 0 and not math.isnan(d2) and not math.isnan(d50)
            else math.nan
        )
        integral = (
            float(dvh_result.dmean_gy) * float(total_vol)
            if total_vol > 0 and not math.isnan(float(dvh_result.dmean_gy))
            else math.nan
        )

        metrics = {
            "D98_gy": d98,
            "D95_gy": d_metric(95.0),
            "D90_gy": d_metric(90.0),
            "D50_gy": d50,
            "D10_gy": d_metric(10.0),
            "D5_gy": d_metric(5.0),
            "D2_gy": d2,
            "D1_gy": d_metric(1.0),
            "Dmin_gy": float(dvh_result.dmin_gy),
            "Dmean_gy": float(dvh_result.dmean_gy),
            "Dmax_gy": float(dvh_result.dmax_gy),
            "V5Gy_cc": v_metric(5.0),
            "V10Gy_cc": v_metric(10.0),
            "V20Gy_cc": v_metric(20.0),
            "V30Gy_cc": v_metric(30.0),
            "V40Gy_cc": v_metric(40.0),
            "V50Gy_cc": v_metric(50.0),
            "V60Gy_cc": v_metric(60.0),
            "V95pct": v_rx_pct(95.0),
            "V100pct": v100,
            "V105pct": v_rx_pct(105.0),
            "V107pct": v_rx_pct(107.0),
            "HI": hi,
            "CI": ci,
            "GI_pct": gi_pct,
            "integral_dose_gy_cm3": integral,
            "EQD2_mean": None,
            "BED_mean": None,
        }
        return metrics


from dicom_io.dvh_shape_features import compute_dvh_shape_features, extract_3d_dose_array  # noqa: E402,F401
