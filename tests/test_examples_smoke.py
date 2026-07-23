"""
Smoke tests for the shipped synthetic examples (examples/data/*).

Keep the illustrative example dataset valid and parseable so the quickstart never
rots. No patient data; pure format checks on committed synthetic files.
"""

from __future__ import annotations

import math
from pathlib import Path

from dicom_io.txt_dvh_reader import parse_dvh_text_file
from validation.clinical_cohort import load_clinical_csv

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
DATA = EXAMPLES / "data"


def test_example_dvh_files_parse():
    files = sorted((DATA / "dvh_txt").glob("*.txt"))
    assert files, "example DVH data missing — run examples/make_example_data.py"
    ptv_files = [f for f in files if "PTV70" in f.name]
    assert ptv_files
    res = parse_dvh_text_file(ptv_files[0])
    assert res.canonical_name == "PTV"
    assert res.quality_flag in {"OK", "LOW_BINS"}
    assert res.dmean_gy > 0 and not math.isnan(res.dmean_gy)
    assert res.total_volume_cc > 0


def test_example_clinical_csv_loads():
    cohort = load_clinical_csv(
        DATA / "clinical_cohort.csv",
        endpoint="xerostomia_grade2",
        covariate_cols=["age", "sex", "smoker"],
    )
    assert cohort.n == 10
    assert 0 < cohort.n_events < cohort.n  # both classes present
    assert cohort.covariates == ["age", "sex", "smoker"]


def test_make_example_data_is_runnable(tmp_path, monkeypatch):
    # Regenerate into a temp dir so the demo generator itself is exercised in CI.
    import examples.make_example_data as gen

    monkeypatch.setattr(gen, "DATA", tmp_path)
    gen.main()
    assert (tmp_path / "dvh_txt").is_dir()
    assert list((tmp_path / "dvh_txt").glob("*.txt"))
    assert (tmp_path / "clinical_cohort.csv").exists()
