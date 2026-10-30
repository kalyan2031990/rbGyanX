"""Tier A defect #20 — the UTCP OAR map, and refusing a partial P+.

Each test fails on v1.4.0 (``ffd69ef``) and passes after the fix.
"""

from __future__ import annotations

import math

import pytest

from config.site_ntcp_params import load_site_ntcp_params
from dicom_io.structure_mapper import canon_target
from radiobiology.utcp import (
    UTCP_INCOMPLETE_OAR_SET,
    UTCP_OAR_MAP,
    attach_utcp_to_tcp_results,
    compute_utcp,
    resolve_oar_map,
)

#: Which NTCP parameter block backs each UTCP site. PELVIS has none at all.
NTCP_BLOCK_FOR_UTCP_SITE = {
    "BRAIN_GBM": "BRAIN_GBM",
    "BRAIN_METS": "BRAIN_METS",
    "HN": "HN",
    "LUNG_CONV": "LUNG",
    "LUNG_SBRT": "LUNG",
    "PROSTATE": "PROSTATE",
    "PELVIS": "PELVIS",
    "LIVER": "LIVER",
    "BREAST": "BREAST",
}


# ------------------------------------------------------------- the map resolves to canonical keys


def test_defect_20_every_map_entry_canonicalises_to_itself_after_resolution() -> None:
    """#20: the map said ``Brainstem``; the vocabulary everywhere else says ``BrainStem``."""
    for site, entries in UTCP_OAR_MAP.items():
        for entry in resolve_oar_map(entries):
            name = entry["oar"]
            mapped = canon_target(name)
            assert mapped["canonical"] == name, (site, name, mapped)
            assert mapped["category"] == "OAR", (site, name, mapped)


def test_defect_20_brainstem_is_reached_at_all_three_brain_and_hn_sites() -> None:
    """The named instance of the defect: the brainstem was missing from P+ at three sites."""
    for site in ("HN", "BRAIN_GBM", "BRAIN_METS"):
        resolved = {e["oar"] for e in resolve_oar_map(UTCP_OAR_MAP[site])}
        assert "BrainStem" in resolved, site
        assert "Brainstem" not in resolved, site


def test_defect_20_breast_no_longer_counts_one_lung_twice() -> None:
    """``Lung_Ipsi`` and ``Lung_Contra`` both canonicalise to ``LungTotal``."""
    listed = UTCP_OAR_MAP["BREAST"]
    resolved = resolve_oar_map(listed)
    assert len(listed) == 8
    assert len(resolved) == 7
    merged = next(e for e in resolved if e["oar"] == "LungTotal")
    assert merged["oar_listed"] == "Lung_Ipsi, Lung_Contra"
    # the conservative weight of the two is kept
    assert merged["severity_weight"] == pytest.approx(0.7)


def test_defect_20_every_resolved_key_is_reachable_from_a_contour_name() -> None:
    """A key no contour name can reach is a key whose NTCP never computes."""
    for site, entries in UTCP_OAR_MAP.items():
        for entry in resolve_oar_map(entries):
            name = entry["oar"]
            # the canonical key is itself a name the mapper accepts
            assert canon_target(name)["canonical"] == name, (site, name)
            # and so is the lower-case spelling a TPS is likely to export
            assert canon_target(name.lower())["canonical"] == name, (site, name.lower())


# ------------------------------------------------- the map vs the NTCP parameter library

#: OARs a site's UTCP map lists that its NTCP block cannot score. These are a real gap, not a
#: coding slip: supplying parameters for them is a scientific decision, so the inventory is
#: pinned here and any drift from it fails this test.
KNOWN_UNSCORABLE = {
    "BRAIN_METS": {"NormalBrain"},
    "LUNG_CONV": {"SpinalCord"},
    "LUNG_SBRT": {"SpinalCord"},
    "PROSTATE": {"SpinalCord"},
    "LIVER": {"Esophagus"},
    "PELVIS": {
        "Bladder",
        "BowelBag",
        "FemoralHead_L",
        "FemoralHead_R",
        "Rectum",
        "SpinalCord",
    },
}


def test_defect_20_the_unscorable_oar_inventory_is_exactly_what_is_recorded() -> None:
    """P+ has been formed over a partial OAR set at five sites; this pins which."""
    found: dict[str, set[str]] = {}
    for site, entries in UTCP_OAR_MAP.items():
        block = NTCP_BLOCK_FOR_UTCP_SITE[site]
        library = set(load_site_ntcp_params(block).organs)
        gap = {e["oar"] for e in resolve_oar_map(entries)} - library
        if gap:
            found[site] = gap
    assert found == KNOWN_UNSCORABLE, found


