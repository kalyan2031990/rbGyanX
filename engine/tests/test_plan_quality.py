"""Plan-quality packs and physical metric helpers."""

from config.plan_quality import infer_technique_profile, load_plan_quality_config, resolve_pack_site_key
from dicom_io.dvh_extractor import DVHExtractor
from validation.plan_quality_eval import evaluate_plan_quality_flags


def test_infer_technique_sbrt():
    assert infer_technique_profile({"dose_per_fraction_gy": 12.0, "number_of_fractions": 5}) == "sbrt"
    assert infer_technique_profile({"dose_per_fraction_gy": 2.0, "number_of_fractions": 30}) == "conventional"
    assert infer_technique_profile({"dose_per_fraction_gy": 3.0, "number_of_fractions": 15}) == "hypofractionated"


def test_lung_sbrt_pack_key():
    assert resolve_pack_site_key("LUNG", "sbrt") == "LUNG_SBRT"
    assert resolve_pack_site_key("LUNG", "conventional") == "LUNG"


def test_plan_quality_yaml_loads():
    cfg = load_plan_quality_config()
    assert "HN" in cfg
    assert "LUNG_SBRT" in cfg
    assert "technique_profiles" in cfg["HN"]


def test_integral_dose_uniform(uniform_dvh_result):
    metrics = DVHExtractor().compute_dose_metrics(uniform_dvh_result, prescription_gy=60.0)
    vol = uniform_dvh_result.total_volume_cc
    expected = 60.0 * vol
    assert abs(metrics["integral_dose_gy_cm3"] - expected) < 0.5


def test_plan_quality_flag_d95_warning():
    rows = [
        {
            "AnonPatientID": "P1",
            "site_params_key": "HN",
            "technique_profile": "conventional",
            "structure": "PTV",
            "structure_role": "TARGET",
            "prescription_gy": 60.0,
            "D95_gy": 50.0,
            "HI": 0.05,
        }
    ]
    flags = evaluate_plan_quality_flags(rows)
    assert not flags.empty
    assert flags.iloc[0]["metric"] == "D95_gy"
    assert flags.iloc[0]["Severity"] == "WARNING"
