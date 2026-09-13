"""
A2 — general, reusable interfaces (site-/endpoint-agnostic), tested on synthetic data.

Proves the tool runs on *any* user's data with no study coupling:
  1. structure normalisation maps arbitrary / centre-variant names (Rectum, Rectum_P, …);
  2. the DICOM feature front-end assembles OARs for any site via ``oar_specs``;
  3. the generic clinical-CSV loader validates the patient_id / endpoint[0/1] / covariate
     contract with clear errors;
  4. the benchmark is endpoint-agnostic and auto-discovers a new site's OAR features.

No real patient data; synthetic DICOM has an analytic uniform dose so metrics have a
closed form.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from dicom_io.cohort_features import (
    DEFAULT_OAR_SPECS,
    PROSTATE_OAR_SPECS,
    build_patient_features,
)
from dicom_io.dvh_extractor import DVHExtractor
from dicom_io.structure_mapper import canon_target
from tests.synthetic.dicom_rt_factory import SyntheticROI, build_rt_triple
from validation.clinical_cohort import load_clinical_csv
from validation.extval_benchmark import feature_matrix, run_benchmark

D0 = 74.0
NFX = 37
TOL = 0.1


# --------------------------------------------------------------------------- 1. names


@pytest.mark.parametrize(
    "raw,expected,category",
    [
        ("Rectum", "Rectum", "OAR"),
        ("Rectum_P", "Rectum", "OAR"),  # SPARK centre variant
        ("Rectum-P", "Rectum", "OAR"),
        ("RECTUM", "Rectum", "OAR"),
        ("Bladder", "Bladder", "OAR"),
        ("bladder_p", "Bladder", "OAR"),
        ("Parotid L", "Parotid_L", "OAR"),
        ("rt parotid", "Parotid_R", "OAR"),
        ("PTV70", "PTV", "TARGET"),
        ("CTV_high", "CTV", "TARGET"),
    ],
)
def test_structure_normalisation_arbitrary_names(raw, expected, category):
    res = canon_target(raw)
    assert res["canonical"] == expected, f"{raw!r} -> {res['canonical']}"
    assert res["category"] == category


def test_unmapped_structure_is_preserved_not_dropped():
    res = canon_target("SomeVendorSpecificBlob")
    assert res["category"] == "UNKNOWN"
    assert res["canonical"] == "SOMEVENDORSPECIFICBLOB"  # passthrough, never silently lost


# --------------------------------------------------------------------- 2. feature front-end


def _dicom_stack_ok() -> bool:
    rs, rd, rp = build_rt_triple(dose_gy=D0, n_fractions=NFX)
    res = DVHExtractor().extract_all_dvhs(
        rd, rs, [{"roi_number": 1, "raw_name": "PTV70", "roi_type": "PTV"}]
    )
    dvh = next(iter(res.values()))
    return dvh.quality_flag == "OK" and not math.isnan(dvh.dmean_gy)


_dicom = pytest.mark.skipif(
    not _dicom_stack_ok(),
    reason="dicompyler-core/pydicom DICOM stack not functional (needs pydicom<3.0)",
)


def _prostate_triple():
    rois = [
        SyntheticROI("PTV70", "PTV", 15.0, 45.0, 15.0, 45.0, 0.0, 27.0),
        SyntheticROI("Rectum_P", "ORGAN", 18.0, 36.0, 18.0, 36.0, 6.0, 21.0),
        SyntheticROI("Bladder", "ORGAN", 48.0, 66.0, 48.0, 66.0, 6.0, 21.0),
    ]
    return build_rt_triple(patient_id="SYN-PROS", dose_gy=D0, n_fractions=NFX, rois=rois)


@_dicom
def test_cohort_features_prostate_oar_spec():
    rs, rd, rp = _prostate_triple()
    row = build_patient_features(rs, rd, rp, patient_id="SYN-PROS", oar_specs=PROSTATE_OAR_SPECS)

    # Prostate OARs present and — for the in-grid uniform dose — equal to D0.
    assert abs(row["Rectum_Dmean_gy"] - D0) < TOL
    assert abs(row["Bladder_Dmean_gy"] - D0) < TOL
    # A spec'd OAR with no contour is NaN (never silently 0.0).
    assert math.isnan(float(row["Urethra_Dmean_gy"]))
    # No head & neck columns leaked into a prostate run.
    assert "Larynx_Dmean_gy" not in row
    assert "PharynxConstrictor_Dmean_gy" not in row


@_dicom
def test_cohort_features_default_is_head_and_neck():
    # Default (no oar_specs) keeps the head & neck dysphagia block — backward compatible.
    rs, rd, rp = build_rt_triple(patient_id="SYN-HN", dose_gy=D0, n_fractions=NFX)
    row = build_patient_features(rs, rd, rp, patient_id="SYN-HN")
    for spec in DEFAULT_OAR_SPECS:
        assert f"{spec.canonical}_Dmean_gy" in row
    assert "Rectum_Dmean_gy" not in row


# ------------------------------------------------------------------- 3. clinical-CSV loader


def _write_csv(tmp_path, text: str):
    p = tmp_path / "clin.csv"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_clinical_csv_valid(tmp_path):
    p = _write_csv(
        tmp_path,
        "patient_id,rectal_gi,age,sex\n" "P1,1,66,M\nP2,0,71,F\nP3,1,59,M\nP4,0,63,F\n",
    )
    cohort = load_clinical_csv(p, endpoint="rectal_gi", covariate_cols=["age", "sex"])
    assert cohort.n == 4
    assert cohort.n_events == 2
    assert abs(cohort.event_rate - 0.5) < 1e-9
    assert cohort.covariates == ["age", "sex"]


def test_load_clinical_csv_binary_word_tokens(tmp_path):
    p = _write_csv(tmp_path, "patient_id,tox\nP1,yes\nP2,no\nP3,Yes\nP4,NO\n")
    cohort = load_clinical_csv(p, endpoint="tox")
    assert set(cohort.df["tox"].unique()) == {0, 1}
    assert cohort.n_events == 2


def test_load_clinical_csv_rejects_nonbinary(tmp_path):
    p = _write_csv(tmp_path, "patient_id,grade\nP1,1\nP2,2\nP3,0\n")
    with pytest.raises(ValueError, match="non-binary"):
        load_clinical_csv(p, endpoint="grade")


def test_load_clinical_csv_requires_columns(tmp_path):
    p = _write_csv(tmp_path, "id,ev\nP1,1\nP2,0\n")
    with pytest.raises(ValueError, match="missing id column"):
        load_clinical_csv(p, endpoint="ev")
    with pytest.raises(ValueError, match="missing endpoint column"):
        load_clinical_csv(p, endpoint="nope", id_col="id")


def test_load_clinical_csv_duplicate_ids(tmp_path):
    p = _write_csv(tmp_path, "patient_id,ev\nP1,1\nP1,0\nP2,1\n")
    with pytest.raises(ValueError, match="not unique"):
        load_clinical_csv(p, endpoint="ev")


def test_load_clinical_csv_drops_missing_endpoint(tmp_path):
    p = _write_csv(tmp_path, "patient_id,ev\nP1,1\nP2,\nP3,0\n")
    cohort = load_clinical_csv(p, endpoint="ev")
    assert cohort.n == 2  # blank-endpoint row dropped
    assert cohort.n_events == 1


def test_load_clinical_csv_constant_endpoint_rejected(tmp_path):
    p = _write_csv(tmp_path, "patient_id,ev\nP1,1\nP2,1\nP3,1\n")
    with pytest.raises(ValueError, match="constant"):
        load_clinical_csv(p, endpoint="ev")


# ------------------------------------------------------- 4. endpoint-agnostic benchmark


def _prostate_cohort(n: int = 90, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    eqd2 = rng.normal(76, 4, n)
    rectum = rng.uniform(40, 70, n)
    bladder = rng.uniform(30, 65, n)
    p = 1.0 / (1.0 + np.exp(-0.1 * (rectum - 55)))  # more rectal GI at higher rectal dose
    y = (rng.uniform(size=n) < p * 0.5).astype(int)
    return pd.DataFrame(
        {
            "patient_id": [f"S{i:03d}" for i in range(n)],
            "centre": rng.choice(["c1", "c2", "c3", "c4"], size=n),
            "PTV_EQD2_gy": eqd2,
            "PTV_gEUD_gy": eqd2 - 1,
            "PTV_Dmean_gy": eqd2 + 1,
            "PTV_HI": rng.uniform(0.02, 0.1, n),
            "Rectum_Dmean_gy": rectum,
            "Rectum_gEUD_gy": rectum + 2,
            "Rectum_V50Gy_cc": rng.uniform(0, 20, n),
            "Bladder_Dmean_gy": bladder,
            "Bladder_gEUD_gy": bladder + 2,
            "PTV_dose_skewness": rng.normal(0, 1, n),
            "PTV_dose_kurtosis": rng.normal(0, 1, n),
            "PTV_dose_std_gy": rng.uniform(1, 4, n),
            "rectal_gi": y,  # arbitrary, non-HN endpoint name
        }
    )


def test_feature_matrix_discovers_non_hn_oars():
    df = _prostate_cohort(30)
    _, names = feature_matrix(df, "dvh")
    assert "Rectum_Dmean_gy" in names
    assert "Bladder_Dmean_gy" in names
    assert "Rectum_gEUD_gy" in names
    # It does not invent head & neck columns for a prostate cohort.
    assert "Larynx_Dmean_gy" not in names


def test_run_benchmark_arbitrary_endpoint():
    df = _prostate_cohort(90, seed=3)
    table, extras = run_benchmark(
        df, endpoint="rectal_gi", feature_set="dosiomics", lambda_phys_sweep=(), n_splits=3
    )
    assert extras["n"] == 90
    assert extras["events"] == int(df["rectal_gi"].sum())
    assert {"C1.T1", "C3.T4"}.issubset(set(table["tier"]))
    # The prostate OAR features reached the model (site-agnostic discovery).
    assert "Rectum_Dmean_gy" in extras["feature_names"]
    assert "Bladder_Dmean_gy" in extras["feature_names"]
