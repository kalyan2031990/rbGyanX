"""Pinning tests for the three defects fixed in v1.5.2: #67, #66 and #68.

Measured against tag v1.5.1 (`641b37b`): **15 of these 17 fail there and pass here**. The two
that pass at the tag as well are guards, not pins, and say so in their docstrings --
`test_defect_67_the_refusal_still_withholds_every_tcp` (the fix must not turn a refusal into a
score) and `test_defect_67_dose_statistics_still_survive_a_refusal` (#62, fixed in v1.5.1, must
keep holding). Synthetic inputs only
-- a two-bin DVH, a hand-built plan-metadata dict and a temporary output tree. Nothing reads a
patient, a cohort or any archive.

* **#67** a target refused for any reason keeps `gEUD_gy`, and it is the same number a scored
  target reports for the same histogram.
* **#66** the run manifest's `n_patients_overridden` counts the cohort, not the batch that
  happened to write the manifest.
* **#68** when a supplied table sets the level, `dose_level_source` names the table and the
  DICOM field matched moves to `dose_level_matched_by`.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.site_params import TCPSiteParams  # noqa: E402
from radiobiology import dvh_object_to_dataframe  # noqa: E402
from radiobiology.geud_tcp import compute_geud_with_reason  # noqa: E402
from radiobiology.tcp_calculator import TCPCalculator  # noqa: E402
from rbgyanx_engine.pipeline import _target_plan_metadata  # noqa: E402


def _runner_helpers():
    """The #66 helpers, imported inside the tests that use them.

    Imported at module level they would turn a run against the v1.5.1 tag into a collection
    error, and a collection error proves nothing about the other two defects. This way each
    test fails on its own terms at the tag: #67 and #68 on their assertions, #66 on this import.
    """
    from rbgyanx_engine.cohort_runner import _harvest_used_the_table, _prescription_record

    return _harvest_used_the_table, _prescription_record


# --------------------------------------------------------------------------- fixtures
class _DVHObject:
    """A two-bin differential DVH in the shape `dvh_object_to_dataframe` reads.

    Bin edges 30/50/90 Gy give centres of 40 and 70 Gy, half the volume in each.
    """

    dvh_type = "differential"
    dose_units = "Gy"
    counts = [50.0, 50.0]
    bins = [30.0, 50.0, 90.0]

    @property
    def differential(self):
        return self


class _DVH:
    """The smallest thing the TCP orchestrator accepts."""

    def __init__(self, raw_name: str = "PTVLow", roi_number: int = 7):
        self.raw_name = raw_name
        self.canonical_name = "PTV"
        self.roi_number = roi_number
        self.total_volume_cc = 100.0
        self.extraction_mode = "synthetic"
        self.quality_flag = "OK"
        self.dvh_object = _DVHObject()

    @property
    def dvh_df(self) -> pd.DataFrame:
        """The same frame the orchestrator will build, for computing an expected value."""
        return dvh_object_to_dataframe(self.dvh_object)


class _Target:
    def __init__(self, raw_name: str, roi_number: int):
        self.raw_name = raw_name
        self.roi_number = roi_number


def _site_params() -> TCPSiteParams:
    return TCPSiteParams(
        site="HN", alpha_gy_inv=0.35, beta_gy_inv2=0.035, alpha_beta_gy=10.0,
        N0_gtv=1e7, N0_ctv=1e6, Tpot_days=3.0, Tk_days=28.0,
        TCD50_gy=50.0, gamma50=2.0, geud_a=-10.0,
        D50_logistic_gy=50.0, k_logistic=2.0, lq_valid_max_dpf_gy=8.0,
        repopulation_relevant=True, params_source="synthetic test fixture",
    )


def _scored_meta() -> dict:
    return {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_level_gy": 70.0,
            "dose_level_source": "target name", "tcp_refusal_reasons": []}


def _refused_meta() -> dict:
    """What `_target_plan_metadata` hands back for a SIB target it cannot tie to a level."""
    return {"prescription_dose_gy": 70.0, "n_fractions": 35,
            "tcp_refusal_reasons": ["SIB_LEVEL_UNKNOWN"]}


# --------------------------------------------------------------------------- #67
def test_defect_67_a_refused_target_keeps_its_geud():
    """#67: refusing a TCP must not discard a gEUD the DVH and `a` fully determine."""
    row = TCPCalculator().compute_all(_DVH(), _refused_meta(), _site_params(), target_type="PTV")
    assert row["tcp_refused"] is True
    assert row["tcp_refusal_reason"] == "SIB_LEVEL_UNKNOWN"
    assert math.isfinite(row["gEUD_gy"]), "a refused target reported NaN for a computable gEUD"
    assert row["gEUD_gy"] > 0


