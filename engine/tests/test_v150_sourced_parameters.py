"""v1.5.0 default NTCP parameters: provenance on every value, and BASIC refuses what has none.

The schema tests here are the guard that the shipped parameter library cannot drift back into
unsourced numbers without saying so. The transcription itself is checked against the papers in
rbGyanX-papers/V1_5_0_DEFAULT_PARAMETERS_FOR_APPROVAL.md; what is asserted below is that the file
says what the papers say, and that nothing is published as sourced by omission.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from dicompylercore.dvh import DVH

from config.site_ntcp_params import (
    ILLUSTRATIVE_PARAMS_IN_BASIC_MODE,
    MODEL_KEYS,
    PROVENANCE_REQUIRED,
    OrganNTCPParams,
    load_site_ntcp_params,
)
from dicom_io.dvh_extractor import DVHResult
from radiobiology.ntcp_calculator import NTCPCalculator

SITES = ("HN", "LUNG", "BREAST", "BRAIN_GBM", "BRAIN_METS", "PROSTATE", "LIVER")

BURMAN = "Burman C, Kutcher GJ, Emami B, Goitein M. IJROBP 21:123-135 (1991)"
BURMAN_PAGE = "Burman 1991, Table 1, p. 125"
RANCATI_PAGE = "Rancati 2009, p. 919 (LEUD best-fit values; also in the abstract, p. 915)"


def _organs():
    for site in SITES:
        for name, params in load_site_ntcp_params(site).organs.items():
            yield site, name, params


# ------------------------------------------------------------------------------ the schema


def test_every_model_block_has_a_provenance_block() -> None:
    """Nothing may be published as sourced by omission."""
    missing = []
    for site, name, params in _organs():
        for model, attr in (
            ("LKB_loglogit", "lkb_loglogit"),
            ("LKB_probit", "lkb_probit"),
            ("RS", "rs"),
        ):
            if getattr(params, attr) and model not in params.provenance:
                missing.append(f"{site}/{name}/{model}")
    assert not missing, missing


def test_every_provenance_block_declares_all_required_fields() -> None:
    incomplete = []
    for site, name, params in _organs():
        for model, block in params.provenance.items():
            for field in PROVENANCE_REQUIRED:
                if field not in block:
                    incomplete.append(f"{site}/{name}/{model}: missing {field}")
    assert not incomplete, incomplete


def test_a_sourced_block_names_a_table_and_a_page() -> None:
    """A citation without a page is not checkable, so it does not count as sourced."""
    vague = []
    for site, name, params in _organs():
        for model, block in params.provenance.items():
            if block.get("illustrative"):
                continue
            if "p." not in str(block.get("table_page", "")):
                vague.append(f"{site}/{name}/{model}: {block.get('table_page')!r}")
            if not str(block.get("endpoint", "")).strip():
                vague.append(f"{site}/{name}/{model}: no endpoint")
    assert not vague, vague


def test_a_sourced_block_records_the_numbers_as_the_paper_prints_them() -> None:
    mismatched = []
    for site, name, params in _organs():
        block = params.provenance.get("LKB_probit")
        if not block or block.get("illustrative"):
            continue
        printed = block.get("as_printed") or {}
        for key, value in (params.lkb_probit or {}).items():
            if key in printed and float(printed[key]) != pytest.approx(float(value)):
                mismatched.append(f"{site}/{name}: {key} {value} vs as_printed {printed[key]}")
    assert not mismatched, mismatched


def test_geud_a_is_one_over_n_for_every_sourced_probit_fit() -> None:
    """The LKB probit model reduces the DVH with a = 1/n; the YAML must agree with its own n."""
    wrong = []
    for site, name, params in _organs():
        block = params.provenance.get("LKB_probit")
        if not block or block.get("illustrative") or not params.lkb_probit:
            continue
        n = float(params.lkb_probit["n"])
        if params.geud_a != pytest.approx(1.0 / n, rel=1e-3):
            wrong.append(f"{site}/{name}: geud_a {params.geud_a} but 1/n = {1.0 / n:.4g}")
    assert not wrong, wrong


def test_the_organ_flag_agrees_with_its_models() -> None:
    """``illustrative`` on the organ means no model of it has a source."""
    for site, name, params in _organs():
        per_model = [params.model_is_illustrative(m) for m in MODEL_KEYS if m in params.provenance]
        if not per_model:
            continue
        assert params.illustrative == all(per_model), f"{site}/{name}"


def test_no_two_organs_share_the_placeholder_m_and_n_any_more() -> None:
    """Five probit blocks used to carry the identical m = 0.18, n = 0.05 across four sites."""
    placeholder = [
        f"{site}/{name}"
        for site, name, params in _organs()
        if params.lkb_probit
        and float(params.lkb_probit.get("m", 0)) == 0.18
        and float(params.lkb_probit.get("n", 0)) == 0.05
    ]
    assert not placeholder, placeholder


# ------------------------------------------------------------------- the transcribed values


@pytest.mark.parametrize(
    "site, organ, td50, m, n, endpoint",
    [
        ("HN", "SpinalCord", 66.5, 0.175, 0.05, "Myelitis/necrosis"),
        ("BREAST", "SpinalCord", 66.5, 0.175, 0.05, "Myelitis/necrosis"),
        ("LUNG", "SpinalCord", 66.5, 0.175, 0.05, "Myelitis/necrosis"),
        ("PROSTATE", "SpinalCord", 66.5, 0.175, 0.05, "Myelitis/necrosis"),
        ("LIVER", "SpinalCord", 66.5, 0.175, 0.05, "Myelitis/necrosis"),
        ("HN", "BrainStem", 65.0, 0.14, 0.16, "Necrosis/infarction"),
        ("BRAIN_GBM", "BrainStem", 65.0, 0.14, 0.16, "Necrosis/infarction"),
        ("BRAIN_METS", "BrainStem", 65.0, 0.14, 0.16, "Necrosis/infarction"),
        ("BRAIN_GBM", "NormalBrain", 60.0, 0.15, 0.25, "Necrosis/infarction"),
        ("BRAIN_METS", "NormalBrain", 60.0, 0.15, 0.25, "Necrosis/infarction"),
        ("BRAIN_GBM", "OpticChiasm", 65.0, 0.14, 0.25, "Blindness"),
        ("BRAIN_GBM", "OpticNerve_L", 65.0, 0.14, 0.25, "Blindness"),
        ("LUNG", "BrachialPlexus", 75.0, 0.12, 0.03, "Clinically apparent nerve damage"),
        ("LUNG", "Heart", 48.0, 0.10, 0.35, "Pericarditis"),
        ("LUNG", "LungTotal", 24.5, 0.18, 0.87, "Pneumonitis"),
        ("LUNG", "Rib", 68.0, 0.21, 0.10, "Pathologic fracture"),
        ("HN", "Esophagus", 68.0, 0.11, 0.06, "Clinical stricture/perforation"),
        ("LIVER", "Esophagus", 68.0, 0.11, 0.06, "Clinical stricture/perforation"),
        ("LIVER", "Liver", 40.0, 0.15, 0.32, "Liver failure"),
        ("LIVER", "Stomach", 65.0, 0.14, 0.15, "Ulceration/perforation"),
        ("PROSTATE", "Bladder", 80.0, 0.11, 0.5, None),
        ("PROSTATE", "FemoralHead_L", 65.0, 0.12, 0.25, "Necrosis"),
    ],
)
def test_burman_values_are_transcribed_exactly(
    site: str, organ: str, td50: float, m: float, n: float, endpoint: str | None
) -> None:
    params = load_site_ntcp_params(site).organs[organ]
    assert params.lkb_probit == {"TD50_gy": td50, "m": m, "n": n}, params.lkb_probit
    block = params.provenance["LKB_probit"]
    assert block["source"] == BURMAN
    assert block["table_page"] == BURMAN_PAGE
    assert block["illustrative"] is False
    if endpoint is not None:
        assert block["endpoint"] == endpoint
    assert params.illustrative is False


def test_the_larynx_carries_the_rancati_fit_and_its_dose_basis() -> None:
    params = load_site_ntcp_params("HN").organs["Larynx"]
    assert params.lkb_probit == {"TD50_gy": 47.3, "m": 0.23, "n": 1.17}
    assert params.geud_a == pytest.approx(1.0 / 1.17, rel=1e-3)
    block = params.provenance["LKB_probit"]
    assert block["table_page"] == RANCATI_PAGE
    assert block["as_printed"] == {"n": 1.17, "m": 0.23, "TD50_gy": 47.3}
    # Rancati fitted the EUD of EQD2 DVHs at alpha/beta 3 Gy; the organ must use that alpha/beta
    assert "EQD2" in block["fractionation_basis"]
    assert "3 Gy" in block["fractionation_basis"]
    assert params.alpha_beta_gy == pytest.approx(3.0)


def test_the_spinal_cord_structure_definition_states_the_20_cm_reference_length() -> None:
    """Burman's V_ref for the cord is a 20 cm LENGTH, not the whole contoured volume."""
    block = load_site_ntcp_params("HN").organs["SpinalCord"].provenance["LKB_probit"]
    assert "20 cm" in block["structure_definition"]
    assert "not the whole contoured cord" in block["structure_definition"]


