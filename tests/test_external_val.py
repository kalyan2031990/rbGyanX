"""External validation pipeline tests (synthetic — no real HNSCC data)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from validation.hnscc_external_val import (
    DISCLAIMER,
    build_external_validation_report,
    run_hnscc_external_validation,
)


def test_disclaimer_present_in_report():
    summary = pd.DataFrame([{"patient_id": "P1", "prescription_dose_gy": 70, "n_oars": 3}])
    report = build_external_validation_report(summary, None)
    assert "NOT an NTCP-toxicity validation" in report["disclaimer"]
    assert DISCLAIMER in report["disclaimer"]


def test_no_outcome_basic_report(tmp_path: Path):
    with __import__("unittest.mock").mock.patch(
        "dicom_io.tcia_hnscc_adapter.adapt_hnscc_cohort",
        return_value=([], pd.DataFrame()),
    ):
        report = run_hnscc_external_validation(tmp_path, None, tmp_path / "out", mode="basic")
    assert "disclaimer" in report
    assert (tmp_path / "out" / "external_validation_report.json").is_file()
