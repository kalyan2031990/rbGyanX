"""
Pack verification and the export gate (phase D).

A shipped pack whose values nobody has read against the papers is transcription, not
verification. Treating it as checked because it arrived in a JSON file would be exactly the
mistake this module exists to prevent, so an unverified SHIPPED_REFERENCE row is marked and
export-gated the same way a model-recalled row is.

The point of doing it this way rather than blocking the release: an unverified pack becomes
honest instead of absent, and it reuses the gate that already exists.
"""

from __future__ import annotations

import json

import pytest
from rbgyanx.ai.tools.literature import (
    ORIENTATION_NOTICE,
    UNVERIFIED_CITATION,
    ExportRefused,
    Provenance,
    compare_against_pack,
    export,
    load_all_packs,
    load_pack,
    render_table,
)


def _quantec():
    return next(p for p in load_all_packs() if p.pack_id == "quantec-2010")


def _quantec_rows():
    return compare_against_pack({"Dmean": 26.4}, _quantec(), organ="Parotid")


def _verified_pack(tmp_path, verified: bool):
    (tmp_path / "p.json").write_text(
        json.dumps(
            {
                "pack_id": "dept",
                "pack_version": "1.0",
                "maintainer_review": "complete" if verified else "pending: awaiting review",
                "entries": [
                    {
                        "organ": "Parotid_L",
                        "endpoint": "xerostomia",
                        "metric": "Dmean",
                        "comparator": "<",
                        "value": 25.0,
                        "units": "Gy",
                        "citation": "Departmental protocol v3",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_pack(tmp_path / "p.json")


# ---------------------------------------------- the shipped pack declares itself unverified


def test_the_quantec_pack_is_marked_pending():
    assert _quantec().review_pending is True
    assert "not verified against primary sources" in _quantec().maintainer_review


def test_every_quantec_entry_is_unverified():
    assert all(entry.verified is False for entry in _quantec().entries)


def test_the_two_flagged_entries_carry_a_review_note():
    """The reviewer is pointed at the two entries most likely to be wrong."""
    notes = {(e.organ, e.metric): e.review_note for e in _quantec().entries if e.review_note}
    larynx = next(v for (o, m), v in notes.items() if o == "Larynx" and m == "Dmean")
    bladder = next(v for (o, m), v in notes.items() if o == "Bladder" and m == "V70")
    assert "endpoint" in larynx
    assert "RTOG 0415" in bladder
    assert "attribution" in bladder


def test_the_pack_says_how_to_clear_the_review():
    import json as _json

    from rbgyanx.ai.tools.literature import packs_dir

    raw = _json.loads((packs_dir() / "quantec_2010.json").read_text(encoding="utf-8"))
    assert "QUANTEC_VERIFIED.json" in raw["review_instructions"]


# ------------------------------------ an unverified shipped row behaves like a recalled one


def test_an_unverified_shipped_row_is_unverified():
    row = _quantec_rows()[0]
    assert row.provenance is Provenance.SHIPPED_REFERENCE
    assert row.entry_verified is False
    assert row.unverified is True


def test_an_unverified_shipped_row_is_marked_in_the_table():
    table = render_table(_quantec_rows())
    assert "SHIPPED_REFERENCE (unverified: awaiting maintainer review)" in table


def test_an_unverified_shipped_row_triggers_the_export_notice():
    """The gate fires on entry-level doubt, not only on the provenance tier."""
    assert ORIENTATION_NOTICE in export(_quantec_rows())


def test_an_unverified_shipped_row_cannot_lose_its_provenance_column():
    with pytest.raises(ExportRefused):
        export(_quantec_rows(), fmt="csv", include_provenance=False)


def test_the_marking_survives_csv_export():
    out = export(_quantec_rows(), fmt="csv")
    assert ORIENTATION_NOTICE in out
    assert "awaiting maintainer review" in out


# ------------------------------------------------- a verified row is not gated


def test_a_verified_pack_row_is_not_gated(tmp_path):
    """The acceptance criterion's other half: verification actually lifts the gate."""
    rows = compare_against_pack(
        {"Dmean": 26.4}, _verified_pack(tmp_path, verified=True), organ="Parotid_L"
    )
    assert rows[0].unverified is False
    out = export(rows)
    assert ORIENTATION_NOTICE not in out
    assert "unverified" not in out.lower()


def test_a_verified_row_may_drop_the_provenance_column(tmp_path):
    rows = compare_against_pack(
        {"Dmean": 26.4}, _verified_pack(tmp_path, verified=True), organ="Parotid_L"
    )
    out = export(rows, fmt="csv", include_provenance=False)
    assert "provenance" not in out.splitlines()[0]


def test_a_pending_pack_gates_its_rows(tmp_path):
    rows = compare_against_pack(
        {"Dmean": 26.4}, _verified_pack(tmp_path, verified=False), organ="Parotid_L"
    )
    assert rows[0].unverified is True
    assert ORIENTATION_NOTICE in export(rows)


def test_an_explicit_entry_flag_overrides_the_pack_default(tmp_path):
    """A reviewer clears entries one at a time, inside a pack still marked pending."""
    (tmp_path / "p.json").write_text(
        json.dumps(
            {
                "pack_id": "dept",
                "pack_version": "1.0",
                "maintainer_review": "pending: awaiting review",
                "entries": [
                    {
                        "organ": "Parotid_L",
                        "endpoint": "x",
                        "metric": "Dmean",
                        "comparator": "<",
                        "value": 25.0,
                        "units": "Gy",
                        "citation": "c",
                        "verified": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    pack = load_pack(tmp_path / "p.json")
    assert pack.review_pending is True
    rows = compare_against_pack({"Dmean": 26.4}, pack, organ="Parotid_L")
    assert rows[0].unverified is False


def test_a_pack_that_says_nothing_is_taken_at_its_word(tmp_path):
    """A site shipping its own tolerances is asserting them; silence is not doubt."""
    (tmp_path / "p.json").write_text(
        json.dumps(
            {
                "pack_id": "dept",
                "pack_version": "1.0",
                "entries": [
                    {
                        "organ": "Parotid_L",
                        "endpoint": "x",
                        "metric": "Dmean",
                        "comparator": "<",
                        "value": 25.0,
                        "units": "Gy",
                        "citation": "c",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rows = compare_against_pack({"Dmean": 26.4}, load_pack(tmp_path / "p.json"), organ="Parotid_L")
    assert rows[0].unverified is False


def test_the_generated_lkb_pack_is_not_gated():
    """It is a faithful copy of the engine config, not a literature claim; a test proves it."""
    lkb = next(p for p in load_all_packs() if p.pack_id == "rbgyanx-lkb-defaults")
    assert lkb.review_pending is False
    assert all(entry.verified for entry in lkb.entries)


# ------------------------------------------- the two kinds of doubt render differently


def test_an_unverified_shipped_citation_keeps_its_reference():
    """A reviewer needs the pointer; the doubt is about the value, not the paper's existence."""
    rendered = _quantec_rows()[0].display_citation()
    assert "Deasy" in rendered
    assert "quantec-2010" in rendered
    assert "UNVERIFIED against primary source" in rendered


def test_a_recalled_citation_is_still_replaced_outright():
    """A recalled reference may not exist at all, so it is removed rather than annotated."""
    from rbgyanx.ai.tools.literature import ComparisonRow

    row = ComparisonRow(
        organ="Parotid_L",
        endpoint="x",
        metric="Dmean",
        observed=26.4,
        reference=25.0,
        units="Gy",
        verdict="exceeds",
        provenance=Provenance.MODEL_RECALL,
        citation="Smith et al. 2011, doi:10.1000/fake",
    )
    assert row.display_citation() == UNVERIFIED_CITATION


def test_both_kinds_of_unverified_are_gated_together():
    from rbgyanx.ai.tools.literature import ComparisonRow

    recalled = ComparisonRow(
        organ="Parotid_L",
        endpoint="x",
        metric="Dmean",
        observed=26.4,
        reference=25.0,
        units="Gy",
        verdict="exceeds",
        provenance=Provenance.MODEL_RECALL,
        citation="c",
    )
    rows = [*_quantec_rows(), recalled]
    out = export(rows)
    assert ORIENTATION_NOTICE in out
    with pytest.raises(ExportRefused):
        export(rows, fmt="csv", include_provenance=False)
