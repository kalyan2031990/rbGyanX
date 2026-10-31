"""Deprecated: use :mod:`dicom_io.dicom_cohort_adapter`.

The module was named for one public collection; what it does -- read a directory of DICOM-RT
studies, one subdirectory per patient -- is general, so it was renamed in v1.5.0. This shim
re-exports the new names and will be removed in the release after next.
"""

from __future__ import annotations

import warnings

from dicom_io.dicom_cohort_adapter import (  # noqa: F401
    DicomPatientRecord,
    adapt_dicom_cohort,
    adapt_patient_folder,
)

warnings.warn(
    "dicom_io.tcia_hnscc_adapter is deprecated; use dicom_io.dicom_cohort_adapter. "
    "HNSCCPatientRecord is now DicomPatientRecord and adapt_hnscc_cohort is now "
    "adapt_dicom_cohort.",
    DeprecationWarning,
    stacklevel=2,
)

#: Former names, kept so existing imports and ``unittest.mock.patch`` targets keep working.
HNSCCPatientRecord = DicomPatientRecord
adapt_hnscc_cohort = adapt_dicom_cohort

__all__ = [
    "DicomPatientRecord",
    "HNSCCPatientRecord",
    "adapt_dicom_cohort",
    "adapt_hnscc_cohort",
    "adapt_patient_folder",
]
