"""dvh_txt fractionation: where each value came from, and refusal when it came from nowhere.

B.3 asked only that each value say whether it was parsed or assumed, and left refusal to later
work. That later work is defects #4 and #5, and this module now covers it: the reader no longer
falls back to the DVH maximum for the prescription or to 2 Gy for the dose per fraction, so an
export that states neither refuses TCP (``RX_MISSING`` / ``FRACTIONATION_MISSING``) instead of
publishing a number derived from a guess. ``parsed`` still means the file said it; ``caller``
means the operator did; ``derived`` means it follows arithmetically from those; ``missing``
means nobody said it.
"""
import logging
import math
from pathlib import Path

import pytest

from dicom_io.txt_dvh_reader import (
    FRACTIONATION_MISSING,
    RX_MISSING,
    parse_dvh_text_file,
)
from rbgyanx_engine.pipeline import collect_txt_tcp

_TABLE = """\
Structure: PTV
Mean Dose [Gy]: 36.9
        Dose [Gy]   Ratio of Total Structure Volume [%]
0    100
36   99
38   40
40   0
"""
_STATED = """\
Patient ID           : FR-001
Prescribed dose [Gy]: 36.25
Number of fractions: 5
Dose per fraction [Gy]: 7.25

""" + _TABLE
_UNSTATED = "Patient ID           : FR-002\n\n" + _TABLE
_KEYS = ("total_dose_source", "n_fractions_source", "dose_per_fraction_source")


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_stated_fractionation_is_parsed_and_does_not_warn(tmp_path: Path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="dicom_io.txt_dvh_reader"):
        r = parse_dvh_text_file(_write(tmp_path, "stated.txt", _STATED))
    assert {k: r.plan_metadata[k] for k in _KEYS} == {k: "parsed" for k in _KEYS}
    assert r.plan_metadata["n_fractions"] == 5
    assert r.plan_metadata["dose_per_fraction_gy"] == pytest.approx(7.25)
    assert r.plan_metadata["tcp_refusal_reasons"] == []
    assert not [m for m in caplog.messages if RX_MISSING in m or FRACTIONATION_MISSING in m]


def test_defect_4_5_an_unstated_prescription_is_not_the_dvh_maximum(tmp_path: Path, caplog) -> None:
    """#4: ``rx_gy`` fell back to ``d_gy.max()``. A DVH maximum is not a prescription."""
    with caplog.at_level(logging.WARNING, logger="dicom_io.txt_dvh_reader"):
        r = parse_dvh_text_file(_write(tmp_path, "unstated.txt", _UNSTATED))
    assert {k: r.plan_metadata[k] for k in _KEYS} == {k: "missing" for k in _KEYS}
    assert math.isnan(r.plan_metadata["prescription_dose_gy"])  # v1.4.0 said 40.0, the DVH max
    assert r.plan_metadata["n_fractions"] == 0
    assert r.plan_metadata["tcp_refusal_reasons"] == [RX_MISSING, FRACTIONATION_MISSING]
    assert len([m for m in caplog.messages if RX_MISSING in m]) == 1


def test_defect_4_5_the_caller_may_state_what_the_header_does_not(tmp_path: Path) -> None:
    """The plan's acceptance case: --rx-gy 70 --n-frac 35 computes."""
    r = parse_dvh_text_file(
        _write(tmp_path, "override.txt", _UNSTATED), rx_gy=70.0, n_frac=35
    )
    assert r.plan_metadata["tcp_refusal_reasons"] == []
    assert r.plan_metadata["prescription_dose_gy"] == pytest.approx(70.0)
    assert r.plan_metadata["n_fractions"] == 35
    assert r.plan_metadata["dose_per_fraction_gy"] == pytest.approx(2.0)
    assert r.plan_metadata["total_dose_source"] == "caller"
    assert r.plan_metadata["n_fractions_source"] == "caller"
    assert r.plan_metadata["dose_per_fraction_source"] == "derived"


def test_defect_4_5_a_stated_prescription_still_needs_a_fractionation(tmp_path: Path) -> None:
    """#5: the dose per fraction used to default to 2 Gy, which is someone else's clinic."""
    text = "Patient ID           : FR-003\nPrescribed dose [Gy]: 36.25\n\n" + _TABLE
    r = parse_dvh_text_file(_write(tmp_path, "partial.txt", text))
    assert r.plan_metadata["total_dose_source"] == "parsed"
    assert r.plan_metadata["n_fractions_source"] == "missing"
    assert r.plan_metadata["dose_per_fraction_source"] == "missing"
    assert r.plan_metadata["tcp_refusal_reasons"] == [FRACTIONATION_MISSING]
    # ... and an operator who states it is recorded as having stated it
    with_dpf = parse_dvh_text_file(
        _write(tmp_path, "partial2.txt", text), default_dose_per_fraction_gy=7.25
    )
    assert with_dpf.plan_metadata["n_fractions_source"] == "caller"
    assert with_dpf.plan_metadata["n_fractions"] == 5
    assert with_dpf.plan_metadata["tcp_refusal_reasons"] == []


@pytest.mark.parametrize(
    ("text", "expected"), [(_STATED, "parsed"), (_UNSTATED, "missing")]
)
def test_sources_land_on_the_tcp_result_row(tmp_path: Path, text: str, expected: str) -> None:
    d = tmp_path / "dvh"
    d.mkdir()
    (d / "p.txt").write_text(text, encoding="utf-8")
    rows = collect_txt_tcp(
        d,
        site_override="PROSTATE",
        user_config=None,
        glob_pattern="*.txt",
        default_dpf_gy=None,
    )
    assert len(rows) == 1
    assert {k: rows[0][k] for k in _KEYS} == {k: expected for k in _KEYS}


def test_defect_4_5_the_row_is_refused_not_merely_annotated(tmp_path: Path) -> None:
    """#4/#5: a warning beside a written TCP is not a refusal. The row must carry one."""
    d = tmp_path / "dvh"
    d.mkdir()
    (d / "p.txt").write_text(_UNSTATED, encoding="utf-8")
    rows = collect_txt_tcp(
        d,
        site_override="PROSTATE",
        user_config=None,
        glob_pattern="*.txt",
        default_dpf_gy=None,
    )
    row = rows[0]
    assert row["tcp_refused"] is True
    assert RX_MISSING in row["tcp_refusal_reason"]
    assert FRACTIONATION_MISSING in row["tcp_refusal_reason"]
    for key in ("TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic", "TCP_mean"):
        assert math.isnan(row[key]), (key, row[key])


def test_defect_4_5_the_overrides_reach_the_collector(tmp_path: Path) -> None:
    d = tmp_path / "dvh"
    d.mkdir()
    (d / "p.txt").write_text(_UNSTATED, encoding="utf-8")
    rows = collect_txt_tcp(
        d,
        site_override="PROSTATE",
        user_config=None,
        glob_pattern="*.txt",
        default_dpf_gy=None,
        rx_gy=70.0,
        n_frac=35,
    )
    row = rows[0]
    assert row["tcp_refused"] is False
    assert row["total_dose_gy"] == pytest.approx(70.0)
    assert row["n_fractions"] == 35
    assert not math.isnan(row["TCP_Poisson"])