def test_the_rib_structure_definition_states_one_third_of_the_rib_cage() -> None:
    block = load_site_ntcp_params("LUNG").organs["Rib"].provenance["LKB_probit"]
    assert "one third of the rib cage" in block["structure_definition"]
    assert "NOT a single rib" in block["structure_definition"]


def test_the_femoral_head_definition_says_head_and_neck() -> None:
    block = load_site_ntcp_params("PROSTATE").organs["FemoralHead_L"].provenance["LKB_probit"]
    assert block["structure_definition"] == "femoral head and neck"


def test_the_mandible_is_not_offered_as_an_osteoradionecrosis_model() -> None:
    block = load_site_ntcp_params("HN").organs["Mandible"].provenance["LKB_probit"]
    assert "TM joint" in block["endpoint"]
    assert "NOT an osteoradionecrosis model" in block["structure_definition"]


def test_the_esophagus_endpoint_is_stricture_not_acute_esophagitis() -> None:
    for site in ("HN", "LUNG", "BREAST", "LIVER"):
        block = load_site_ntcp_params(site).organs["Esophagus"].provenance["LKB_probit"]
        assert block["endpoint"] == "Clinical stricture/perforation", site


def test_the_burman_fractionation_basis_claims_only_what_can_be_cited() -> None:
    """Burman 1991 states no fractionation of its own; the field must not invent one."""
    block = load_site_ntcp_params("HN").organs["SpinalCord"].provenance["LKB_probit"]
    basis = block["fractionation_basis"]
    assert "Emami et al. 1991 tolerance compilation" in basis
    assert "state no fractionation of their own" in basis
    assert "1.8" not in basis and "2 Gy" not in basis


