"""
Phase-2 tests for the real-data DVH + feature front-end.

Uses the analytic synthetic DICOM-RT factory (uniform dose grid) so DVH metrics
have an exact closed form, independent of any real patient data:

  1. round-trip: factory -> extractor -> tidy feature row;
  2. closed form: uniform D0 -> Dmean = Dmax = D95 = D2 = gEUD = D0, HI=0, CI=1,
     BED/EQD2 from the LQ formula;
  3. NaN-not-zero: empty / out-of-grid ROI yields NaN metrics, never 0.0.
"""

from __future__ import annotations

import math

import pytest

from dicom_io.cohort_features import build_patient_features
from dicom_io.dvh_extractor import DVHExtractor
from tests.synthetic.dicom_rt_factory import SyntheticROI, build_rt_triple

D0 = 70.0
NFX = 35
TOL = 0.1  # dicompyler-core bins dose at ~0.01 Gy


def _dicom_stack_ok() -> bool:
    """True iff dicompyler-core can actually consume pydicom datasets (pydicom<3.0)."""
    rs, rd, rp = build_rt_triple(dose_gy=D0, n_fractions=NFX)
    res = DVHExtractor().extract_all_dvhs(
        rd, rs, [{"roi_number": 1, "raw_name": "PTV70", "roi_type": "PTV"}]
    )
    dvh = next(iter(res.values()))
    return dvh.quality_flag == "OK" and not math.isnan(dvh.dmean_gy)


pytestmark = pytest.mark.skipif(
    not _dicom_stack_ok(),
    reason="dicompyler-core/pydicom DICOM stack not functional (needs pydicom<3.0)",
)


def test_synthetic_factory_roundtrip():
    rs, rd, rp = build_rt_triple(patient_id="SYN-RT", dose_gy=D0, n_fractions=NFX)
    row = build_patient_features(rs, rd, rp, patient_id="SYN-RT")

    assert row["patient_id"] == "SYN-RT"
    assert row["n_fractions"] == NFX
    assert row["dose_summation_type"] == "PLAN"
    assert row["approval_status"] == "UNAPPROVED"
    # PTV target block present and populated
    assert row["PTV_name"] == "PTV70"
    assert row["PTV_volume_cc"] > 0
    # Dysphagia-OAR columns exist for the full canonical set (NaN if absent)
    for canon in ("PharynxConstrictor", "Larynx", "OralCavity", "SpinalCord"):
        assert f"{canon}_Dmean_gy" in row


def test_uniform_dose_closed_form():
    rs, rd, rp = build_rt_triple(patient_id="SYN-CF", dose_gy=D0, n_fractions=NFX)
    row = build_patient_features(rs, rd, rp, patient_id="SYN-CF")

    # Uniform dose => every PTV percentile dose equals D0.
    for key in ("PTV_Dmean_gy", "PTV_D95_gy", "PTV_D2_gy", "PTV_D98_gy", "PTV_gEUD_gy"):
        assert abs(row[key] - D0) < TOL, f"{key}={row[key]}"

    # Perfect homogeneity / coverage.
    assert abs(row["PTV_HI"]) < 0.02
    assert abs(row["PTV_CI"] - 1.0) < 0.05

    # BED / EQD2 match the LQ closed form at the realised mean dose.
    dmean = row["PTV_Dmean_gy"]
    dpf = dmean / NFX
    bed_expected = dmean * (1.0 + dpf / 10.0)
    eqd2_expected = dmean * (dpf + 10.0) / (2.0 + 10.0)
    assert abs(row["PTV_BED_gy"] - bed_expected) < 1e-3
    assert abs(row["PTV_EQD2_gy"] - eqd2_expected) < 1e-3

    # In-grid OAR (Larynx) sees the same uniform dose.
    assert abs(row["Larynx_Dmean_gy"] - D0) < TOL
    assert abs(row["Larynx_gEUD_gy"] - D0) < TOL


def test_nan_not_zero_on_empty_roi():
    # ROI placed entirely outside the dose grid -> empty DVH.
    rois = [
        SyntheticROI("PTV70", "PTV", 15.0, 45.0, 15.0, 45.0, 0.0, 27.0),
        SyntheticROI("Larynx", "ORGAN", 500.0, 530.0, 500.0, 530.0, 0.0, 9.0),
    ]
    rs, rd, rp = build_rt_triple(patient_id="SYN-NAN", dose_gy=D0, n_fractions=NFX, rois=rois)

    # Direct extractor contract on the out-of-grid ROI.
    res = DVHExtractor().extract_all_dvhs(
        rd, rs, [{"roi_number": 2, "raw_name": "Larynx", "roi_type": "ORGAN"}]
    )
    larynx = next(iter(res.values()))
    metrics = DVHExtractor().compute_dose_metrics(larynx, prescription_gy=D0)
    dmean = float(metrics["Dmean_gy"])
    assert math.isnan(dmean)  # NaN, explicitly not the silent 0.0 of an empty DVH
    assert dmean != 0.0

    # And in the assembled row, the degenerate OAR is NaN, not 0.0.
    row = build_patient_features(rs, rd, rp, patient_id="SYN-NAN")
    assert math.isnan(float(row["Larynx_Dmean_gy"]))
    # A canonical OAR with no contour at all is also NaN (never silently 0.0).
    assert math.isnan(float(row["OralCavity_Dmean_gy"]))
