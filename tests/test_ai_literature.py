"""
Literature quick-compare and export-gate tests (governed AI assistant, phase 6).

The property under test is that a recalled number and a checked number never become
indistinguishable. That means provenance has to survive three things: rendering, mixing, and
export - and the one operation that would erase it has to be refused rather than accommodated.
"""

from __future__ import annotations

import json

import pytest
import yaml
from rbgyanx.ai.capability import Capability, InstallType
from rbgyanx.ai.config import PROVIDERS
from rbgyanx.ai.tools import ToolContext, invoke
from rbgyanx.ai.tools.literature import (
    ORIENTATION_NOTICE,
    UNVERIFIED_CITATION,
    ComparisonRow,
    ExportRefused,
    Provenance,
    compare_against_pack,
    export,
    load_all_packs,
    load_pack,
    packs_dir,
    render_table,
)

LOCAL = PROVIDERS["local"]
REMOTE = PROVIDERS["claude"]
NO_ENV: dict[str, str] = {}
SOURCE_LOCAL = ToolContext(LOCAL, InstallType.SOURCE, env=NO_ENV)
FROZEN_REMOTE = ToolContext(REMOTE, InstallType.FROZEN, env=NO_ENV)
CI_LOCAL = ToolContext(LOCAL, InstallType.CI, env=NO_ENV)


def _recalled(organ="Parotid_L", value=25.0) -> ComparisonRow:
    return ComparisonRow(
        organ=organ,
        endpoint="xerostomia",
        metric="Dmean",
        observed=26.4,
        reference=value,
        units="Gy",
        verdict="exceeds",
        provenance=Provenance.MODEL_RECALL,
        citation="Smith et al. 2011, doi:10.1000/fake-doi-12345",
    )


def _shipped() -> ComparisonRow:
    pack = next(p for p in load_all_packs() if p.pack_id == "quantec-2010")
    rows = compare_against_pack({"Dmean": 26.4}, pack, organ="Parotid")
    assert rows, "the QUANTEC pack should have a parotid Dmean entry"
    return rows[0]


# ------------------------------------------------------------------------- the packs


def test_both_shipped_packs_load():
    ids = {p.pack_id for p in load_all_packs()}
    assert {"quantec-2010", "rbgyanx-lkb-defaults"} <= ids


def test_every_pack_entry_carries_the_required_fields():
    for pack in load_all_packs():
        assert pack.pack_version
        for entry in pack.entries:
            assert entry.organ and entry.endpoint and entry.metric
            assert entry.units
            assert entry.citation, f"{pack.pack_id}: an entry has no citation"
            assert isinstance(entry.value, float)


def test_a_file_without_the_required_keys_is_not_a_pack(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"pack_id": "x"}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a reference pack"):
        load_pack(bad)