def test_the_liver_geud_a_is_no_longer_n_itself() -> None:
    """``geud_a`` held n (0.97) instead of 1/n, so the DVH reduction was wrong (defect #47)."""
    params = load_site_ntcp_params("LIVER").organs["Liver"]
    assert params.geud_a == pytest.approx(1.0 / 0.32, rel=1e-3)
    assert params.geud_a != pytest.approx(0.97)
    assert "defect #47" in params.provenance["LKB_probit"]["replaces"]


# --------------------------------------------------------------- what stays illustrative

AWAITING_A_PAPER = {
    ("HN", "Parotid_L"),
    ("HN", "Parotid_R"),
    ("PROSTATE", "Rectum"),
    ("BREAST", "Thyroid"),
}

NO_PUBLISHED_FIT = {
    ("HN", "OralCavity"),
    ("HN", "PharynxConstrictor"),
    ("HN", "Submandibular_L"),
    ("HN", "Submandibular_R"),
    ("LUNG", "ChestWall"),
    ("BREAST", "LAD"),
    ("BRAIN_GBM", "Pituitary"),
    ("BRAIN_GBM", "Hippocampus_L"),
    ("BRAIN_GBM", "Hippocampus_R"),
    ("BRAIN_GBM", "Cochlea_L"),
    ("BRAIN_GBM", "Cochlea_R"),
    ("BRAIN_METS", "Hippocampus_L"),
    ("BRAIN_METS", "Hippocampus_R"),
    ("BRAIN_METS", "Cochlea_L"),
    ("BRAIN_METS", "Cochlea_R"),
    ("PROSTATE", "Urethra"),
    ("LIVER", "Duodenum"),
}


def test_the_illustrative_inventory_is_exactly_what_is_recorded() -> None:
    """Pinned so an organ cannot quietly become sourced, or quietly lose its source."""
    found = {(site, name) for site, name, p in _organs() if p.illustrative}
    assert found == AWAITING_A_PAPER | NO_PUBLISHED_FIT, found ^ (
        AWAITING_A_PAPER | NO_PUBLISHED_FIT
    )


