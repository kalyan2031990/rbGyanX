"""Tier A defect #25 — each SIB target is scored against its own prescription level.

Each test fails on v1.4.0 (``ffd69ef``) and passes after the fix.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pytest
from pydicom.dataset import Dataset

from dicom_io.dicom_reader import (
    SIB_LEVEL_UNKNOWN,
    dose_level_from_target_name,
    dose_levels_from_plan,
)
from rbgyanx_engine.pipeline import _target_plan_metadata


@dataclass
class _Target:
    raw_name: str
    roi_number: int | None = None


def _plan(levels: list[tuple[float, str, int | None]]) -> Dataset:
    ds = Dataset()
    items = []
    for dose, description, roi in levels:
        item = Dataset()
        item.TargetPrescriptionDose = dose
        item.DoseReferenceType = "TARGET"
        if description:
            item.DoseReferenceDescription = description
        if roi is not None:
            item.ReferencedROINumber = roi
        items.append(item)
    ds.DoseReferenceSequence = items
    return ds


# -------------------------------------------------------------- reading the levels off the plan


def test_defect_25_every_level_is_read_not_just_the_first() -> None:
    """#25: ``_prescription_dose_gy`` returned one number for the whole plan."""
    levels = dose_levels_from_plan(_plan([(70.0, "PTV70", 1), (56.0, "PTV56", 2)]))
    assert [lv["dose_gy"] for lv in levels] == [70.0, 56.0]
    assert [lv["roi_number"] for lv in levels] == [1, 2]


def test_defect_25_an_implausible_level_is_ignored() -> None:
    """A 0 Gy or 500 Gy dose reference is not a prescription level."""
    levels = dose_levels_from_plan(_plan([(0.0, "", None), (500.0, "", None), (70.0, "", None)]))
    assert [lv["dose_gy"] for lv in levels] == [70.0]


@pytest.mark.parametrize(
    "name, level",
    [
        ("PTV63", 63.0),
        ("PTV_56", 56.0),
        ("PTV 70 Gy", 70.0),
        ("PTV5600", 56.0),  # cGy
        ("PTV_5040_cGy", 50.4),
        ("PTV 46GY", 46.0),
        ("PTV", None),
        ("PTVHigh", None),
        ("GTV", None),
        ("CTV1", None),  # an index, not a dose
    ],
)
def test_defect_25_the_level_in_a_target_name(name: str, level: float | None) -> None:
    assert dose_level_from_target_name(name) == level


# ------------------------------------------------------- scoring each target at its own level

_META = {
    "prescription_dose_gy": 70.0,
    "n_fractions": 35,
    "dose_per_fraction_gy": 2.0,
    "dose_levels": [
        {"dose_gy": 70.0, "description": "PTV70", "roi_number": 1, "type": "TARGET"},
        {"dose_gy": 56.0, "description": "PTV56", "roi_number": 2, "type": "TARGET"},
    ],
}


def test_defect_25_the_boost_target_keeps_the_high_level() -> None:
    meta = _target_plan_metadata(_META, _Target("PTV70", roi_number=1))
    assert meta["prescription_dose_gy"] == pytest.approx(70.0)
    assert meta["dose_per_fraction_gy"] == pytest.approx(2.0)
    assert meta["tcp_refusal_reasons"] == []


def test_defect_25_the_elective_target_is_scored_at_56_not_70() -> None:
    """The defect itself: a PTV56 used to be given the plan's 70 Gy, raising its TCP."""
    meta = _target_plan_metadata(_META, _Target("PTV56", roi_number=2))
    assert meta["prescription_dose_gy"] == pytest.approx(56.0)
    assert meta["dose_per_fraction_gy"] == pytest.approx(56.0 / 35)
    assert meta["dose_level_source"] == "DoseReferenceSequence.ReferencedROINumber"
    assert meta["tcp_refusal_reasons"] == []


def test_defect_25_a_description_match_works_without_an_roi_reference() -> None:
    meta_no_roi = {
        **_META,
        "dose_levels": [
            {"dose_gy": 70.0, "description": "PTV_70", "roi_number": None, "type": "TARGET"},
            {"dose_gy": 56.0, "description": "PTV_56", "roi_number": None, "type": "TARGET"},
        ],
    }
    meta = _target_plan_metadata(meta_no_roi, _Target("PTV56"))
    assert meta["prescription_dose_gy"] == pytest.approx(56.0)
    assert meta["dose_level_source"] == "DoseReferenceSequence.DoseReferenceDescription"


