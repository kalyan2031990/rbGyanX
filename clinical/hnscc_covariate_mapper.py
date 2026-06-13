"""Map TCIA HNSCC clinical spreadsheet columns to canonical covariate schema."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Column aliases observed in Head-Neck-CT-Atlas clinical XLSX (normalised lowercase)
HNSCC_COLUMN_MAP = {
    "patient_id": ["patientid", "patient_id", "anonpatientid", "subjectid", "id"],
    "age": ["age", "age_at_rt", "ageyears"],
    "sex": ["sex", "gender"],
    "t_stage": ["tstage", "t_stage", "t"],
    "n_stage": ["nstage", "n_stage", "n"],
    "m_stage": ["mstage", "m_stage", "m"],
    "site": ["site", "primarysite", "tumorsite", "diagnosis"],
    "smoking": ["smoking", "smokingstatus", "tobacco"],
    "recurrence": ["recurrence", "recurrence_event", "local_recurrence"],
    "survival": ["survival", "os", "overall_survival", "vitalstatus"],
    "survival_months": ["survivalmonths", "os_months", "months_followup"],
}


def _norm_col(c: str) -> str:
    return "".join(ch for ch in str(c).lower() if ch.isalnum())


def map_hnscc_clinical(xlsx_path: Path | str) -> pd.DataFrame:
    """
    Read HNSCC clinical workbook and map to canonical covariates.

    Missing/unmapped columns are NaN and listed in ``_mapping_log`` attribute.
    """
    path = Path(xlsx_path)
    raw = pd.read_excel(path, sheet_name=0, engine="openpyxl")
    norm_lookup = {_norm_col(c): c for c in raw.columns}
    out = pd.DataFrame()
    log: list[str] = []

    for canonical, aliases in HNSCC_COLUMN_MAP.items():
        src = None
        for alias in aliases:
            if alias in norm_lookup:
                src = norm_lookup[alias]
                break
        if src is None:
            out[canonical] = float("nan")
            log.append(f"missing:{canonical}")
        else:
            out[canonical] = raw[src]

    out.attrs["mapping_log"] = log
    out.attrs["source_file"] = str(path)
    logger.info("HNSCC clinical map: %d rows, missing fields: %s", len(out), log)
    return out