def test_a_site_can_add_its_own_pack(tmp_path):
    """rbGyanX ships to many countries; one institution's tolerances are not universal."""
    (tmp_path / "site.json").write_text(
        json.dumps(
            {
                "pack_id": "site-local",
                "pack_version": "2026.1",
                "title": "Our department",
                "entries": [
                    {
                        "organ": "Parotid_L",
                        "endpoint": "xerostomia",
                        "metric": "Dmean",
                        "comparator": "<",
                        "value": 22.0,
                        "units": "Gy",
                        "citation": "Departmental protocol v3",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    packs = load_all_packs(tmp_path)
    assert [p.pack_id for p in packs] == ["site-local"]
    rows = compare_against_pack({"Dmean": 26.4}, packs[0], organ="Parotid_L")
    assert rows[0].verdict == "exceeds"
    assert rows[0].reference == 22.0


def test_the_lkb_pack_agrees_with_the_engine_yaml():
    """The pack is generated from the engine config; this catches drift between them."""
    from rbgyanx.ai.scrubber import install_root

    raw = yaml.safe_load(
        (install_root() / "engine" / "config" / "site_params_ntcp_default.yaml").read_text(
            encoding="utf-8"
        )
    )
    pack = next(p for p in load_all_packs() if p.pack_id == "rbgyanx-lkb-defaults")
    indexed = {(e.site, e.organ, e.endpoint, e.metric): e.value for e in pack.entries}

    checked = 0
    for site_key, site in raw.items():
        for organ, params in (site.get("organs") or {}).items():
            for model in ("LKB_loglogit", "LKB_probit", "RS"):
                for name, value in (params.get(model) or {}).items():
                    key = (site_key, organ, f"{model} parameter", name)
                    assert key in indexed, f"pack is missing {key}"
                    assert indexed[key] == float(value), f"pack drifted from the YAML at {key}"
                    checked += 1
    assert checked > 100, "expected the engine YAML to contribute many parameters"


# ------------------------------------------------------- shipped rows are arithmetic


def test_shipped_comparisons_need_no_model():
    """Reproducible without any model call: the verdict is arithmetic on the pack."""
    pack = next(p for p in load_all_packs() if p.pack_id == "quantec-2010")
    rows = compare_against_pack({"Dmean": 26.4}, pack, organ="Parotid")
    assert rows
    for row in rows:
        assert row.provenance is Provenance.SHIPPED_REFERENCE
        assert row.provenance.verified is True


def test_arithmetic_verdicts_are_correct():
    pack = next(p for p in load_all_packs() if p.pack_id == "quantec-2010")
    over = compare_against_pack({"Dmean": 26.4}, pack, organ="Parotid (single gland)")
    under = compare_against_pack({"Dmean": 12.0}, pack, organ="Parotid (single gland)")
    assert all(r.verdict == "exceeds" for r in over)
    assert all(r.verdict == "within" for r in under)


def test_a_shipped_row_carries_its_citation_and_pack_version():
    row = _shipped()
    rendered = row.display_citation()
    assert "Deasy" in rendered
    assert "quantec-2010" in rendered
    assert "v1.0.0" in rendered


def test_repeated_comparison_is_identical():
    """No model in the loop means the same inputs give the same table every time."""
    pack = next(p for p in load_all_packs() if p.pack_id == "quantec-2010")
    first = render_table(compare_against_pack({"Dmean": 26.4}, pack, organ="Parotid"))
    second = render_table(compare_against_pack({"Dmean": 26.4}, pack, organ="Parotid"))
    assert first == second


# ---------------------------------------------------------- recalled rows are marked


def test_a_recalled_row_is_unverified():
    row = _recalled()
    assert row.unverified is True
    assert row.provenance.verified is False


def test_a_recalled_doi_is_never_rendered_as_a_reference():
    """A plausible-looking citation is worse than none at all."""
    row = _recalled()
    rendered = row.display_citation()
    assert rendered == UNVERIFIED_CITATION
    assert "doi" not in rendered.lower()
    assert "10.1000" not in rendered
    assert "Smith" not in rendered


def test_the_rendered_table_marks_the_recalled_row():
    table = render_table([_shipped(), _recalled()])
    assert "MODEL_RECALL (unverified)" in table
    assert "SHIPPED_REFERENCE" in table
    assert UNVERIFIED_CITATION in table


def test_web_retrieved_counts_as_unverified():
    """Retrieval proves a page said it, not that the page is right."""
    assert Provenance.WEB_RETRIEVED.verified is False


def test_provenance_column_is_always_present():
    table = render_table([_shipped()])
    assert "Provenance" in table


def test_mixing_tiers_keeps_the_provenance_column_visible():
    table = render_table([_shipped(), _recalled()])
    header = table.splitlines()[0]
    assert "Provenance" in header


# --------------------------------------------------------------------- the export gate


def test_an_export_with_a_recalled_row_carries_the_notice():
    out = export([_shipped(), _recalled()])
    assert ORIENTATION_NOTICE in out


def test_the_notice_wording_is_verbatim():
    assert ORIENTATION_NOTICE == (
        "Quick orientation only. Values marked unverified come from model recall, not a checked "
        "source. Any comparison intended for publication, QA documentation or clinical use must "
        "be performed and verified by a human against primary literature."
    )


def test_an_all_shipped_export_carries_no_notice():
    """The notice means something only if it is not on everything."""
    out = export([_shipped()])
    assert ORIENTATION_NOTICE not in out
    assert "SHIPPED_REFERENCE" in out


def test_rows_stay_marked_inside_the_exported_artefact():
    out = export([_shipped(), _recalled()])
    assert "MODEL_RECALL (unverified)" in out
    assert UNVERIFIED_CITATION in out


def test_csv_export_also_carries_the_notice_and_the_marking():
    out = export([_shipped(), _recalled()], fmt="csv")
    assert ORIENTATION_NOTICE in out
    assert "MODEL_RECALL (unverified)" in out
    assert "provenance" in out.splitlines()[2]


def test_dropping_provenance_is_refused_while_unverified_rows_are_present():
    """The one operation that would make recalled content indistinguishable from checked."""
    with pytest.raises(ExportRefused) as excinfo:
        export([_shipped(), _recalled()], fmt="csv", include_provenance=False)
    assert "unverified" in str(excinfo.value)
    assert "provenance" in str(excinfo.value)


def test_dropping_provenance_is_allowed_when_every_row_is_shipped():
    out = export([_shipped()], fmt="csv", include_provenance=False)
    assert "provenance" not in out.splitlines()[0]


def test_the_notice_cannot_be_lost_by_choosing_a_format():
    for fmt in ("markdown", "csv"):
        assert ORIENTATION_NOTICE in export([_recalled()], fmt=fmt)


def test_an_unknown_export_format_is_rejected():
    with pytest.raises(ValueError, match="unknown export format"):
        export([_shipped()], fmt="latex")


# ----------------------------------------------------------------------- the tool


def test_literature_compare_is_registered_and_gated():
    from rbgyanx.ai.tools import REGISTRY

    assert REGISTRY.get("literature_compare").capability is Capability.LITERATURE_COMPARE


def test_literature_compare_works_on_a_frozen_remote_install():
    """The matrix grants this everywhere except CI: it compares published values."""
    result = invoke("literature_compare", FROZEN_REMOTE, organ="Parotid", observed={"Dmean": 26.4})
    assert result.ok is True
    assert result.metadata["rows"] >= 1


def test_literature_compare_is_refused_in_ci():
    result = invoke("literature_compare", CI_LOCAL, organ="Parotid", observed={"Dmean": 26.4})
    assert result.ok is False


def test_the_tool_reports_how_many_rows_were_unverified():
    result = invoke(
        "literature_compare",
        SOURCE_LOCAL,
        organ="Parotid",
        observed={"Dmean": 26.4},
        model_rows=[_recalled()],
    )
    assert result.ok is True
    assert result.metadata["unverified_rows"] == 1
    assert ORIENTATION_NOTICE in result.output


def test_a_clean_comparison_reports_no_notice():
    result = invoke("literature_compare", SOURCE_LOCAL, organ="Parotid", observed={"Dmean": 26.4})
    assert result.reason == ""
    assert ORIENTATION_NOTICE not in result.output


def test_the_tool_names_the_packs_it_used():
    result = invoke("literature_compare", SOURCE_LOCAL, organ="Parotid", observed={"Dmean": 26.4})
    assert "quantec-2010" in result.metadata["packs"]


def test_the_packs_directory_ships_with_the_package():
    """A stranger installing a wheel must get the packs, not just a checkout."""
    from rbgyanx.ai.scrubber import install_root

    assert packs_dir().is_dir()
    assert list(packs_dir().glob("*.json"))
    # It has to be an importable package, or setuptools will not carry the JSON into the wheel.
    assert (packs_dir() / "__init__.py").is_file()
    pyproject = (install_root() / "pyproject.toml").read_text(encoding="utf-8")
    assert '"rbgyanx.ai.reference_packs" = ["*.json"]' in pyproject