def test_defect_25_the_target_name_is_used_when_the_plan_ties_nothing() -> None:
    meta_unlinked = {
        **_META,
        "dose_levels": [
            {"dose_gy": 70.0, "description": "", "roi_number": None, "type": "TARGET"},
            {"dose_gy": 56.0, "description": "", "roi_number": None, "type": "TARGET"},
        ],
    }
    meta = _target_plan_metadata(meta_unlinked, _Target("PTV56"))
    assert meta["prescription_dose_gy"] == pytest.approx(56.0)
    assert meta["dose_level_source"] == "target name"


def test_defect_25_an_undeterminable_level_refuses_tcp() -> None:
    """#25: two levels and nothing ties either to this target — refusing beats guessing high."""
    meta_unlinked = {
        **_META,
        "dose_levels": [
            {"dose_gy": 70.0, "description": "", "roi_number": None, "type": "TARGET"},
            {"dose_gy": 56.0, "description": "", "roi_number": None, "type": "TARGET"},
        ],
    }
    meta = _target_plan_metadata(meta_unlinked, _Target("PTVHigh"))
    assert meta["tcp_refusal_reasons"] == [SIB_LEVEL_UNKNOWN]
    assert meta["dose_level_source"] == "unknown"


def test_defect_25_a_single_level_plan_is_unchanged() -> None:
    """A plan with one prescription is not a SIB, so nothing has to be matched."""
    meta_single = {
        **_META,
        "dose_levels": [
            {"dose_gy": 70.0, "description": "", "roi_number": None, "type": "TARGET"}
        ],
    }
    meta = _target_plan_metadata(meta_single, _Target("PTV"))
    assert meta["prescription_dose_gy"] == pytest.approx(70.0)
    assert meta["dose_level_source"] == "single plan level"
    assert meta["tcp_refusal_reasons"] == []


def test_defect_25_a_plan_without_a_dose_reference_sequence_still_works() -> None:
    """Older exports carry no DoseReferenceSequence; the plan prescription is all there is."""
    meta = _target_plan_metadata(
        {"prescription_dose_gy": 66.0, "n_fractions": 33, "dose_levels": []},
        _Target("PTV"),
    )
    assert meta["prescription_dose_gy"] == pytest.approx(66.0)
    assert meta["dose_level_source"] == "plan prescription"


def test_defect_25_the_refusal_reaches_the_tcp_row() -> None:
    from config.site_params import SITE_PARAMS
    from radiobiology.tcp_calculator import TCPCalculator

    meta_unlinked = {
        **_META,
        "dose_levels": [
            {"dose_gy": 70.0, "description": "", "roi_number": None, "type": "TARGET"},
            {"dose_gy": 56.0, "description": "", "roi_number": None, "type": "TARGET"},
        ],
    }
    target_meta = _target_plan_metadata(meta_unlinked, _Target("PTVHigh"))

    class _DVH:
        canonical_name = "PTV"
        raw_name = "PTVHigh"
        dvh_object = None
        dmean_gy = 60.0
        quality_flag = "OK"

    row = TCPCalculator().compute_all(_DVH(), target_meta, SITE_PARAMS["HN"], target_type="PTV")
    assert row["tcp_refused"] is True
    assert row["tcp_refusal_reason"] == SIB_LEVEL_UNKNOWN
    assert math.isnan(row["TCP_Poisson"])


def test_defect_25_an_upstream_refusal_is_not_lost() -> None:
    """A txt export with no prescription (#4/#5) keeps its reason through the SIB resolution."""
    meta = _target_plan_metadata(
        {
            "prescription_dose_gy": 70.0,
            "n_fractions": 35,
            "dose_levels": [
                {"dose_gy": 70.0, "description": "", "roi_number": None, "type": "TARGET"}
            ],
            "tcp_refusal_reasons": ["RX_MISSING"],
        },
        _Target("PTV"),
    )
    assert meta["tcp_refusal_reasons"] == ["RX_MISSING"]
