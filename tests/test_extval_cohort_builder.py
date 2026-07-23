"""
Tests for the external-validation cohort builder (CI-safe, no real data).

Exercises plan-sum dose selection, the multi-sheet outcomes loader, and the
zip -> feature-row pipeline using the synthetic DICOM-RT factory.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pandas as pd
import pytest
from clinical.hnscc_covariate_mapper import load_hnscc_outcomes
from external_validation.build_cohort_features import (
    _select_plan_sum_dose,
    build_cohort_csv,
)

from tests.synthetic.dicom_rt_factory import build_rt_triple, save_dataset


def _stack_ok() -> bool:
    from dicom_io.dvh_extractor import DVHExtractor

    rs, rd, _ = build_rt_triple()
    res = DVHExtractor().extract_all_dvhs(
        rd, rs, [{"roi_number": 1, "raw_name": "PTV70", "roi_type": "PTV"}]
    )
    return next(iter(res.values())).quality_flag == "OK"


pytestmark = pytest.mark.skipif(
    not _stack_ok(), reason="DICOM stack not functional (needs pydicom<3.0)"
)


def test_select_plan_sum_prefers_plan_over_beam():
    _, rd_plan, _ = build_rt_triple()
    _, rd_beam, _ = build_rt_triple()
    rd_beam.DoseSummationType = "BEAM"
    chosen = _select_plan_sum_dose([rd_beam, rd_plan])
    assert str(chosen.DoseSummationType).upper() == "PLAN"
    # Falls back to whatever exists when no PLAN dose is present.
    assert _select_plan_sum_dose([rd_beam]) is rd_beam
    assert _select_plan_sum_dose([]) is None


def test_load_hnscc_outcomes_multisheet_and_coercion(tmp_path: Path):
    xlsx = tmp_path / "outcomes.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        pd.DataFrame(
            {
                "Patient #": ["HN-HGJ-001", "HN-HGJ-002"],
                "Age": [60, 71],
                "Locoregional": [1, 0],
                "Death": ["Yes", "No"],
                "HPV status": ["positive", None],
            }
        ).to_excel(xw, sheet_name="HGJ", index=False)
        pd.DataFrame({"Patient #": ["HN-XXX-999"], "Death": [1]}).to_excel(
            xw, sheet_name="Excluded", index=False
        )

    out = load_hnscc_outcomes(xlsx)
    assert len(out) == 2  # Excluded sheet skipped
    assert set(out["patient_id"]) == {"HN-HGJ-001", "HN-HGJ-002"}
    row1 = out.set_index("patient_id").loc["HN-HGJ-001"]
    assert row1["locoregional"] == 1.0
    assert row1["death"] == 1.0  # "Yes" -> 1
    assert row1["hpv_status"] == "positive"  # non-event covariate passed through verbatim
    assert out.set_index("patient_id").loc["HN-HGJ-002"]["death"] == 0.0  # "No" -> 0


def _write_triple_to_zip(zf: zipfile.ZipFile, coll: str, pid: str, **kwargs) -> None:
    rs, rd, rp = build_rt_triple(patient_id=pid, **kwargs)
    for mod, ds, stem in (("RTSTRUCT", rs, "RS"), ("RTDOSE", rd, "RD"), ("RTPLAN", rp, "RP")):
        buf = io.BytesIO()
        save_dataset(ds, buf)
        zf.writestr(f"{coll}/{pid}/{mod}/{stem}.dcm", buf.getvalue())


def test_zip_pipeline_to_cohort_csv(tmp_path: Path):
    zpath = tmp_path / "mini.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        _write_triple_to_zip(zf, "MINI", "HN-CHUM-001", dose_gy=70.0, n_fractions=35)
        _write_triple_to_zip(zf, "MINI", "HN-CHUM-002", dose_gy=60.0, n_fractions=30)

    out_csv = tmp_path / "cohort_features.csv"
    df = build_cohort_csv(zpath, clinical_xlsx=None, out_csv=out_csv, limit=None)

    assert out_csv.is_file()
    assert set(df["patient_id"]) == {"HN-CHUM-001", "HN-CHUM-002"}
    assert (df["dose_summation_type"] == "PLAN").all()
    # PTV mean dose tracks the per-patient prescription.
    by_id = df.set_index("patient_id")["PTV_Dmean_gy"]
    assert abs(by_id["HN-CHUM-001"] - 70.0) < 0.2
    assert abs(by_id["HN-CHUM-002"] - 60.0) < 0.2
