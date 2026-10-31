"""External validation harness: the software pipeline against outcome endpoints.

Runs the four-tier harness and the MCD/CCS consistency check on an independent dataset the
caller supplies. Nothing in the computation is specific to a particular collection.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from validation.cohort_consistency import compute_mcd_ccs
from validation.four_tier_harness import run_four_tier_harness

logger = logging.getLogger(__name__)

#: Read this before quoting a figure this harness produces. The distinction it makes is the
#: substantive one: validating against recurrence or survival says nothing about whether an NTCP
#: model predicts toxicity, because they are different endpoints.
DISCLAIMER = (
    "This external validation evaluates the rbGyanX software pipeline and its TCP/covariate "
    "models against the outcome endpoint supplied with the dataset. Where that endpoint is "
    "recurrence or survival, the result is NOT an NTCP-toxicity validation: a dataset carrying "
    "recurrence or survival does not carry xerostomia or dysphagia outcomes, and an NTCP model's "
    "performance cannot be inferred from it. No clinical-deployment claims are made."
)


def build_external_validation_report(
    cohort_summary: pd.DataFrame,
    clinical: pd.DataFrame | None,
    tier_results: dict | None = None,
    ccs_result: dict | None = None,
) -> dict[str, Any]:
    """Assemble report sections with mandatory honesty disclaimer."""
    report: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "disclaimer": DISCLAIMER,
        "cohort_description": {
            "n_patients_imaging": int(len(cohort_summary)),
            "modality_completeness": cohort_summary.to_dict(orient="records"),
        },
        "quantec_summary": {},
        "index_distributions": {},
        "benchmarking": {},
        "ccs": ccs_result or {},
    }
    if clinical is not None and not clinical.empty:
        report["cohort_description"]["n_clinical_rows"] = int(len(clinical))
        if "recurrence" in clinical.columns:
            report["cohort_description"]["n_recurrence_events"] = int(
                pd.to_numeric(clinical["recurrence"], errors="coerce").fillna(0).sum()
            )
    if tier_results:
        report["benchmarking"] = {
            k: {
                "apparent_auc": getattr(v, "apparent_auc", None),
                "cv_auc": getattr(v, "cv_auc", None),
                "refused": getattr(v, "refused", False),
            }
            for k, v in tier_results.items()
        }
    return report


def _read_clinical_workbook(xlsx_path: Path) -> pd.DataFrame:
    """Read a clinical workbook as it stands, normalising only the column names.

    The default when no ``clinical_mapper`` is supplied. It makes no assumption about which
    columns exist: whatever the sheet carries is what the harness sees, so a caller whose
    workbook already uses the expected names needs no mapper at all.
    """
    frame = pd.read_excel(xlsx_path)
    frame.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_") for c in frame.columns
    ]
    return frame


def run_external_validation(
    data_root: Path,
    clinical_xlsx: Path | None = None,
    output_dir: Path | None = None,
    mode: str = "basic",
    clinical_mapper: Callable[[Path], pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """
    Run BASIC (+ optional ADVANCED) external validation on adapted HNSCC cohort.
    """
    from dicom_io.dicom_cohort_adapter import adapt_dicom_cohort

    output_dir = output_dir or data_root / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    records, summary = adapt_dicom_cohort(data_root)
    clinical = None
    if clinical_xlsx and Path(clinical_xlsx).is_file():
        # The column map that used to live here described one public collection's workbook, which
        # is a dataset binding rather than a format, so it was removed in v1.5.0. Pass
        # ``clinical_mapper`` to adapt your own workbook; without one the sheet is read as it
        # stands, with column names normalised to lower case and underscores.
        clinical = (clinical_mapper or _read_clinical_workbook)(Path(clinical_xlsx))

    tier_results = None
    ccs_result = None
    if mode == "advanced" and clinical is not None and len(summary) >= 10:
        y = pd.to_numeric(clinical.get("recurrence", pd.Series(dtype=float)), errors="coerce")
        if y.notna().sum() >= 5:
            p_classical = np.full(len(y), 0.5)  # placeholder until engine NTCP join
            tier_results = run_four_tier_harness(
                y.fillna(0).astype(int).values,
                p_classical,
                clinical.get("patient_id", pd.Series(range(len(y)))).astype(str).values,
                clinical_features=clinical[["age"]].fillna(clinical["age"].median())
                if "age" in clinical.columns
                else None,
            )
        feat = summary[["prescription_dose_gy", "n_oars"]].fillna(0).values
        if len(feat) >= 5:
            ccs_result = compute_mcd_ccs(feat)

    report = build_external_validation_report(summary, clinical, tier_results, ccs_result)
    out_json = output_dir / "external_validation_report.json"
    out_md = output_dir / "EXTERNAL_VALIDATION_REPORT.md"
    out_json.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    out_md.write_text(
        f"# External validation report\n\n{DISCLAIMER}\n\n"
        f"See `{out_json.name}` for full JSON.\n",
        encoding="utf-8",
    )
    logger.info("Wrote %s", out_json)
    return report
