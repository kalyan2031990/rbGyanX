"""
DVH integrity regression tests (branch fix/dvh-integrity).

These fail on the pre-fix code and pass after it:
  * an inverted cumulative DVH is rejected with a clear error;
  * an out-of-order DVH is deterministically sorted, then validated (benign reorder accepted,
    malformed reorder rejected);
  * a PTV/CTV/GTV never receives an NTCP through the run controller;
  * every shipped example DVH parses and is a valid cumulative curve;
  * the do-no-harm numerics (positive controls) are unaffected.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from dicom_io.dvh_integrity import DVHIntegrityError, validate_cumulative_dvh

pytestmark = pytest.mark.unit

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "data" / "dvh_txt"


# --------------------------------------------------------------- the validator


def test_valid_cumulative_dvh_passes_and_sorts():
    dose = np.array([0.0, 10.0, 20.0, 30.0])
    vol = np.array([100.0, 60.0, 20.0, 0.0])
    d, v = validate_cumulative_dvh(dose, vol, structure="OAR")
    assert np.allclose(d, dose) and np.allclose(v, vol)


def test_inverted_cumulative_dvh_is_rejected():
    # volume RISES with dose -> physically impossible
    dose = np.array([42.0, 56.0, 63.0, 70.0, 72.1])
    vol = np.array([1.0, 10.0, 60.0, 99.0, 100.0])
    with pytest.raises(DVHIntegrityError, match="RISES with dose"):
        validate_cumulative_dvh(dose, vol, structure="PTV70")


def test_out_of_order_but_valid_is_sorted_and_accepted():
    dose = np.array([20.0, 0.0, 30.0, 10.0])
    vol = np.array([20.0, 100.0, 0.0, 60.0])  # correct pairing, shuffled rows
    d, v = validate_cumulative_dvh(dose, vol, structure="OAR")
    assert list(d) == [0.0, 10.0, 20.0, 30.0]
    assert list(v) == [100.0, 60.0, 20.0, 0.0]


def test_out_of_order_and_malformed_is_rejected():
    # the shipped-data defect: last two rows swapped so sorted volume rises (0.5 then 5)
    dose = np.array([0.0, 9.6, 24.0, 33.6, 32.0])
    vol = np.array([30.0, 24.0, 12.0, 5.0, 0.5])
    with pytest.raises(DVHIntegrityError, match="RISES with dose"):
        validate_cumulative_dvh(dose, vol, structure="Parotid_L")


def test_negative_and_nonfinite_rejected():
    with pytest.raises(DVHIntegrityError, match="negative"):
        validate_cumulative_dvh(np.array([0.0, -1.0]), np.array([10.0, 5.0]), structure="X")
    with pytest.raises(DVHIntegrityError, match="non-finite"):
        validate_cumulative_dvh(np.array([0.0, np.nan]), np.array([10.0, 5.0]), structure="X")


# ------------------------------------------------------ reader rejects bad text


def test_reader_rejects_inverted_ptv_file(tmp_path):
    from dicom_io.txt_dvh_reader import parse_dvh_text_file

    bad = tmp_path / "BAD_PTV70_dvh.txt"
    bad.write_text(
        "Patient ID          : BAD\nMean Dose [cGy]: 7070\nStructure: PTV70\n\n"
        "Dose [cGy]  Structure Volume [cm3]\n"
        "7210  100.0\n7000  99.0\n6650  90.0\n6300  60.0\n5600  10.0\n4200  1.0\n",
        encoding="utf-8",
    )
    with pytest.raises(DVHIntegrityError, match="RISES with dose"):
        parse_dvh_text_file(bad)


# ------------------------------------------------ NTCP never assigned to targets


@pytest.mark.parametrize("name", ["PTV70", "PTV_70", "CTV", "GTV", "PTVn", "ptv 70gy"])
def test_targets_never_receive_ntcp_via_run_controller(tmp_path, name):
    from rbgyanx.services.run_controller import RunController
    from rbgyanx.services.run_request import RunRequest

    f = tmp_path / f"P_{name.replace(' ', '_')}_dvh.txt"
    f.write_text(
        f"Patient ID          : P\nMean Dose [cGy]: 7000\nStructure: {name}\n\n"
        "Dose [cGy]  Structure Volume [cm3]\n"
        "0  100.0\n2000  100.0\n6000  90.0\n7000  50.0\n7400  0.0\n",
        encoding="utf-8",
    )
    req = RunRequest(
        analysis_mode="NTCP", input_path=tmp_path, output_dir=tmp_path, input_source="dvh_txt"
    )
    res = RunController().run_dvh_text(
        req, ntcp_models={"LKB": {"model": "lkb_probit", "params": {"TD50_gy": 39.9, "m": 0.40}}}
    )
    s = res.structures[0]
    assert s.is_target is True
    assert s.ntcp == {}, "a target must carry no NTCP value"


def test_oar_still_receives_ntcp(tmp_path):
    from rbgyanx.services.run_controller import RunController
    from rbgyanx.services.run_request import RunRequest

    f = tmp_path / "P_Parotid_L_dvh.txt"
    f.write_text(
        "Patient ID          : P\nMean Dose [cGy]: 2400\nStructure: Parotid_L\n\n"
        "Dose [cGy]  Structure Volume [cm3]\n"
        "0  30.0\n1200  20.0\n2400  10.0\n4000  1.0\n5000  0.0\n",
        encoding="utf-8",
    )
    req = RunRequest(
        analysis_mode="NTCP", input_path=tmp_path, output_dir=tmp_path, input_source="dvh_txt"
    )
    res = RunController().run_dvh_text(
        req, ntcp_models={"LKB": {"model": "lkb_probit", "params": {"TD50_gy": 39.9, "m": 0.40}}}
    )
    s = res.structures[0]
    assert s.is_target is False
    assert "LKB" in s.ntcp and s.ntcp["LKB"] == s.ntcp["LKB"]  # a real number


# --------------------------------------------- shipped examples are a positive control


def test_every_shipped_example_is_a_valid_cumulative_dvh():
    from dicom_io.txt_dvh_reader import parse_dvh_text_file

    files = sorted(EXAMPLES.glob("*.txt"))
    assert len(files) >= 12
    for f in files:
        parsed = parse_dvh_text_file(f)  # raises DVHIntegrityError if any curve is invalid
        assert parsed.dmean_gy == parsed.dmean_gy  # not NaN


def test_shipped_ptv_files_are_targets_without_ntcp():
    from rbgyanx.services.run_controller import RunController
    from rbgyanx.services.run_request import RunRequest

    req = RunRequest(
        analysis_mode="NTCP", input_path=EXAMPLES, output_dir=EXAMPLES, input_source="dvh_txt"
    )
    res = RunController().run_dvh_text(
        req, ntcp_models={"LKB": {"model": "lkb_probit", "params": {"TD50_gy": 39.9, "m": 0.40}}}
    )
    assert res.ok
    for s in res.structures:
        if "PTV" in s.label.upper() or "CTV" in s.label.upper() or "GTV" in s.label.upper():
            assert s.is_target and s.ntcp == {}
        else:
            assert not s.is_target and s.ntcp
