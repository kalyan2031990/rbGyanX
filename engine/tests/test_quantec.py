import pandas as pd


def test_quantec_spinal_cord_violation():
    from validation.quantec_checker import check_quantec_constraints

    dvh = pd.DataFrame({"dose_gy": [47.0], "volume_frac": [1.0]})
    v = check_quantec_constraints(dvh, "SpinalCord")
    assert any(x.severity == "VIOLATION" for x in v)


def test_quantec_spinal_cord_pass():
    from validation.quantec_checker import check_quantec_constraints

    dvh = pd.DataFrame({"dose_gy": [38.0], "volume_frac": [1.0]})
    assert len(check_quantec_constraints(dvh, "SpinalCord")) == 0


def test_quantec_warning_zone():
    from validation.quantec_checker import check_quantec_constraints

    dvh = pd.DataFrame({"dose_gy": [43.0], "volume_frac": [1.0]})
    v = check_quantec_constraints(dvh, "SpinalCord")
    assert any(x.severity == "WARNING" for x in v)


def test_quantec_parotid_warning():
    from validation.quantec_checker import check_quantec_constraints

    dvh = pd.DataFrame({"dose_gy": [23.0], "volume_frac": [1.0]})
    v = check_quantec_constraints(dvh, "Parotid_L")
    assert len(v) > 0
