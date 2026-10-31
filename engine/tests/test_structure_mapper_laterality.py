"""The fuzzy mapper must never invent a laterality the source name does not carry.

Defect #21. ``canon_target`` falls back to ``difflib.get_close_matches(..., cutoff=0.88)``. For an
unlateralised paired-organ name the ``_L`` and ``_R`` keys score IDENTICALLY, and
``get_close_matches`` breaks the tie lexicographically, so ``_R`` always won: the side was chosen
by the alphabet, not by anatomy.

Before the fix, a side-less ``Submandibular`` became ``Submandibular_R`` and a side-less
``Parotid`` became ``Parotid_R``, both at confidence LOW, and that
LOW never reached any output. In one subject the contours carried ``SubmandL-PTV`` and no
``SubmandR-PTV`` -- the only laterality evidence present pointed LEFT and the engine reported RIGHT.

``config/structure_aliases.py`` already documents the policy ("Deliberately does NOT add
merged/bilateral names (e.g. 'parotids') to single-sided canonicals"). The alias table honoured it;
the fuzzy branch bypassed it. ``Parotids`` escaped only because its ratio was 0.875 against a 0.88
cutoff -- a margin of 0.005. These tests make the policy hold by construction.
"""

from __future__ import annotations

import pytest

from dicom_io.structure_mapper import canon_target, normalize_to_tg263

pytestmark = pytest.mark.unit


# --------------------------------------------------------------- the guard itself

@pytest.mark.parametrize("raw", ["Submandibular", "Parotid", "Parotid_Bilat", "Parotids",
                                 "submandibular", "PAROTID"])
def test_unlateralised_name_never_gains_a_side(raw):
    """The core claim. Reverting the guard makes every one of these return a ``_L``/``_R`` key."""
    got = canon_target(raw, None)["canonical"]
    assert not got.endswith(("_L", "_R")), (
        f"{raw!r} asserts no side but resolved to {got!r} -- a fabricated laterality"
    )


def test_the_tie_is_what_made_r_always_win():
    """Documents the mechanism: both sides score the same, so the winner was alphabetical."""
    from difflib import SequenceMatcher

    from config.tg263_aliases import TG263_ALIASES
    from dicom_io.structure_mapper import normalise_name

    n = normalise_name("Submandibular")
    scores = {
        k: SequenceMatcher(None, n, normalise_name(k)).ratio()
        for k in TG263_ALIASES
        if k in ("Submandibular_L", "Submandibular_R")
    }
    assert len(scores) == 2
    assert scores["Submandibular_L"] == scores["Submandibular_R"], (
        "the two sides must tie exactly -- that tie is the defect"
    )
    assert min(scores.values()) > 0.88, "and both must clear the cutoff"


# --------------------------------------------------------------- what must keep working

@pytest.mark.parametrize(("raw", "expect"), [
    # a curated exact alias asserting the side is a human decision, not an invention
    ("Submandibular_R", "Submandibular_R"),
    ("Submandibular_L", "Submandibular_L"),
    ("SubmandL", "Submandibular_L"),
    ("SubmandR", "Submandibular_R"),
    ("Parotid_L", "Parotid_L"),
    ("Parotid_R", "Parotid_R"),
    # abbreviations that carry the side, matched by curated alias rather than fuzzily
    ("FemHead_R", "FemoralHead_R"),
    ("FemHead_L", "FemoralHead_L"),
    ("Femur_L", "FemoralHead_L"),
    # the side stated in words or as an Lt/Rt prefix
    ("Lt Parotid", "Parotid_L"),
    ("leftparotid", "Parotid_L"),
])
def test_a_name_that_does_assert_a_side_still_resolves(raw, expect):
    """The guard must not become a blanket refusal of lateralised organs."""
    assert canon_target(raw, None)["canonical"] == expect


def test_unlateralised_names_are_still_reported_not_silently_dropped():
    """A refusal must stay visible: unmapped, category UNKNOWN, confidence LOW."""
    r = canon_target("Submandibular", None)
    assert r["category"] == "UNKNOWN"
    assert r["confidence"] == "LOW"
    assert normalize_to_tg263("Submandibular")["mapped"] is False


def test_non_paired_organs_are_untouched_by_the_guard():
    for raw, expect in (("SpinalCord", "SpinalCord"), ("Mandible", "Mandible"),
                        ("OralCavity", "OralCavity"), ("Larynx", "Larynx")):
        assert canon_target(raw, None)["canonical"] == expect


# --------------------------------------------------------------- the constrictor alias

def test_pharynxconst_reaches_its_organ_key():
    """``PharynxConst`` is a common export spelling; its fuzzy ratio is 0.80,
    under the cutoff, so it resolved to UNKNOWN and its parameters were unreachable."""
    r = canon_target("PharynxConst", None)
    assert r["canonical"] == "PharynxConstrictor"
    assert r["category"] == "OAR"
