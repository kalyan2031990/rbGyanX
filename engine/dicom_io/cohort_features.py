"""
Real-data feature front-end: (RTSTRUCT, RTDOSE[, RTPLAN]) -> one tidy feature row.

Produces the per-patient features the external-validation benchmark consumes
(``cohort_features.csv``): a single prescription-PTV target metric block, a fixed
dysphagia-OAR metric block, DVH-shape dosiomics, and BED/EQD2 from fractionation,
all with provenance columns. Reuses the validated radiobiology numerics; this module
only *assembles* features (no new dose–response math).

Parsing rules (per docs/EXTVAL_DATA_READINESS.md):
- prefer the pure OAR contour over ``-PTV`` planning-subtraction volumes;
- pick a single prescription PTV (PTV70 / PTVHighOPT) and one plan-sum RTDOSE.

NaN contract: degenerate / empty / zero-volume ROIs yield NaN metrics, never 0.0.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import pandas as pd

from dicom_io.dvh_extractor import DVHExtractor, DVHResult
from dicom_io.structure_mapper import get_oar_structures, get_target_structures
from radiobiology import dvh_object_to_dataframe
from radiobiology.bdvh import compute_eqd2_dvh, get_alpha_beta_for_organ
from radiobiology.geud_tcp import compute_geud
from radiobiology.lq_model import bed, eqd2

try:  # plan metadata is optional (RTPLAN may be absent)
    from dicom_io.dicom_reader import DicomPlanReader
except Exception:  # pragma: no cover - reader import is environment-dependent
    DicomPlanReader = None  # type: ignore[assignment]

from dicom_io.dvh_shape_features import compute_dvh_shape_features

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OARSpec:
    """One organ-at-risk to assemble features for (site-agnostic).

    ``aliases`` are normalised raw-name substrings (lowercased, spaces/underscores
    stripped) used to select the ROI directly by name — independent of any dataset.
    ``a_exp`` is the gEUD volume exponent (parallel-like OARs use a≈1 ≈ mean dose;
    serial OARs such as cord use a large a).
    """

    canonical: str
    a_exp: float
    aliases: tuple[str, ...]


# Default OAR set: head & neck dysphagia organs. The mapper leaves several of these
# unmapped (e.g. ``PharynxConst``, ``Parotids``), so we select them directly by name
# with the Phase-0 parsing rules: skip ``-PTV`` planning-subtraction volumes; prefer
# the pure organ over a PRV expansion (``SpinalCord_05``).
DEFAULT_OAR_SPECS: tuple[OARSpec, ...] = (
    OARSpec("PharynxConstrictor", 1.0, ("pharynxconst", "pharconst", "constrictor")),
    OARSpec("Larynx", 1.0, ("larynx",)),
    OARSpec("OralCavity", 1.0, ("oralcavity", "ocavity", "oralcav")),
    OARSpec("Parotids", 1.0, ("parotids", "parotid")),
    OARSpec("Submandibular", 1.0, ("submandibular", "submand")),
    OARSpec("SpinalCord", 12.0, ("spinalcord",)),
)

# Example alternative set: prostate/pelvic OARs (SPARK-style centre naming varies, so
# ``Rectum``/``Rectum_P`` both normalise here). Illustrates that the feature front-end
# is site-agnostic — pass any OARSpec sequence to ``build_*_features(oar_specs=...)``.
PROSTATE_OAR_SPECS: tuple[OARSpec, ...] = (
    OARSpec("Rectum", 1.0, ("rectum", "rectump", "rectal", "anorectum")),
    OARSpec("Bladder", 1.0, ("bladder", "bladderwall")),
    OARSpec("FemoralHead_L", 4.0, ("femoralheadl", "femurl", "femoralhead_l", "caputfeml")),
    OARSpec("FemoralHead_R", 4.0, ("femoralheadr", "femurr", "femoralhead_r", "caputfemr")),
    OARSpec("Urethra", 8.0, ("urethra",)),
)

# Backward-compatible views of the default HN set (kept for older imports).
DYSPHAGIA_OARS: dict[str, float] = {s.canonical: s.a_exp for s in DEFAULT_OAR_SPECS}
DYSPHAGIA_ALIASES: dict[str, tuple[str, ...]] = {s.canonical: s.aliases for s in DEFAULT_OAR_SPECS}

_PRV_SUFFIX = re.compile(r"_\d+$")  # SpinalCord_05, BrainStem_03 = planning-risk volumes

PTV_GEUD_A = -10.0  # tumour gEUD exponent (Niemierko); emphasises cold spots
PTV_ALPHA_BETA = 10.0  # Gy, tumour
_PTV_NAME_PRIORITY = ("PTV70", "PTVHIGHOPT", "PTVHIGH", "PTV_HIGH", "PTV66", "PTV_TOTAL")


def _norm(name: str) -> str:
    return name.lower().replace(" ", "").replace("_", "")


def _select_oars(rt_struct_ds: Any, specs: Sequence[OARSpec]) -> dict[str, dict]:
    """Pick one ROI per OAR canonical by name (pure organ, not -PTV / not PRV)."""
    rois = [
        {"roi_number": int(r.ROINumber), "raw_name": str(r.ROIName)}
        for r in getattr(rt_struct_ds, "StructureSetROISequence", [])
    ]
    type_by_num = {
        int(o.ReferencedROINumber): str(getattr(o, "RTROIInterpretedType", "") or "")
        for o in getattr(rt_struct_ds, "RTROIObservationsSequence", [])
    }
    selected: dict[str, dict] = {}
    for spec in specs:
        canonical, patterns = spec.canonical, spec.aliases
        cands = [
            r
            for r in rois
            if "-ptv" not in r["raw_name"].lower().replace(" ", "")
            and any(p in _norm(r["raw_name"]) for p in patterns)
        ]
        if not cands:
            continue
        # Prefer the base organ (no PRV numeric suffix), then the shortest name.
        cands.sort(
            key=lambda r: (
                1 if _PRV_SUFFIX.search(r["raw_name"].replace(" ", "")) else 0,
                len(r["raw_name"]),
            )
        )
        chosen = cands[0]
        selected[canonical] = {**chosen, "roi_type": type_by_num.get(chosen["roi_number"], "ORGAN")}
    return selected


@dataclass
class PatientFeatureRow:
    values: dict[str, Any]


def _differential_df(dvh_result: DVHResult) -> pd.DataFrame | None:
    if dvh_result.dvh_object is None or dvh_result.quality_flag not in {"OK", "LOW_BINS"}:
        return None
    df = dvh_object_to_dataframe(dvh_result.dvh_object)
    return df if df is not None and not df.empty else None


def _select_prescription_ptv(targets: list[dict]) -> dict | None:
    """Choose one prescription PTV: name priority, else first PTV-canonical."""
    ptvs = [t for t in targets if t.get("canonical") == "PTV"]
    if not ptvs:
        ptvs = [t for t in targets if str(t.get("canonical", "")).startswith("PTV")]
    if not ptvs:
        return None
    for token in _PTV_NAME_PRIORITY:
        for t in ptvs:
            if token in str(t.get("raw_name", "")).upper().replace(" ", ""):
                return t
    return ptvs[0]


def _ptv_block(
    extractor: DVHExtractor,
    dvh_result: DVHResult,
    prescription_gy: float,
    n_fractions: int,
) -> dict[str, Any]:
    metrics = extractor.compute_dose_metrics(dvh_result, prescription_gy=prescription_gy)
    diff = _differential_df(dvh_result)
    geud = compute_geud(diff, PTV_GEUD_A) if diff is not None else math.nan
    # Source Dmean from metrics so the NaN-not-zero contract holds for degenerate ROIs.
    dmean = float(metrics["Dmean_gy"])

    bed_gy = math.nan
    eqd2_gy = math.nan
    if n_fractions and n_fractions > 0 and not math.isnan(dmean):
        dpf = dmean / n_fractions
        bed_gy = bed(dmean, dpf, PTV_ALPHA_BETA)
        eqd2_gy = eqd2(dmean, dpf, PTV_ALPHA_BETA)

    shape = compute_dvh_shape_features(diff, dvh_result.canonical_name) if diff is not None else {}
    out = {
        "PTV_name": dvh_result.raw_name,
        "PTV_volume_cc": dvh_result.total_volume_cc if dvh_result.total_volume_cc > 0 else math.nan,
        "PTV_D95_gy": metrics["D95_gy"],
        "PTV_D2_gy": metrics["D2_gy"],
        "PTV_D98_gy": metrics["D98_gy"],
        "PTV_Dmean_gy": dmean,
        "PTV_gEUD_gy": geud,
        "PTV_HI": metrics["HI"],
        "PTV_CI": metrics["CI"],
        "PTV_BED_gy": bed_gy,
        "PTV_EQD2_gy": eqd2_gy,
        "PTV_dose_skewness": shape.get("dose_skewness", math.nan),
        "PTV_dose_kurtosis": shape.get("dose_kurtosis", math.nan),
        "PTV_dose_std_gy": shape.get("dose_std_gy", math.nan),
    }
    return out


def _oar_block(
    extractor: DVHExtractor,
    dvh_by_canonical: dict[str, DVHResult],
    n_fractions: int,
    specs: Sequence[OARSpec],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for spec in specs:
        canonical, a_exp = spec.canonical, spec.a_exp
        prefix = f"{canonical}_"
        res = dvh_by_canonical.get(canonical)
        if res is None:
            out[prefix + "Dmean_gy"] = math.nan
            out[prefix + "Dmax_gy"] = math.nan
            out[prefix + "gEUD_gy"] = math.nan
            out[prefix + "EQD2mean_gy"] = math.nan
            out[prefix + "V30Gy_cc"] = math.nan
            out[prefix + "V50Gy_cc"] = math.nan
            continue
        metrics = extractor.compute_dose_metrics(res, prescription_gy=70.0)
        diff = _differential_df(res)
        geud = compute_geud(diff, a_exp) if diff is not None else math.nan
        eqd2_mean = math.nan
        if diff is not None and n_fractions and n_fractions > 0:
            ab = get_alpha_beta_for_organ(canonical)
            eqd2_df = compute_eqd2_dvh(diff, n_fractions, ab)
            if eqd2_df is not None and not eqd2_df.empty:
                eqd2_mean = float((eqd2_df["dose_gy"] * eqd2_df["volume_frac"]).sum())
        out[prefix + "Dmean_gy"] = float(metrics["Dmean_gy"])
        out[prefix + "Dmax_gy"] = float(metrics["Dmax_gy"])
        out[prefix + "gEUD_gy"] = geud
        out[prefix + "EQD2mean_gy"] = eqd2_mean
        out[prefix + "V30Gy_cc"] = metrics["V30Gy_cc"]
        out[prefix + "V50Gy_cc"] = metrics["V50Gy_cc"]
    return out


def _plan_metadata(rt_plan_ds: Any) -> dict[str, Any]:
    if rt_plan_ds is None or DicomPlanReader is None:
        return {"prescription_dose_gy": math.nan, "n_fractions": 0, "approval_status": ""}
    try:
        meta = DicomPlanReader().extract_plan_metadata(rt_plan_ds)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("plan metadata extraction failed: %s", exc)
        return {"prescription_dose_gy": math.nan, "n_fractions": 0, "approval_status": ""}
    return {
        "prescription_dose_gy": meta.get("prescription_dose_gy") or math.nan,
        "n_fractions": int(meta.get("n_fractions") or 0),
        "approval_status": str(getattr(rt_plan_ds, "ApprovalStatus", "") or ""),
    }


def build_patient_features(
    rt_struct_ds: Any,
    rt_dose_ds: Any,
    rt_plan_ds: Any = None,
    *,
    patient_id: str = "",
    oar_specs: Sequence[OARSpec] | None = None,
) -> dict[str, Any]:
    """Assemble one tidy feature row from a DICOM-RT triple (datasets in memory).

    ``oar_specs`` selects which organs-at-risk to assemble feature blocks for; it
    defaults to the head & neck dysphagia set (:data:`DEFAULT_OAR_SPECS`). Pass a
    different sequence (e.g. :data:`PROSTATE_OAR_SPECS`) to run on any site.
    """
    specs = tuple(oar_specs) if oar_specs is not None else DEFAULT_OAR_SPECS
    meta = _plan_metadata(rt_plan_ds)
    rx_known = bool(meta["prescription_dose_gy"]) and not math.isnan(
        float(meta["prescription_dose_gy"])
    )
    prescription_gy = float(meta["prescription_dose_gy"]) if rx_known else math.nan
    # Dose used to normalise relative target metrics (D-as-%-of-Rx); fall back to 70 Gy.
    rx_for_metrics = prescription_gy if (rx_known and prescription_gy > 0) else 70.0
    n_fractions = int(meta["n_fractions"] or 0)

    extractor = DVHExtractor()
    targets = get_target_structures(rt_struct_ds, {})
    oars = get_oar_structures(rt_struct_ds)

    row: dict[str, Any] = {
        "patient_id": patient_id,
        "prescription_dose_gy": prescription_gy,
        "n_fractions": n_fractions if n_fractions > 0 else math.nan,
        "approval_status": meta["approval_status"],
        "dose_summation_type": str(getattr(rt_dose_ds, "DoseSummationType", "") or ""),
        "n_targets": len(targets),
        "n_oars_mapped": len(oars),
    }

    # PTV block
    ptv = _select_prescription_ptv(targets)
    if ptv is not None:
        ptv_results = extractor.extract_all_dvhs(
            rt_dose_ds,
            rt_struct_ds,
            [
                {
                    "roi_number": ptv["roi_number"],
                    "raw_name": ptv["raw_name"],
                    "roi_type": ptv.get("roi_type"),
                }
            ],
        )
        ptv_res = next(iter(ptv_results.values()))
        row.update(_ptv_block(extractor, ptv_res, rx_for_metrics, n_fractions))
    else:
        row.update(_empty_ptv_block())

    # OAR block — select organs by name (pure organ, not -PTV / not PRV).
    selected = _select_oars(rt_struct_ds, specs)
    oar_struct_list = [
        {"roi_number": d["roi_number"], "raw_name": d["raw_name"], "roi_type": d.get("roi_type")}
        for d in selected.values()
    ]
    oar_results = (
        extractor.extract_all_dvhs(rt_dose_ds, rt_struct_ds, oar_struct_list)
        if oar_struct_list
        else {}
    )
    res_by_num = {dr.roi_number: dr for dr in oar_results.values()}
    dvh_by_canonical: dict[str, DVHResult] = {
        canon: res_by_num[d["roi_number"]]
        for canon, d in selected.items()
        if d["roi_number"] in res_by_num
    }
    row.update(_oar_block(extractor, dvh_by_canonical, n_fractions, specs))
    return row


def _empty_ptv_block() -> dict[str, Any]:
    keys = (
        "PTV_name",
        "PTV_volume_cc",
        "PTV_D95_gy",
        "PTV_D2_gy",
        "PTV_D98_gy",
        "PTV_Dmean_gy",
        "PTV_gEUD_gy",
        "PTV_HI",
        "PTV_CI",
        "PTV_BED_gy",
        "PTV_EQD2_gy",
        "PTV_dose_skewness",
        "PTV_dose_kurtosis",
        "PTV_dose_std_gy",
    )
    out: dict[str, Any] = {k: math.nan for k in keys}
    out["PTV_name"] = ""
    return out


def build_cohort_features(
    patient_triples: list[tuple[str, Any, Any, Any]],
    *,
    oar_specs: Sequence[OARSpec] | None = None,
) -> pd.DataFrame:
    """
    Build the tidy cohort feature table.

    ``patient_triples`` is a list of ``(patient_id, rt_struct_ds, rt_dose_ds, rt_plan_ds)``.
    ``oar_specs`` picks the OAR set (defaults to head & neck; see
    :func:`build_patient_features`). Returns one row per patient; columns are the
    union of feature keys.
    """
    rows = []
    for pid, rs, rd, rp in patient_triples:
        try:
            rows.append(build_patient_features(rs, rd, rp, patient_id=pid, oar_specs=oar_specs))
        except Exception as exc:
            logger.warning("feature build failed for %s: %s", pid, exc)
            rows.append({"patient_id": pid, "build_error": str(exc)})
    return pd.DataFrame(rows)