def test_defect_67_the_refused_geud_equals_the_scored_geud_bit_for_bit():
    """The same histogram must give the same gEUD whether or not the TCP was refused."""
    calc = TCPCalculator()
    scored = calc.compute_all(_DVH(), _scored_meta(), _site_params(), target_type="PTV")
    refused = calc.compute_all(_DVH(), _refused_meta(), _site_params(), target_type="PTV")
    assert repr(float(refused["gEUD_gy"])) == repr(float(scored["gEUD_gy"]))


def test_defect_67_the_geud_matches_the_function_that_defines_it():
    """Not merely self-consistent: it is the gEUD of this DVH at this site's `a`."""
    sp = _site_params()
    expected, _ = compute_geud_with_reason(_DVH().dvh_df, sp.geud_a)
    row = TCPCalculator().compute_all(_DVH(), _refused_meta(), sp, target_type="PTV")
    assert repr(float(row["gEUD_gy"])) == repr(float(expected))


def test_defect_67_the_refusal_still_withholds_every_tcp():
    """Guard, not a pin: this already held at v1.5.1 and must go on holding."""
    row = TCPCalculator().compute_all(_DVH(), _refused_meta(), _site_params(), target_type="PTV")
    for model in ("TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic", "TCP_mean"):
        assert not math.isfinite(row[model]), f"{model} was reported on a refused target"


def test_defect_67_dose_statistics_still_survive_a_refusal():
    """Guard, not a pin: #62 passed at v1.5.1 and #67 is the same rule on another field."""
    row = TCPCalculator().compute_all(_DVH(), _refused_meta(), _site_params(), target_type="PTV")
    for field in ("D2_gy", "D50_gy", "D98_gy", "Dmean_gy"):
        assert math.isfinite(row[field]), f"{field} was discarded by the refusal"


# --------------------------------------------------------------------------- #66
class _FakeTable:
    """A prescription table that has looked up only part of the cohort, as a resumed run leaves it."""

    def __init__(self, entries: int, matched_this_process: list[str]):
        self._entries = entries
        self._matched = matched_this_process

    def manifest_record(self) -> dict:
        return {"path": "table.csv", "sha256": "0" * 64, "entries": self._entries,
                "patients_overridden": sorted(self._matched),
                "n_patients_overridden": len(self._matched),
                "entries_not_matched_to_a_patient": []}


def test_defect_66_the_manifest_counts_the_cohort_not_the_last_batch():
    """#66: a run resumed in batches must not report the final batch as the whole cohort."""
    _, _prescription_record = _runner_helpers()
    table = _FakeTable(entries=121, matched_this_process=["P-0113", "P-0114"])
    cohort_raw = {f"P-{i:04d}" for i in range(1, 117)}      # 116 patients on disk
    cohort_labels = {f"S-{i:04d}" for i in range(1, 117)}
    rec = _prescription_record(table, cohort_raw, cohort_labels)
    assert rec["n_patients_overridden"] == 116
    assert rec["n_patients_overridden_this_process"] == 2
    assert len(rec["patients_overridden_labels"]) == 116


