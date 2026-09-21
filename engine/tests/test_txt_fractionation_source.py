"""B.3: dvh_txt fractionation values are marked parsed vs assumed, and assumed ones warn at read time.

The reader must not refuse or change any number for a file lacking fractionation (refusal is v1.4
work); it only has to say, beside each value, where it came from.
"""
import logging
from pathlib import Path

import pytest

from dicom_io.txt_dvh_reader import parse_dvh_text_file
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
    assert not [m for m in caplog.messages if "fractionation not stated" in m]


def test_unstated_fractionation_is_assumed_and_warns(tmp_path: Path, caplog) -> None:
    with caplog.at_level(logging.WARNING, logger="dicom_io.txt_dvh_reader"):
        r = parse_dvh_text_file(_write(tmp_path, "unstated.txt", _UNSTATED), default_dose_per_fraction_gy=2.0)
    assert {k: r.plan_metadata[k] for k in _KEYS} == {k: "assumed" for k in _KEYS}
    # Numbers are unchanged from before: total dose = DVH max, dpf = default, n_frac derived.
    assert r.plan_metadata["prescription_dose_gy"] == pytest.approx(40.0)
    assert r.plan_metadata["n_fractions"] == 20
    warned = [m for m in caplog.messages if "fractionation not stated" in m]
    assert len(warned) == 1 and "n_fractions=20" in warned[0]


def test_partial_header_marks_only_what_was_defaulted(tmp_path: Path) -> None:
    text = "Patient ID           : FR-003\nPrescribed dose [Gy]: 36.25\n\n" + _TABLE
    r = parse_dvh_text_file(_write(tmp_path, "partial.txt", text), default_dose_per_fraction_gy=2.0)
    assert r.plan_metadata["total_dose_source"] == "parsed"
    assert r.plan_metadata["n_fractions_source"] == "assumed"  # derived from an assumed dpf
    assert r.plan_metadata["dose_per_fraction_source"] == "assumed"


@pytest.mark.parametrize(("text", "expected"), [(_STATED, "parsed"), (_UNSTATED, "assumed")])
def test_sources_land_on_the_tcp_result_row(tmp_path: Path, text: str, expected: str) -> None:
    d = tmp_path / "dvh"
    d.mkdir()
    (d / "p.txt").write_text(text, encoding="utf-8")
    rows = collect_txt_tcp(d, site_override="PROSTATE", user_config=None, glob_pattern="*.txt", default_dpf_gy=2.0)
    assert len(rows) == 1
    assert {k: rows[0][k] for k in _KEYS} == {k: expected for k in _KEYS}
