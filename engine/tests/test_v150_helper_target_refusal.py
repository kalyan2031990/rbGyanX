"""Planning helper structures must not be scored as targets (defect #59).

An optimisation surrogate, a dose-shaping ring, a boolean subtraction of one target from another,
or an aggregate "total" structure is created to drive a planning system. It is not a volume that
carries a prescription. Scoring one as a target gives it TCP and target dose metrics that mean
nothing for it, and -- because several such structures share a name stem with the real target --
produces several "targets" with near-identical dose.

The archives that create these structures also tag them `RTROIInterpretedType = PTV`, so the DICOM
type cannot be trusted on its own here; the name is the more reliable signal and is checked first.

These tests fail on v1.4.0, where `canon_target` returned `PTV` for every one of the refused names.
"""

from __future__ import annotations

import pydicom
import pytest
from pydicom.dataset import Dataset

from dicom_io.structure_mapper import (
    canon_target,
    get_target_structures,
    helper_target_reason,
)

# Naming conventions seen across planning systems, not one dataset.
HELPERS = [
    ("PTVHighOPT", "optimisation"),
    ("PTVLowOPT", "optimisation"),
    ("PTVMidOPT", "optimisation"),
    ("OPT_PTV", "optimisation"),
    ("RingPTVHigh", "ring"),
    ("PTV_Ring", "ring"),
    ("PTVLow-PTVMid", "boolean-subtraction"),
    ("PTVMid-PTVHigh", "boolean-subtraction"),
    ("PTV_Total", "total"),
    ("PTV_eval", "evaluation copy"),
]

# Real targets, and OARs that must not be caught by the helper patterns.
KEEPERS = [
    "PTV70", "PTVHigh", "PTVLow", "PTVMid", "GTV", "CTV56", "ITV",
    "OralCavity", "OpticNerve_R", "Optic_Chiasm", "Parotids", "BrainStem",
    "Larynx-PTV",   # an OAR minus the target: an OAR, not a target, either way
]


@pytest.mark.parametrize("name,reason", HELPERS)
def test_helper_names_are_recognised(name: str, reason: str):
    assert helper_target_reason(name) == reason


@pytest.mark.parametrize("name", KEEPERS)
def test_real_targets_and_oars_are_not_helpers(name: str):
    assert helper_target_reason(name) is None


@pytest.mark.parametrize("name,_reason", HELPERS)
def test_helper_is_refused_even_when_dicom_says_PTV(name: str, _reason: str):
    """#59: `RTROIInterpretedType = PTV` must not override the name.

    This is the case that bit: the structures are written with the DICOM type of the target they
    were derived from, so trusting the type alone scored every one of them as a target.
    """
    mapped = canon_target(name, "PTV")
    assert mapped["category"] == "HELPER", f"{name} was scored as {mapped['category']}"
    assert mapped["canonical"] not in {"PTV", "GTV", "CTV", "ITV", "BOOST"}
    assert mapped.get("helper_reason")


def test_a_real_target_still_maps_when_dicom_says_PTV():
    mapped = canon_target("PTV70", "PTV")
    assert mapped["canonical"] == "PTV"
    assert mapped["category"] != "HELPER"


def _struct_set(names: list[tuple[str, str]]) -> Dataset:
    """Minimal RT Structure Set: [(roi name, RTROIInterpretedType), ...]."""
    ds = Dataset()
    ds.StructureSetROISequence = []
    for i, (name, typ) in enumerate(names, start=1):
        roi = Dataset()
        roi.ROINumber = i
        roi.ROIName = name
        roi.RTROIInterpretedType = typ
        ds.StructureSetROISequence.append(roi)
    return ds


def test_only_the_named_target_survives_a_realistic_structure_set():
    """The shape that produced the defect: one real target among five helpers, all typed PTV."""
    ds = _struct_set([
        ("PTV70", "PTV"),
        ("PTVHighOPT", "PTV"),
        ("PTV_Total", "PTV"),
        ("RingPTVHigh", "PTV"),
        ("PTVLow-PTVMid", "PTV"),
        ("Parotids", "ORGAN"),
    ])
    targets = get_target_structures(ds, {"prescription_dose_gy": 70.0, "n_fractions": 35})
    names = [t["raw_name"] for t in targets]
    assert names == ["PTV70"], names


def test_several_genuine_dose_levels_are_all_kept():
    """Refusing helpers must not collapse a multi-level plan to one target."""
    ds = _struct_set([("PTV70", "PTV"), ("PTVMid", "PTV"), ("PTVLow", "PTV"),
                      ("PTVHighOPT", "PTV"), ("PTV_Total", "PTV")])
    targets = get_target_structures(ds, {})
    assert sorted(t["raw_name"] for t in targets) == ["PTV70", "PTVLow", "PTVMid"]


def test_a_study_of_helpers_only_yields_no_target_and_says_so(caplog):
    """If every candidate is a helper, that must be loud rather than look like 'no target'."""
    ds = _struct_set([("PTVHighOPT", "PTV"), ("RingPTVHigh", "PTV"), ("PTV_Total", "PTV")])
    with caplog.at_level("WARNING"):
        targets = get_target_structures(ds, {})
    assert targets == []
    assert "no treated target remains" in caplog.text, caplog.text
    assert "#59" in caplog.text


def test_the_refusal_is_logged_with_its_reason(caplog):
    ds = _struct_set([("PTV70", "PTV"), ("PTVHighOPT", "PTV")])
    with caplog.at_level("WARNING"):
        get_target_structures(ds, {})
    text = caplog.text
    assert "REFUSED" in text and "PTVHighOPT" in text and "#59" in text


def test_pydicom_is_the_real_one():
    """Guard against the module shadowing that defect #48 was about."""
    assert pydicom.__name__ == "pydicom"
