"""B.2: DICOM-path TCP rows carry raw_name / roi_number, so structure_mapping.csv is populated.

DICOM I/O is faked; what is under test is that collect_dicom_tcp passes each ROI's identity onto
its row and that the cohort runner's structure_mapping.csv picks it up unchanged.
"""
from collections import defaultdict
from types import SimpleNamespace

from dicom_io.dvh_extractor import DVHResult
from rbgyanx_engine import pipeline
from rbgyanx_engine.cohort_runner import PatientRecord, _accumulate


def _dvh(roi_number: int, raw_name: str) -> DVHResult:
    return DVHResult(
        roi_number=roi_number, raw_name=raw_name, canonical_name="PTV", category="TARGET",
        total_volume_cc=10.0, dmin_gy=1.0, dmean_gy=2.0, dmax_gy=3.0,
    )


def test_dicom_tcp_rows_carry_raw_name_and_roi_number(monkeypatch) -> None:
    class _Reader:
        def load_patient_dicom(self, *_a, **_k):
            return {"rt_plan": object(), "rt_struct": object(), "rt_dose": object()}

        def extract_plan_metadata(self, _plan):
            return {}

    class _Extractor:
        def extract_all_dvhs(self, *_a, **_k):
            # Two ROIs colliding on canonical PTV, distinguishable only by raw name / ROI number.
            return {7: _dvh(7, "PTV_high"), 9: _dvh(9, "PTV_low")}

    class _Calc:
        def compute_all(self, *_a, **_k):
            return {"TCP_Poisson": 0.5, "canonical_name": "PTV", "target_type": "PTV"}

    monkeypatch.setattr(pipeline, "DicomPlanReader", _Reader)
    monkeypatch.setattr(pipeline, "DVHExtractor", _Extractor)
    monkeypatch.setattr(pipeline, "TCPCalculator", _Calc)
    monkeypatch.setattr(pipeline, "get_target_structures", lambda *_a, **_k: [])
    monkeypatch.setattr(pipeline, "_structures_for_site_detection", lambda *_a, **_k: [])
    monkeypatch.setattr(pipeline, "detect_site", lambda *_a, **_k: {})
    monkeypatch.setattr(pipeline, "resolve_pipeline_site", lambda *_a, **_k: ("PROSTATE", {"site": "PROSTATE"}))
    monkeypatch.setattr(
        pipeline, "load_site_params",
        lambda *_a, **_k: SimpleNamespace(params_source="test", TCD50_gy=1.0, alpha_beta_gy=1.0),
    )

    rows = pipeline.collect_dicom_tcp(None, None, "anon", None)
    assert [(r["roi_number"], r["raw_name"]) for r in rows] == [(7, "PTV_high"), (9, "PTV_low")]

    accum: dict[str, list[dict]] = defaultdict(list)
    _accumulate(
        SimpleNamespace(site="PROSTATE"), "P-0001",
        PatientRecord(pseudonym="P-0001", status="completed", dvh_mode="COMPUTED"),
        {"tcp": rows, "ntcp": []}, accum, defaultdict(int),
    )
    mapping = accum["structure_mapping.csv"]
    assert [(m["roi_number"], m["raw_name"], m["canonical"]) for m in mapping] == [
        (7, "PTV_high", "PTV"), (9, "PTV_low", "PTV"),
    ]
