"""Physical dose metrics and plan-quality index collection (DICOM)."""

from __future__ import annotations

import logging
from pathlib import Path

from config.plan_quality import (
    get_site_pack,
    infer_technique_profile,
    physical_oar_canonicals,
    resolve_pack_site_key,
)
from config.site_ntcp_params import allowed_oar_names
from dicom_io.dicom_reader import DicomPlanReader
from dicom_io.dvh_extractor import DVHExtractor
from dicom_io.site_detector import detect_site, resolve_pipeline_site
from dicom_io.structure_mapper import TARGET_CANONICALS, get_oar_structures, get_target_structures
from rbgyanx_engine.pipeline import (
    _attach_site_metadata,
    _structures_for_site_detection,
    iter_dicom_patient_jobs,
)

logger = logging.getLogger(__name__)


def collect_dicom_physical_metrics(
    dicom_dir: Path,
    site_override: str | None,
    anon_id: str,
    user_config: Path | None = None,
    user_ntcp_config: Path | None = None,
    patient_id: str | None = None,
) -> list[dict]:
    """Extract physical dose metrics for targets and site OARs (one patient folder)."""
    reader = DicomPlanReader()
    dicom = reader.load_patient_dicom(dicom_dir, patient_id=patient_id)
    meta = reader.extract_plan_metadata(dicom["rt_plan"])
    detection = detect_site(meta, _structures_for_site_detection(dicom["rt_struct"], meta))
    params_key, site_info = resolve_pipeline_site(site_override, detection)
    technique_profile = infer_technique_profile(meta)
    pack_key, _pack = get_site_pack(params_key, technique_profile, user_config)
    index_pack = resolve_pack_site_key(params_key, technique_profile)

    targets = get_target_structures(dicom["rt_struct"], meta)
    ntcp_allowed = allowed_oar_names(params_key, user_ntcp_config)
    oar_allowed = physical_oar_canonicals(
        params_key, technique_profile, ntcp_allowed, user_config
    )
    oars = get_oar_structures(dicom["rt_struct"], allowed_canonicals=oar_allowed)

    struct_list = targets + oars
    if not struct_list:
        logger.warning("Patient %s: no structures for physical metrics", anon_id)
        return []

    dvh_map = DVHExtractor().extract_all_dvhs(
        dicom["rt_dose"], dicom["rt_struct"], struct_list
    )
    rx = float(meta.get("prescription_dose_gy") or meta.get("prescription_gy") or 0.0)
    extractor = DVHExtractor()
    rows: list[dict] = []

    for dvh_r in dvh_map.values():
        if dvh_r.quality_flag == "FAILED":
            continue
        metrics = extractor.compute_dose_metrics(dvh_r, rx if rx > 0 else float(dvh_r.dmax_gy or 60.0))
        role = (
            "TARGET"
            if dvh_r.canonical_name in TARGET_CANONICALS
            else "OAR"
            if dvh_r.category == "OAR"
            else "OTHER"
        )
        if role == "OTHER":
            continue
        row = {
            "AnonPatientID": anon_id,
            "site": params_key,
            "site_params_key": params_key,
            "technique_profile": technique_profile,
            "index_pack": index_pack,
            "site_pack": pack_key,
            "structure": dvh_r.canonical_name,
            "raw_structure_name": dvh_r.raw_name,
            "structure_role": role,
            "total_volume_cc": dvh_r.total_volume_cc,
            "prescription_gy": rx,
            "dose_per_fraction_gy": meta.get("dose_per_fraction_gy"),
            "number_of_fractions": meta.get("number_of_fractions"),
            "dvh_quality": dvh_r.quality_flag,
            "dvh_mode": dvh_r.extraction_mode,
            **metrics,
        }
        _attach_site_metadata(row, site_info)
        rows.append(row)
    return rows


def collect_cohort_physical_metrics(
    input_dir: Path,
    site_override: str | None,
    cohort: bool,
    user_config: Path | None = None,
    user_ntcp_config: Path | None = None,
) -> list[dict]:
    """Collect physical metrics for all patients under a DICOM root."""
    jobs = list(iter_dicom_patient_jobs(Path(input_dir).resolve()))
    if not cohort and len(jobs) == 1:
        jobs = jobs[:1]
    all_rows: list[dict] = []
    for anon_id, folder, pid_filter in jobs:
        try:
            all_rows.extend(
                collect_dicom_physical_metrics(
                    folder,
                    site_override,
                    anon_id,
                    user_config=user_config,
                    user_ntcp_config=user_ntcp_config,
                    patient_id=pid_filter,
                )
            )
        except Exception as exc:
            logger.warning("Physical metrics skipped for %s: %s", anon_id, exc)
    return all_rows
