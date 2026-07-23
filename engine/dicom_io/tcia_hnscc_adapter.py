"""Ingest TCIA Head-Neck-CT-Atlas DICOM into rbGyanX canonical patient records."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from dicom_io.dicom_reader import DicomPlanReader
from dicom_io.dvh_extractor import DVHExtractor
from dicom_io.structure_mapper import get_oar_structures, normalize_to_tg263

logger = logging.getLogger(__name__)


@dataclass
class HNSCCPatientRecord:
    patient_id: str
    plan_meta: dict
    dvh_by_tg263: dict[str, Any]
    structures: list[dict]
    skipped: bool = False
    skip_reason: str = ""
    unmapped_structures: list[str] = field(default_factory=list)


def _patient_roots(data_root: Path) -> list[Path]:
    """Discover per-patient folders (NBIA retriever layout or nested studies)."""
    raw = data_root / "_raw"
    search = raw if raw.is_dir() and any(raw.iterdir()) else data_root
    roots: list[Path] = []
    for child in sorted(search.iterdir()):
        if not child.is_dir():
            continue
        if any(child.rglob("*.dcm")):
            roots.append(child)
    if not roots and any(data_root.rglob("*.dcm")):
        roots.append(data_root)
    return roots


def adapt_patient_folder(folder: Path, reader: DicomPlanReader | None = None) -> HNSCCPatientRecord:
    """Build one canonical record from a patient DICOM folder."""
    reader = reader or DicomPlanReader()
    try:
        bundle = reader.load_patient_dicom(folder)
    except FileNotFoundError as exc:
        return HNSCCPatientRecord(
            patient_id=folder.name,
            plan_meta={},
            dvh_by_tg263={},
            structures=[],
            skipped=True,
            skip_reason=str(exc),
        )

    plan_meta = reader.extract_plan_metadata(bundle["rt_plan"])
    oars = get_oar_structures(bundle["rt_struct"])
    extractor = DVHExtractor()
    dvh_results = extractor.extract_all_dvhs(
        bundle["rt_dose"], bundle["rt_struct"], oars
    )

    dvh_by_tg263: dict[str, Any] = {}
    unmapped: list[str] = []
    for res in dvh_results.values():
        tg = normalize_to_tg263(res.raw_name)
        key = tg["tg263"]
        if not tg["mapped"]:
            unmapped.append(res.raw_name)
        dvh_by_tg263[key] = {
            "dmean_gy": res.dmean_gy,
            "dmax_gy": res.dmax_gy,
            "dmin_gy": res.dmin_gy,
            "volume_cc": res.total_volume_cc,
            "quality_flag": res.quality_flag,
            "canonical_name": res.canonical_name,
            "tg263": key,
        }

    return HNSCCPatientRecord(
        patient_id=str(bundle["patient_id"]),
        plan_meta=plan_meta,
        dvh_by_tg263=dvh_by_tg263,
        structures=oars,
        unmapped_structures=unmapped,
    )


def adapt_hnscc_cohort(data_root: Path | str) -> tuple[list[HNSCCPatientRecord], pd.DataFrame]:
    """Adapt all patients under external_validation/data/hnscc/."""
    root = Path(data_root)
    records: list[HNSCCPatientRecord] = []
    for pdir in _patient_roots(root):
        rec = adapt_patient_folder(pdir)
        if rec.skipped:
            logger.warning("Skipped %s: %s", pdir.name, rec.skip_reason)
        records.append(rec)

    rows = []
    for r in records:
        if r.skipped:
            continue
        row = {
            "patient_id": r.patient_id,
            "prescription_dose_gy": r.plan_meta.get("prescription_dose_gy"),
            "n_fractions": r.plan_meta.get("n_fractions"),
            "n_oars": len(r.dvh_by_tg263),
            "unmapped_count": len(r.unmapped_structures),
        }
        rows.append(row)
    summary = pd.DataFrame(rows)
    return records, summary