def test_every_illustrative_organ_says_why() -> None:
    for site, name, params in _organs():
        if not params.illustrative:
            continue
        for model, block in params.provenance.items():
            assert block.get("note"), f"{site}/{name}/{model} is illustrative with no reason"


def test_the_organs_awaiting_a_paper_name_it() -> None:
    expected = {
        ("HN", "Parotid_L"): "Deasy",
        ("HN", "Parotid_R"): "Deasy",
        ("PROSTATE", "Rectum"): "Michalski",
        ("BREAST", "Thyroid"): "Bakhshandeh",
    }
    for (site, name), author in expected.items():
        params = load_site_ntcp_params(site).organs[name]
        notes = " ".join(str(b.get("note", "")) for b in params.provenance.values())
        assert author in notes, (site, name, notes[:120])


# --------------------------------------------------------------- BASIC mode refuses them


def _oar_dvh_result(label: str, dose_gy: float = 40.0) -> DVHResult:
    bins = np.linspace(0.0, dose_gy * 1.5, 241)
    edge = bins[1:]
    counts = np.where(edge <= dose_gy, 100.0, 0.0)
    return DVHResult(
        roi_number=1,
        raw_name=label,
        canonical_name=label,
        category="OAR",
        total_volume_cc=25.0,
        dmin_gy=dose_gy,
        dmean_gy=dose_gy,
        dmax_gy=dose_gy,
        dvh_object=DVH(
            counts=counts,
            bins=bins,
            dvh_type="cumulative",
            dose_units="Gy",
            volume_units="cm3",
        ),
        quality_flag="OK",
    )


_PLAN = {"n_fractions": 35, "dose_per_fraction_gy": 2.0}


def test_basic_mode_refuses_an_illustrative_organ() -> None:
    """The parotid has no citable source yet, so BASIC must not publish its NTCP."""
    params = load_site_ntcp_params("HN").organs["Parotid_L"]
    row = NTCPCalculator().compute_all(
        _oar_dvh_result("Parotid_L"), _PLAN, params, "HN", mode="basic"
    )
    assert row["param_illustrative"] is True
    assert row["ntcp_refusal_reason"] == ILLUSTRATIVE_PARAMS_IN_BASIC_MODE
    assert row["definition_ok"] is False
    assert math.isnan(row["NTCP_LKB_loglogit"])
    assert math.isnan(row["NTCP_RS"])


def test_advanced_mode_computes_it_and_labels_it() -> None:
    params = load_site_ntcp_params("HN").organs["Parotid_L"]
    row = NTCPCalculator().compute_all(
        _oar_dvh_result("Parotid_L"), _PLAN, params, "HN", mode="advanced"
    )
    assert row["param_illustrative"] is True
    assert row["param_source"] == "unsourced"
    assert not row.get("ntcp_refusal_reason")
    assert not math.isnan(row["NTCP_LKB_loglogit"])


def test_basic_mode_computes_a_sourced_organ() -> None:
    params = load_site_ntcp_params("HN").organs["SpinalCord"]
    row = NTCPCalculator().compute_all(
        _oar_dvh_result("SpinalCord", 45.0), _PLAN, params, "HN", mode="basic"
    )
    assert row["param_illustrative"] is False
    assert row["param_source"].startswith("Burman")
    assert not math.isnan(row["NTCP_LKB_probit"])


def test_basic_mode_refuses_only_the_unsourced_model_of_a_sourced_organ() -> None:
    """HN SpinalCord has a sourced probit fit and an unsourced relative-seriality block."""
    params = load_site_ntcp_params("HN").organs["SpinalCord"]
    row = NTCPCalculator().compute_all(
        _oar_dvh_result("SpinalCord", 45.0), _PLAN, params, "HN", mode="basic"
    )
    assert not math.isnan(row["NTCP_LKB_probit"])
    assert math.isnan(row["NTCP_RS"])
    assert row["ntcp_refused_models"] == "RS"
    # the organ itself is sourced, so its applicability verdict is left alone
    assert row.get("definition_ok") is not False


def test_every_row_carries_the_source_and_the_flag() -> None:
    for site, name, params in _organs():
        row = NTCPCalculator().compute_all(
            _oar_dvh_result(name), _PLAN, params, site, mode="advanced"
        )
        assert "param_source" in row, (site, name)
        assert "param_illustrative" in row, (site, name)
        assert isinstance(row["param_provenance"], dict), (site, name)


