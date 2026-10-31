"""Tier A defects #22, #9 and #19 — reachability against real names, and PRV expansions.

Each test fails on v1.4.0 (``ffd69ef``) and passes after the fix.
"""

from __future__ import annotations

import pytest

from config.site_ntcp_params import (
    default_organ_keys,
    organ_key_corpus_reachability,
    read_contour_name_corpus,
)
from dicom_io.structure_mapper import canon_target

# --------------------------------------------------------------- #22 a corpus, not a tautology


def test_defect_22_the_corpus_exists_and_holds_real_names() -> None:
    names = read_contour_name_corpus()
    assert len(names) > 400, len(names)
    # spellings a planning system really writes, not the canonical forms
    assert "PharynxConst" in names
    assert "SpinalCord_05" in names
    assert "Chiasm" in names


def test_defect_22_pharynxconst_resolves_to_the_constrictor() -> None:
    """#22: a common export spelling for the constrictors. Delete its alias and this must fail."""
    mapped = canon_target("PharynxConst")
    assert mapped["canonical"] == "PharynxConstrictor"
    assert mapped["category"] == "OAR"
    assert "PharynxConstrictor" in default_organ_keys()["HN"]


#: Organ keys the corpus cannot reach, and why. The corpus is weighted towards head-and-neck and
#: pelvic structure names, so a thoracic, hepatic or deep-brain organ simply does not appear in
#: it; that is a gap in the corpus, not in the alias table. The salivary glands are a different
#: case: the corpus holds only side-less and bilateral spellings for them ("Parotid", "Parotids",
#: "Submandibular"), and a side-less name must NOT be given a side -- doing so is what defect #21
#: was. Those four keys are unreachable from such names by design, which is the correct outcome
#: and not something an alias can fix.
NOT_IN_CORPUS_SITE_NOT_COVERED = {
    "ChestWall",
    "Duodenum",
    "Heart",
    "Hippocampus_L",
    "Hippocampus_R",
    "LAD",
    "Liver",
    "Lung_L",
    "Lung_R",
    "NormalBrain",
    "Rib",
    "Stomach",
}
NOT_IN_CORPUS_SIDELESS_IN_THE_DATA = {
    "Parotid_L",
    "Parotid_R",
    "Submandibular_L",
    "Submandibular_R",
}


def test_defect_22_every_covered_organ_key_is_reached_by_a_real_name() -> None:
    """The check that the v1.4.0 tautology could not make: real names, not the table itself."""
    reach = organ_key_corpus_reachability()
    unreached = {k for k, names in reach.items() if not names}
    assert unreached == (
        NOT_IN_CORPUS_SITE_NOT_COVERED | NOT_IN_CORPUS_SIDELESS_IN_THE_DATA
    ), unreached
    # and the ones that are covered really are reached
    assert len(reach) - len(unreached) == 21


@pytest.mark.parametrize(
    "name, key",
    [
        ("PharynxConst", "PharynxConstrictor"),
        ("Chiasm", "OpticChiasm"),
        ("Lungs", "LungTotal"),
        ("FemHead_L", "FemoralHead_L"),
        ("FemHead_R", "FemoralHead_R"),
        ("RECTUM", "Rectum"),
        ("URETHRA", "Urethra"),
        ("BLADDER", "Bladder"),
    ],
)
def test_defect_22_named_variants_from_the_corpus_reach_their_organ(name: str, key: str) -> None:
    """Each of these is a spelling a planning system actually wrote in one of the cohorts."""
    mapped = canon_target(name)
    assert mapped["canonical"] == key, mapped
    assert mapped["category"] == "OAR"
    assert not mapped.get("is_prv")


def test_defect_22_a_sideless_gland_is_still_not_given_a_side() -> None:
    """The corpus contains these spellings; giving them a side would reintroduce defect #21."""
    for name in ("Parotid", "Parotids", "Submandibular"):
        mapped = canon_target(name)
        assert mapped["canonical"] not in {
            "Parotid_L",
            "Parotid_R",
            "Submandibular_L",
            "Submandibular_R",
        }, (name, mapped)


