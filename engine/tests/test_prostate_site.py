"""Smoke tests for prostate/pelvic site detection and NTCP loading."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))


def test_prostate_keyword_detected():
    from dicom_io.site_detector import detect_site

    result = detect_site(
        {
            "plan_label": "PROSTATE 78Gy/39fx",
            "prescription_dose_gy": 78.0,
            "n_fractions": 39,
            "dose_per_fraction_gy": 2.0,
        },
        [{"canonical": "PTV"}, {"canonical": "Rectum"}, {"canonical": "Bladder"}],
    )
    assert result["site"] == "PROSTATE"


def test_prostate_oar_detected_from_structures():
    from dicom_io.site_detector import detect_site

    result = detect_site(
        {
            "plan_label": "PLAN_01",
            "prescription_dose_gy": 78.0,
            "n_fractions": 39,
            "dose_per_fraction_gy": 2.0,
        },
        [
            {"canonical": "PTV"},
            {"canonical": "Rectum"},
            {"canonical": "Bladder"},
            {"canonical": "FemoralHead_L"},
        ],
    )
    assert result["site"] == "PROSTATE"


def test_prostate_ntcp_params_load():
    from config.site_ntcp_params import load_site_ntcp_params

    params = load_site_ntcp_params("PROSTATE")
    assert "Rectum" in params.organs
    assert "Bladder" in params.organs


def test_prostate_site_not_misclassified_as_hn():
    from dicom_io.site_detector import detect_site

    result = detect_site(
        {
            "plan_label": "PATIENT_001",
            "prescription_dose_gy": 76.0,
            "n_fractions": 38,
            "dose_per_fraction_gy": 2.0,
        },
        [{"canonical": "PTV"}],
    )
    assert result["site"] != "HN"
