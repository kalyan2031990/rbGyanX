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


# Head-Neck-PET-CT (Vallières) outcome workbook: 4 centre sheets + an "Excluded" sheet.
_OUTCOME_SHEETS_SKIP = {"excluded"}
_OUTCOME_COLS = {
    "patient_id": ["patient#", "patientid", "patient"],
    "sex": ["sex", "gender"],
    "age": ["age"],
    "primary_site": ["primarysite"],
    "t_stage": ["tstage"],
    "n_stage": ["nstage"],
    "m_stage": ["mstage"],
    "stage_group": ["tnmgroupstage", "stagegroup"],
    "hpv_status": ["hpvstatus", "hpv"],
    "locoregional": ["locoregional"],
    "distant": ["distant"],
    "death": ["death"],
}


def _coerce_event(series: pd.Series) -> pd.Series:
    """Map outcome cells to {0,1} (NaN preserved); accepts 0/1 or yes/no text."""

    def one(v: object) -> float:
        if pd.isna(v):
            return float("nan")
        s = str(v).strip().lower()
        if s in {"1", "yes", "y", "true", "positive", "pos"}:
            return 1.0
        if s in {"0", "no", "n", "false", "negative", "neg"}:
            return 0.0
        try:
            return 1.0 if float(s) != 0 else 0.0
        except ValueError:
            return float("nan")

    return series.map(one)


def load_hnscc_outcomes(xlsx_path: Path | str) -> pd.DataFrame:
    """
    Load Head-Neck-PET-CT outcomes across all centre sheets into one tidy table.

    Returns one row per patient with ``patient_id``, ``centre`` and canonical
    covariate/endpoint columns. Loco-regional recurrence and death are coerced to
    {0,1} event indicators (NaN if missing). The "Excluded" sheet is skipped.
    """
    path = Path(xlsx_path)
    xl = pd.ExcelFile(path, engine="openpyxl")
    frames: list[pd.DataFrame] = []
    for sheet in xl.sheet_names:
        if sheet.strip().lower() in _OUTCOME_SHEETS_SKIP:
            continue
        raw = xl.parse(sheet)
        norm_lookup = {_norm_col(c): c for c in raw.columns}
        tidy = pd.DataFrame()
        tidy["centre"] = [sheet] * len(raw)
        for canonical, aliases in _OUTCOME_COLS.items():
            src = next((norm_lookup[a] for a in aliases if a in norm_lookup), None)
            tidy[canonical] = raw[src] if src is not None else float("nan")
        frames.append(tidy)

    out = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if not out.empty:
        out["patient_id"] = out["patient_id"].astype(str).str.strip()
        for ev in ("locoregional", "distant", "death"):
            out[ev] = _coerce_event(out[ev])
        out = out[out["patient_id"].str.startswith("HN-")].reset_index(drop=True)
    logger.info("HNSCC outcomes: %d patients across %d sheets", len(out), len(frames))
    return out