def test_a_user_override_without_provenance_does_not_inherit_the_shipped_citation(
    tmp_path,
) -> None:
    """A changed number must not keep a source that describes the old one."""
    user = tmp_path / "site_params_ntcp_user.yaml"
    user.write_text(
        "HN:\n"
        "  organs:\n"
        "    SpinalCord:\n"
        "      LKB_probit: {TD50_gy: 50.0, m: 0.2, n: 0.05}\n",
        encoding="utf-8",
    )
    params = load_site_ntcp_params("HN", user_config=user).organs["SpinalCord"]
    assert params.lkb_probit == {"TD50_gy": 50.0, "m": 0.2, "n": 0.05}
    assert params.model_is_illustrative("LKB_probit")
    assert params.illustrative is True
    assert "without a provenance block" in params.provenance["LKB_probit"]["note"]


def test_an_organ_with_no_provenance_at_all_is_illustrative() -> None:
    """The safe reading of silence is "no source", never "trust me"."""
    bare = OrganNTCPParams(canonical="Rectum", lkb_probit={"TD50_gy": 70.0, "m": 0.1, "n": 0.1})
    assert bare.illustrative is True
    assert bare.model_is_illustrative("LKB_probit")
    assert bare.source == "unsourced"


def test_the_dvh_is_untouched_by_the_mode() -> None:
    """BASIC refuses a value; it must not change the dose metrics beside it."""
    params = load_site_ntcp_params("HN").organs["Parotid_L"]
    dvh = _oar_dvh_result("Parotid_L")
    basic = NTCPCalculator().compute_all(dvh, _PLAN, params, "HN", mode="basic")
    advanced = NTCPCalculator().compute_all(dvh, _PLAN, params, "HN", mode="advanced")
    for key in ("Dmean_gy", "Dmax_gy", "gEUD_gy"):
        assert basic[key] == pytest.approx(advanced[key], nan_ok=True), key


def test_the_shipped_yaml_still_loads_for_every_site() -> None:
    for site in SITES:
        assert load_site_ntcp_params(site).organs, site
    assert pd.notna(load_site_ntcp_params("HN").organs["SpinalCord"].geud_a)


# ------------------------------------------- the AI reference pack mirrors the same values


def test_the_lkb_reference_pack_carries_the_real_citation() -> None:
    """The pack used to cite the YAML itself, which told a reader nothing checkable.

    It also drifted: when HN/SpinalCord moved from 45.0 to 66.5 Gy the pack still said 45.0, and
    the repository's own guard caught it. ``scripts/generate_lkb_reference_pack.py`` now makes the
    pack's ``generated_from`` claim mechanical, so the two cannot disagree silently again.
    """
    import json
    import pathlib

    pack = json.loads(
        (
            pathlib.Path(__file__).resolve().parents[2]
            / "rbgyanx"
            / "ai"
            / "reference_packs"
            / "rbgyanx_lkb_defaults.json"
        ).read_text(encoding="utf-8")
    )
    indexed = {
        (e["site"], e["organ"], e["endpoint"], e["metric"]): e for e in pack["entries"]
    }

    cord = indexed[("HN", "SpinalCord", "LKB_probit parameter", "TD50_gy")]
    assert cord["value"] == 66.5
    assert "Burman 1991, Table 1, p. 125" in cord["citation"]
    assert "Myelitis/necrosis" in cord["citation"]

    larynx = indexed[("HN", "Larynx", "LKB_probit parameter", "TD50_gy")]
    assert larynx["value"] == 47.3
    assert "Rancati 2009, p. 919" in larynx["citation"]

    parotid = indexed[("HN", "Parotid_L", "LKB_loglogit parameter", "TD50_gy")]
    assert "no published source (illustrative)" in parotid["citation"]
    assert "Deasy" in parotid["citation"]


def test_the_reference_pack_generator_reports_no_drift() -> None:
    """``--check`` is the guard that keeps the pack and the engine config in step."""
    import pathlib
    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parents[2]
    done = subprocess.run(
        [sys.executable, "-I", str(root / "scripts" / "generate_lkb_reference_pack.py"), "--check"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert done.returncode == 0, done.stderr or done.stdout
