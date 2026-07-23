"""
DVH dose-unit handling must be explicit and deterministic (P1 · S4).

Units come from the file's own declarations ("Mean Dose [cGy]:", "Dose [Gy]" column
header), never from value magnitude. The same plan expressed in cGy and in Gy must yield
identical Gy DVHs and identical NTCP.
"""

from __future__ import annotations

import numpy as np
import pytest

from dicom_io.txt_dvh_reader import parse_dvh_text_file
from radiobiology import dvh_object_to_dataframe
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

pytestmark = pytest.mark.unit

_CGY = """\
Patient ID           : U-001
Prescribed dose [cGy]: 7000.0
Mean Dose [cGy]: 3000.0
Structure: Parotid
Number of fractions: 35

Dose [cGy]  Structure Volume [cm3]
0     100.0
1000   80.0
3000   40.0
5000   10.0
7000    0.0
"""

_GY = """\
Patient ID           : U-001
Prescribed dose [Gy]: 70.0
Mean Dose [Gy]: 30.0
Structure: Parotid
Number of fractions: 35

Dose [Gy]  Structure Volume [cm3]
0      100.0
10      80.0
30      40.0
50      10.0
70       0.0
"""


def _parse(tmp_path, text, name):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return parse_dvh_text_file(p)


def test_cgy_and_gy_give_identical_dvh_and_ntcp(tmp_path):
    a = _parse(tmp_path, _CGY, "a_cgy.txt")
    b = _parse(tmp_path, _GY, "b_gy.txt")

    assert a.dmean_gy == pytest.approx(b.dmean_gy)
    assert a.dmean_gy == pytest.approx(30.0)  # declared cGy converted, Gy left alone
    assert a.plan_metadata["prescription_dose_gy"] == pytest.approx(70.0)
    assert b.plan_metadata["prescription_dose_gy"] == pytest.approx(70.0)

    da = dvh_object_to_dataframe(a.dvh_object)
    db = dvh_object_to_dataframe(b.dvh_object)
    np.testing.assert_allclose(da["dose_gy"].to_numpy(), db["dose_gy"].to_numpy(), rtol=1e-9)
    np.testing.assert_allclose(
        da["volume_frac"].to_numpy(), db["volume_frac"].to_numpy(), rtol=1e-9
    )

    # Identical NTCP through both classical models.
    assert calculate_ntcp_lkb_probit(a.dmean_gy, 39.9, 0.40) == pytest.approx(
        calculate_ntcp_lkb_probit(b.dmean_gy, 39.9, 0.40)
    )
    assert calculate_ntcp_rs_poisson(da, 28.4, 1.0, 0.25) == pytest.approx(
        calculate_ntcp_rs_poisson(db, 28.4, 1.0, 0.25)
    )


def test_gy_file_above_150_is_not_rescaled(tmp_path):
    """The old >150 magnitude rule silently divided a legitimate high-dose Gy plan by 100."""
    text = """\
Patient ID           : HIGH-1
Prescribed dose [Gy]: 200.0
Structure: Target
Dose [Gy]  Volume [cm3]
0     100.0
100    60.0
200     0.0
"""
    res = _parse(tmp_path, text, "high_gy.txt")
    df = dvh_object_to_dataframe(res.dvh_object)
    assert df["dose_gy"].max() > 100.0, "declared Gy must not be divided by 100"
    assert res.plan_metadata["prescription_dose_gy"] == pytest.approx(200.0)


def test_undeclared_units_fall_back_to_magnitude_rule(tmp_path):
    """Backward compatibility: files with no unit label still parse via the old rule."""
    text = """\
Patient ID           : NOUNIT-1
Structure: Parotid
Dose  Volume
0     100.0
3000   40.0
7000    0.0
"""
    res = _parse(tmp_path, text, "nounit.txt")
    df = dvh_object_to_dataframe(res.dvh_object)
    assert df["dose_gy"].max() <= 100.0  # 7000 treated as cGy -> 70 Gy
