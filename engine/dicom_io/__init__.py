"""DICOM ingestion layer for py_tcpx."""

from dicom_io.dicom_reader import DicomPlanReader
from dicom_io.dvh_extractor import DVHExtractor, DVHResult
from dicom_io.patient_registry import PatientRegistry
from dicom_io.site_detector import (
    detect_site,
    detect_site_from_text,
    params_site_key,
    resolve_pipeline_site,
)
from dicom_io.structure_mapper import canon_target, get_target_structures, normalise_name
from dicom_io.txt_dvh_reader import TxtDVHResult, iter_dvh_text_files, parse_dvh_text_file

__all__ = [
    "DicomPlanReader",
    "DVHExtractor",
    "DVHResult",
    "PatientRegistry",
    "TxtDVHResult",
    "canon_target",
    "detect_site",
    "detect_site_from_text",
    "params_site_key",
    "resolve_pipeline_site",
    "get_target_structures",
    "iter_dvh_text_files",
    "normalise_name",
    "parse_dvh_text_file",
]
