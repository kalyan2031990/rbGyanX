"""Tests for treatment site auto-detection."""

from dicom_io.site_detector import (
    detect_site,
    detect_site_from_text,
    params_site_key,
    resolve_pipeline_site,
)


def test_hn_from_label():
    plan = {
        "plan_label": "HN_66Gy_33fr",
        "n_fractions": 33,
        "dose_per_fraction_gy": 2.0,
        "prescription_dose_gy": 66,
    }
    result = detect_site(plan, [])
    assert result["site"] == "HN"
    assert result["confidence"] == "HIGH"


def test_lung_from_label_conventional_fractionation():
    plan = {
        "plan_label": "LUNG_NSCLC_IMRT",
        "n_fractions": 30,
        "dose_per_fraction_gy": 2.0,
        "prescription_dose_gy": 60,
    }
    result = detect_site(plan, [])
    assert result["site"] == "LUNG"
    assert result["fractionation"] == "CONVENTIONAL"
    assert params_site_key(result["site"], result["histology"]) == "LUNG"


def test_brain_gbm_not_inferred_from_single_fraction():
    plan = {
        "plan_label": "GBM_cranial_IMRT",
        "n_fractions": 1,
        "dose_per_fraction_gy": 20.0,
        "prescription_dose_gy": 20,
    }
    result = detect_site(plan, [])
    assert result["site"] == "BRAIN"
    assert result["histology"] == "GBM"
    assert params_site_key(result["site"], result["histology"]) == "BRAIN_GBM"
    assert result["fractionation"] == "SINGLE_FRACTION"


def test_brain_mets_from_disease_keywords():
    plan = {
        "plan_label": "Brain_metastasis_plan",
        "n_fractions": 5,
        "dose_per_fraction_gy": 6.0,
        "prescription_dose_gy": 30,
    }
    result = detect_site(plan, [])
    assert result["site"] == "BRAIN"
    assert result["histology"] == "METS"
    assert params_site_key(result["site"], result["histology"]) == "BRAIN_METS"


def test_breast_from_fractionation_regime_only():
    plan = {
        "plan_label": "BREAST_40GY",
        "n_fractions": 15,
        "dose_per_fraction_gy": 2.67,
        "prescription_dose_gy": 40.05,
    }
    result = detect_site(plan, [])
    assert result["site"] == "BREAST"
    assert result["fractionation"] in ("HYPOFRACTIONATED", "OTHER", "")


def test_oar_presence_overrides():
    plan = {
        "plan_label": "UNKNOWN",
        "n_fractions": 30,
        "dose_per_fraction_gy": 2.0,
        "prescription_dose_gy": 60,
    }
    structs = [{"canonical": "Parotid_L"}, {"canonical": "Mandible"}]
    result = detect_site(plan, structs)
    assert result["site"] == "HN"
    assert result["confidence"] == "HIGH"


def test_params_site_key_brain_histology():
    assert params_site_key("BRAIN", "METS") == "BRAIN_METS"
    assert params_site_key("BRAIN", "GBM") == "BRAIN_GBM"
    assert params_site_key("BRAIN", "") == "BRAIN_GBM"
    assert params_site_key("LUNG", "") == "LUNG"
    assert params_site_key("LUNG_SBRT", "") == "LUNG"


def test_detect_site_from_text_hn_structure():
    plan = {
        "plan_label": "Plan3",
        "n_fractions": 35,
        "dose_per_fraction_gy": 2.0,
        "prescription_dose_gy": 70.0,
    }
    result = detect_site_from_text(
        plan, "PTV HR", "Patient comment: head and neck squamous"
    )
    assert result["site"] == "HN"


def test_resolve_pipeline_site_override():
    det = {"site": "LUNG", "histology": "", "confidence": "HIGH", "evidence": []}
    key, info = resolve_pipeline_site("HN", det)
    assert key == "HN"
    assert info["confidence"] == "USER"


def test_ambiguous_curative_plan_not_default_hn():
    """Regression: prostate/cervix EBRT must not be labelled HN from dose-fractionation alone."""
    plan = {
        "plan_label": "CTV_HR 78Gy/39fx",
        "prescription_dose_gy": 78,
        "n_fractions": 39,
        "dose_per_fraction_gy": 2.0,
    }
    result = detect_site(plan, [{"canonical": "PTV"}])
    assert result["site"] == "UNKNOWN"


def test_resolve_pipeline_site_unknown_raises():
    det = {"site": "UNKNOWN", "histology": "", "confidence": "LOW", "evidence": []}
    try:
        resolve_pipeline_site(None, det)
        raised = False
    except ValueError:
        raised = True
    assert raised