def test_defect_66_the_per_process_count_is_kept_under_a_name_that_says_so():
    _, _prescription_record = _runner_helpers()
    table = _FakeTable(entries=10, matched_this_process=["P-0001"])
    rec = _prescription_record(table, {"P-0001", "P-0002"}, {"S-0001", "S-0002"})
    assert rec["patients_overridden_this_process"] == ["P-0001"]
    assert "this process" in rec["cumulative_source"]


def test_defect_66_no_table_still_records_nothing():
    _, _prescription_record = _runner_helpers()
    assert _prescription_record(None, set(), set()) is None


@pytest.mark.parametrize(
    "harvest,expected",
    [
        ({"tcp": [{"prescription_source": "user_prescription_table"}]}, True),
        ({"tcp": [{"prescription_source": "rtplan"}]}, False),
        ({"tcp": []}, False),
        ({}, False),
    ],
)
def test_defect_66_a_cached_patient_is_read_from_its_harvest(harvest, expected):
    """The cumulative count comes from the output on disk, so a resumed patient counts."""
    _harvest_used_the_table, _ = _runner_helpers()
    assert _harvest_used_the_table(harvest) is expected


# --------------------------------------------------------------------------- #68
def _meta_with_table_level() -> dict:
    """Plan metadata after a supplied table has written the level, as the table module leaves it."""
    return {
        "prescription_dose_gy": 59.0,
        "prescription_dose_gy_from_rtplan": 70.0,
        "prescription_source": "user_prescription_table",
        "n_fractions": 35,
        "dose_levels": [{"dose_gy": 59.0, "description": "PTV70", "roi_number": None,
                         "source": "user_prescription_table"}],
        "tcp_refusal_reasons": [],
    }


def test_defect_68_dose_level_source_names_the_table_not_the_dicom_field():
    """#68: the row said DoseReferenceSequence on a run where no DICOM value changed."""
    meta = _target_plan_metadata(_meta_with_table_level(), _Target("PTV70", 30))
    assert meta["dose_level_gy"] == 59.0
    assert meta["dose_level_source"] == "user_prescription_table"


def test_defect_68_the_dicom_field_matched_is_kept_in_its_own_column():
    meta = _target_plan_metadata(_meta_with_table_level(), _Target("PTV70", 30))
    assert meta["dose_level_matched_by"] == "DoseReferenceSequence.DoseReferenceDescription"


def test_defect_68_a_plan_level_still_reports_the_dicom_field():
    """Without a table nothing changes: the value did come from the RT Plan."""
    meta = {"prescription_dose_gy": 70.0, "n_fractions": 35, "tcp_refusal_reasons": [],
            "dose_levels": [{"dose_gy": 70.0, "description": "PTV70", "roi_number": None}]}
    out = _target_plan_metadata(meta, _Target("PTV70", 30))
    assert out["dose_level_source"] == "DoseReferenceSequence.DoseReferenceDescription"
    assert out["dose_level_matched_by"] == ""


def test_defect_68_a_single_plan_level_written_by_the_table_names_the_table():
    meta = {"prescription_dose_gy": 59.0, "n_fractions": 35, "tcp_refusal_reasons": [],
            "prescription_source": "user_prescription_table",
            "dose_levels": [{"dose_gy": 59.0, "description": "", "roi_number": None,
                             "source": "user_prescription_table"}]}
    out = _target_plan_metadata(meta, _Target("ElectiveVolume", 12))
    assert out["dose_level_source"] == "user_prescription_table"
    assert out["dose_level_matched_by"] == "single plan level"


def test_defect_68_a_refused_target_reports_no_match():
    meta = {"prescription_dose_gy": 70.0, "n_fractions": 35, "tcp_refusal_reasons": [],
            "dose_levels": [{"dose_gy": 70.0, "description": "PTV70", "roi_number": None},
                            {"dose_gy": 56.0, "description": "PTV56", "roi_number": None}]}
    out = _target_plan_metadata(meta, _Target("ElectiveVolume", 12))
    assert out["dose_level_source"] == "unknown"
    assert out["dose_level_matched_by"] == ""
    assert "SIB_LEVEL_UNKNOWN" in out["tcp_refusal_reasons"]