def test_defect_20_hn_and_brain_gbm_are_fully_scorable() -> None:
    """After the canonicalisation fix these two sites can form a complete P+."""
    for site in ("HN", "BRAIN_GBM"):
        library = set(load_site_ntcp_params(NTCP_BLOCK_FOR_UTCP_SITE[site]).organs)
        assert {e["oar"] for e in resolve_oar_map(UTCP_OAR_MAP[site])} <= library, site


# ------------------------------------------------------------- a partial set is refused


def _hn_ntcp_rows(organs: list[str], ntcp: float = 0.1) -> list[dict]:
    return [
        {"AnonPatientID": "P1", "structure": organ, "NTCP_LKB_loglogit": ntcp}
        for organ in organs
    ]


_HN_FULL = [
    "SpinalCord",
    "BrainStem",
    "Parotid_L",
    "Parotid_R",
    "Mandible",
    "PharynxConstrictor",
    "OralCavity",
    "Larynx",
]


def test_defect_20_a_complete_oar_set_gives_a_number() -> None:
    result = compute_utcp(
        {"AnonPatientID": "P1", "TCP_Poisson": 0.8}, _hn_ntcp_rows(_HN_FULL), "HN"
    )
    assert result.reason == ""
    assert result.n_oars_missing == 0
    assert result.n_oars_scored == 8
    assert pytest.approx(0.8 * 0.9**8) == result.UTCP


def test_defect_20_a_missing_oar_refuses_with_the_reason_and_the_names() -> None:
    """#20: a dropped OAR used to raise P+ silently, with only a warning string beside it."""
    result = compute_utcp(
        {"AnonPatientID": "P1", "TCP_Poisson": 0.8},
        _hn_ntcp_rows([o for o in _HN_FULL if o != "Larynx"]),
        "HN",
    )
    assert math.isnan(result.UTCP)
    assert math.isnan(result.UTCP_weighted)
    assert result.reason == UTCP_INCOMPLETE_OAR_SET
    assert result.missing_OAR_names == ["Larynx"]
    assert result.n_oars_scored == 7


def test_defect_20_allow_partial_computes_it_and_still_names_the_gap() -> None:
    result = compute_utcp(
        {"AnonPatientID": "P1", "TCP_Poisson": 0.8},
        _hn_ntcp_rows([o for o in _HN_FULL if o != "Larynx"]),
        "HN",
        allow_partial=True,
    )
    assert pytest.approx(0.8 * 0.9**7) == result.UTCP
    assert result.reason == UTCP_INCOMPLETE_OAR_SET
    assert result.missing_OAR_names == ["Larynx"]


def test_defect_20_the_brainstem_now_enters_the_product() -> None:
    """Before the fix, rows named BrainStem never matched the map's 'Brainstem'."""
    result = compute_utcp(
        {"AnonPatientID": "P1", "TCP_Poisson": 0.8}, _hn_ntcp_rows(_HN_FULL), "HN"
    )
    assert "BrainStem" in result.scored_OAR_names
    assert "BrainStem" not in result.missing_OAR_names


def test_defect_20_an_unknown_site_refuses_rather_than_returning_tcp() -> None:
    """With no OAR map the product is empty, so P+ would have equalled TCP exactly."""
    result = compute_utcp(
        {"AnonPatientID": "P1", "TCP_Poisson": 0.8}, _hn_ntcp_rows(_HN_FULL), "NOSUCHSITE"
    )
    assert math.isnan(result.UTCP)
    assert result.reason == UTCP_INCOMPLETE_OAR_SET


# ------------------------------------------- the counts are on every row, not just some


def test_defect_20_every_tcp_row_carries_the_scored_and_missing_counts() -> None:
    """#20: a row with no matching NTCP patient used to get no UTCP columns at all."""
    tcp_rows = [
        {"AnonPatientID": "P1", "TCP_Poisson": 0.8},
        {"AnonPatientID": "P2", "TCP_Poisson": 0.7},  # no NTCP rows for this patient
    ]
    attach_utcp_to_tcp_results(tcp_rows, _hn_ntcp_rows(_HN_FULL), "HN")
    for row in tcp_rows:
        assert "UTCP_OARs_scored" in row, row
        assert "UTCP_OARs_missing" in row, row
        assert "UTCP_reason" in row, row
    assert tcp_rows[0]["UTCP_OARs_missing"] == 0
    assert tcp_rows[0]["UTCP_reason"] == ""
    assert tcp_rows[1]["UTCP_OARs_scored"] == 0
    assert tcp_rows[1]["UTCP_OARs_missing"] == 8
    assert tcp_rows[1]["UTCP_reason"] == UTCP_INCOMPLETE_OAR_SET
    assert math.isnan(tcp_rows[1]["UTCP"])