def test_defect_22_the_import_time_check_now_also_rejects_a_prv_key() -> None:
    import inspect

    from config import site_ntcp_params

    src = inspect.getsource(site_ntcp_params._validate_default_organ_keys_reachable)
    assert "is_prv" in src


# ------------------------------------------------------- #9 / #19 PRV expansions are their own


@pytest.mark.parametrize(
    "name, canonical, organ",
    [
        ("SpinalCord_05", "SpinalCord_PRV", "SpinalCord"),
        ("BrainStem_03", "BrainStem_PRV", "BrainStem"),
        ("BrainStem_PRV", "BrainStem_PRV", "BrainStem"),
        ("PRV_Cord", "SpinalCord_PRV", "SpinalCord"),
        ("spinalcordprv", "SpinalCord_PRV", "SpinalCord"),
        ("Cord_PRV5", "SpinalCord_PRV", "SpinalCord"),
        ("Rectum PRV", "Rectum_PRV", "Rectum"),
        ("URETHRA_PRV02", "Urethra_PRV", "Urethra"),
        ("BladderPRV", "Bladder_PRV", "Bladder"),
        ("Parotid_L_PRV", "Parotid_L_PRV", "Parotid_L"),
    ],
)
def test_defect_9_19_a_prv_gets_its_own_key(name: str, canonical: str, organ: str) -> None:
    """#9/#19: SpinalCord_05 and BrainStem_03 came back as the organ itself.

    The organ and its PRV then share one ``structure`` label, so which of them was scored changed
    the written number: a PRV's DVH is colder and larger than its organ's.
    """
    mapped = canon_target(name)
    assert mapped["canonical"] == canonical, mapped
    assert mapped["is_prv"] is True
    assert mapped["prv_of"] == organ
    assert mapped["category"] == "OAR"


@pytest.mark.parametrize(
    "name", ["SpinalCord", "BrainStem", "Rectum", "Urethra", "Bladder", "Parotid_L", "Larynx"]
)
def test_defect_9_19_the_organ_itself_is_not_flagged_as_a_prv(name: str) -> None:
    mapped = canon_target(name)
    assert mapped["canonical"] == name
    assert mapped["is_prv"] is False


def test_defect_9_19_no_prv_key_has_organ_parameters() -> None:
    """A PRV must never be scored with the organ's published parameters."""
    keys = {k for organs in default_organ_keys().values() for k in organs}
    assert not {k for k in keys if k.endswith("_PRV")}, keys


def test_defect_9_19_a_prv_cannot_reach_an_organ_key() -> None:
    """The point of the fix: no PRV name may canonicalise onto a scored organ."""
    for name in read_contour_name_corpus():
        mapped = canon_target(name)
        if mapped.get("is_prv"):
            assert mapped["canonical"].endswith("_PRV"), (name, mapped)


def test_defect_9_19_a_target_dose_level_is_not_a_prv_margin() -> None:
    """``PTV70`` ends in digits but the number is a dose, not a margin.

    ``ITV50`` is included because the PRV detector must leave it alone too. It comes back
    UNKNOWN rather than TARGET, which is a separate, pre-existing gap: the dose-embedded-name
    pass in ``_lookup_alias`` covers the gtv/ctv/ptv prefixes and not itv. Out of scope here;
    recorded so it is not mistaken for something this fix caused.
    """
    for name in ("PTV70", "PTV 46GY", "CTV63", "GTV1", "ITV50"):
        mapped = canon_target(name)
        assert mapped["is_prv"] is False, (name, mapped)
    for name in ("PTV70", "PTV 46GY", "CTV63", "GTV1"):
        assert canon_target(name)["category"] == "TARGET", name
    assert canon_target("ITV50")["category"] == "UNKNOWN"
