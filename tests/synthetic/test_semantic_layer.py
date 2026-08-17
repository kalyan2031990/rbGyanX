"""
Phase 3 acceptance — semantic layer (structure mapping, site detection, NTCP applicability).

Synthetic ROI names only (anatomical labels, no patient data). Proves:
  3.1 every ROI is mapped or recorded unmapped-with-raw-name; mapping rate is reported;
  3.2 HN/lung/brain/breast/prostate/pelvis/liver detect, and ambiguity yields UNKNOWN/LOW + evidence;
  3.3 a TARGET never receives NTCP; a merged-bilateral ROI against single-gland params is flagged.
"""

from __future__ import annotations

import pytest

from dicom_io.site_detector import detect_site
from dicom_io.structure_mapper import canon_target, get_oar_structures, get_target_structures
from dicom_io.structure_mapping_report import aggregate_reports, structure_mapping_report
from radiobiology.ntcp_applicability import (
    classify_definition,
    evaluate_ntcp_applicability,
    ntcp_allowed,
)

pytestmark = pytest.mark.unit


class _ROI:
    def __init__(self, num, name, rtype=""):
        self.ROINumber = num
        self.ROIName = name
        self.RTROIInterpretedType = rtype


class _Struct:
    def __init__(self, items):
        self.StructureSetROISequence = [_ROI(i + 1, n, t) for i, (n, t) in enumerate(items)]


# ---------------------------------------------------------------- 3.1 mapping report


def test_report_maps_all_and_lists_unmapped():
    st = _Struct(
        [
            ("PTV70", "PTV"),
            ("Parotid_L", "ORGAN"),
            ("Larynx", "ORGAN"),
            ("ZZ_WeirdBlob", "ORGAN"),
        ]
    )
    rep = structure_mapping_report(st)
    assert rep["total"] == 4  # nothing silently dropped
    assert len(rep["rows"]) == 4
    assert "ZZ_WeirdBlob" in rep["unmapped_raw_names"]
    assert rep["mapped"] >= 2 and 0.0 < rep["mapping_rate"] <= 1.0


@pytest.mark.parametrize("raw", ["Lt Parotid", "LEFT PAROTID", "parotid-l", "Parotid_L"])
def test_laterality_variants_map_to_parotid_l(raw):
    assert canon_target(raw)["canonical"] == "Parotid_L"


def test_aggregate_reports_unions_unmapped():
    a = structure_mapping_report(_Struct([("ZZ_Blob", "ORGAN"), ("Parotid_L", "ORGAN")]))
    b = structure_mapping_report(_Struct([("ZZ_Blob", "ORGAN"), ("QQ_Other", "ORGAN")]))
    agg = aggregate_reports([a, b])
    assert agg["total"] == 4
    assert agg["unmapped_raw_names"]["ZZ_Blob"] == 2  # seen in both


# ---------------------------------------------------------------- 3.2 site detection


@pytest.mark.parametrize(
    "label,expected",
    [
        ("HN_chemoRT_70Gy", "HN"),
        ("LUNG_SBRT", "LUNG"),
        ("BrainMets_WBRT", "BRAIN"),
        ("Breast_LtWholeBreast", "BREAST"),
        ("Prostate_78Gy", "PROSTATE"),
        ("Pelvis_Cervix_EBRT", "PELVIS"),
        ("Liver_SBRT_HCC", "LIVER"),
    ],
)
def test_site_detected_from_label(label, expected):
    out = detect_site({"plan_label": label}, [])
    assert out["site"] == expected
    assert out["evidence"]  # evidence is always recorded


def test_ambiguous_plan_is_unknown_or_low_with_evidence():
    # No anatomical label, curative-range dose → explicitly ambiguous
    out = detect_site(
        {
            "plan_label": "",
            "prescription_dose_gy": 70.0,
            "n_fractions": 35,
            "dose_per_fraction_gy": 2.0,
        },
        [{"canonical": "PTV"}],
    )
    assert out["site"] == "UNKNOWN" or out["confidence"] == "LOW"
    assert any("ambiguous" in e.lower() for e in out["evidence"])


# ---------------------------------------------------------------- 3.3 NTCP applicability


def test_targets_excluded_from_oar_list():
    st = _Struct([("PTV70", "PTV"), ("GTV", "GTV"), ("Parotid_L", "ORGAN")])
    oar_names = {o["canonical"] for o in get_oar_structures(st)}
    target_names = {t["canonical"] for t in get_target_structures(st, {})}
    assert "PTV" in target_names and "GTV" in target_names
    assert not (oar_names & {"PTV", "GTV", "CTV", "ITV", "BOOST"})  # no target ever in the OAR list


@pytest.mark.parametrize(
    "category,code",
    [
        ("TARGET", "NTCP_ON_TARGET_BLOCKED"),
        ("SUPPORT", "NTCP_ON_SUPPORT_BLOCKED"),
        ("UNKNOWN", "NTCP_ON_UNKNOWN_BLOCKED"),
    ],
)
def test_ntcp_blocked_off_oar(category, code):
    allowed, reason = ntcp_allowed(category)
    assert allowed is False and reason == code


def test_single_gland_parotid_is_ok():
    v = evaluate_ntcp_applicability("Parotid_L", "OAR", "Parotid_L")
    assert v["allowed"] and v["structure_definition"] == "single_gland"
    assert v["definition_ok"] is True and v["reason_codes"] == []


def test_merged_bilateral_parotid_is_flagged():
    v = evaluate_ntcp_applicability("Parotid_L", "OAR", "Parotids")
    assert v["structure_definition"] == "merged_bilateral"
    assert v["definition_ok"] is False
    assert "NTCP_DEFINITION_MISMATCH" in v["reason_codes"]


def test_sideless_parotid_is_unverified():
    v = evaluate_ntcp_applicability("Parotid", "OAR", "Parotid")
    assert v["definition_ok"] is None
    assert "NTCP_DEFINITION_UNVERIFIED" in v["reason_codes"]


def test_nonpaired_organ_has_no_definition_flag():
    v = evaluate_ntcp_applicability("SpinalCord", "OAR", "SpinalCord")
    assert v["definition_ok"] is True and v["reason_codes"] == []


def test_classify_definition_direct():
    assert classify_definition("Parotid_L", "Lt Parotid") == "single_gland"
    assert classify_definition("Parotid_L", "Bilateral Parotids") == "merged_bilateral"
    assert classify_definition("Heart", "Heart") == "unspecified"
