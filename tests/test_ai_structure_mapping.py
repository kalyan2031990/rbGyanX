"""The LLM may propose a label. It may not decide a laterality, and it may not be required to run.

Two properties carry the whole design:

  1. **Defect #21 is impossible by construction.** If the source name asserts no side, a
     lateralised key is refused no matter what the model returns, no matter how confident it is,
     and again at approval-write time so a human cannot wave it through either.
  2. **The result does not depend on the model.** Once a pack is approved, resolution is a dict
     lookup: no provider, no network, no model, identical answers.

The provider here is a MOCK. No live call is made, and the module never performs one itself -
the caller supplies the answers.
"""

from __future__ import annotations

import json

import pytest
from rbgyanx.ai.structure_mapping import (
    PROMPT_VERSION,
    Residual,
    approve_to_alias_pack,
    build_prompt,
    collect_residue,
    load_alias_pack,
    looks_like_planning_aid,
    source_asserts_laterality,
    validate_proposal,
    write_proposals,
)

pytestmark = pytest.mark.unit

ALLOWED = {
    "Parotid_L": "left parotid gland; xerostomia, parallel mean-dose endpoint",
    "Parotid_R": "right parotid gland; xerostomia, parallel mean-dose endpoint",
    "Submandibular_L": "left submandibular gland",
    "Submandibular_R": "right submandibular gland",
    "SpinalCord": "spinal cord; serial, myelopathy",
    "PharynxConstrictor": "pharyngeal constrictor muscles; dysphagia",
    "Larynx": "larynx",
}


def _answer(canonical, conf="HIGH", **kw):
    base = {"canonical": canonical, "bilateral": False, "asserts_laterality": True,
            "planning_aid": False, "confidence": conf, "reasoning": "mock"}
    base.update(kw)
    return base


def _res(raw, conf="LOW", cat="UNKNOWN"):
    return Residual(raw_name=raw, site="HN", deterministic_canonical=raw.upper(),
                    deterministic_category=cat, deterministic_confidence=conf)


# ------------------------------------------------------- 1. the laterality guard is unconditional

@pytest.mark.parametrize("raw", ["Parotids", "Parotid", "Submandibular", "Parotid_Bilat",
                                 "Glnd_Submand", "parotid gland"])
@pytest.mark.parametrize("key", ["Parotid_L", "Parotid_R", "Submandibular_R"])
def test_lateralised_key_refused_when_source_asserts_no_side(raw, key):
    """The model insisting, at HIGH confidence, that it is lateralised changes nothing."""
    p = validate_proposal(_res(raw), _answer(key, asserts_laterality=True), ALLOWED, "mock-model")
    assert not p.accepted
    assert "asserts a side" in p.rejected_reason
    assert "laterality" in p.guards_applied


@pytest.mark.parametrize(("raw", "key"), [
    ("Lt Parotid", "Parotid_L"),
    ("Parotid_L", "Parotid_L"),
    ("parotid right", "Parotid_R"),
    ("Parotid_R", "Parotid_R"),
    ("Submandibular_L", "Submandibular_L"),
])
def test_a_side_asserting_name_can_still_be_mapped(raw, key):
    """The guard must not become a blanket refusal of lateralised organs."""
    p = validate_proposal(_res(raw), _answer(key), ALLOWED, "m")
    assert p.accepted, p.rejected_reason


def test_the_predicate_is_narrow_on_purpose():
    """A false positive would LET AN INVENTED LATERALITY THROUGH, so when in doubt it says no.

    ``SubmandR`` is the worked example: the predicate does not claim it states a side, so the
    fuzzy/LLM path declines it and it is resolved instead by its curated exact alias in the
    engine - a human decision rather than an inference. A false negative costs a visible refusal;
    a false positive costs a wrong label.
    """
    assert not source_asserts_laterality("SubmandR")
    assert not source_asserts_laterality("Submandibular")
    # and the curated alias table, not this predicate, is what resolves it
    pytest.importorskip("dicom_io.structure_mapper")
    from dicom_io.structure_mapper import canon_target

    r = canon_target("SubmandR", None)
    assert r["canonical"] == "Submandibular_R" and r["confidence"] == "MEDIUM"


def test_unlateralised_non_paired_organ_is_fine():
    p = validate_proposal(_res("PharynxConst"), _answer("PharynxConstrictor"), ALLOWED, "m")
    assert p.accepted, p.rejected_reason


# ------------------------------------------------------- the other guards

def test_a_key_outside_the_allowed_set_is_refused():
    p = validate_proposal(_res("Cochlea"), _answer("Cochlea_L"), ALLOWED, "m")
    assert not p.accepted and "not in the allowed" in p.rejected_reason


@pytest.mark.parametrize("raw", ["Mandible-PTV", "OCavity-PTV", "PTV70OPT", "RingPTV70",
                                 "SpinalCord_05", "BrainStem_03", "Parotid+3mm"])
def test_planning_aids_and_margin_expansions_are_refused(raw):
    assert looks_like_planning_aid(raw)
    p = validate_proposal(_res(raw), _answer("Larynx", planning_aid=False), ALLOWED, "m")
    assert not p.accepted and "planning-aid" in p.guards_applied


def test_low_model_confidence_is_refused():
    p = validate_proposal(_res("PharynxConst"), _answer("PharynxConstrictor", conf="LOW"),
                          ALLOWED, "m")
    assert not p.accepted and "confidence" in p.rejected_reason


def test_no_key_is_refused_not_guessed():
    p = validate_proposal(_res("Blob"), _answer(None), ALLOWED, "m")
    assert not p.accepted and "no canonical key" in p.rejected_reason


# ------------------------------------------------------- the residue and the prompt

def test_only_unresolved_or_low_confidence_names_reach_a_model():
    def canon(name, _):
        table = {
            "SpinalCord": {"canonical": "SpinalCord", "category": "OAR", "confidence": "MEDIUM"},
            "Parotids": {"canonical": "PAROTIDS", "category": "UNKNOWN", "confidence": "LOW"},
            "Submandibular": {"canonical": "Submandibular_R", "category": "OAR",
                              "confidence": "LOW"},
        }
        return table[name]

    res = collect_residue(["SpinalCord", "Parotids", "Submandibular", "SpinalCord"], "HN", canon)
    got = {r.raw_name for r in res}
    assert got == {"Parotids", "Submandibular"}, "a confidently resolved name must not be sent"


def test_prompt_states_the_rules_and_carries_a_version():
    msgs = build_prompt([_res("Parotids")], "HN", ALLOWED)
    text = " ".join(m["content"] for m in msgs)
    assert "does not state a side" in text
    assert "planning aid" in text
    assert PROMPT_VERSION


# ------------------------------------------------------- propose, approve, and run without a model

def test_proposal_file_applies_nothing(tmp_path):
    ps = [validate_proposal(_res("PharynxConst"), _answer("PharynxConstrictor"), ALLOWED, "m"),
          validate_proposal(_res("Parotids"), _answer("Parotid_R"), ALLOWED, "m")]
    p = write_proposals(ps, tmp_path / "proposal.json", site="HN",
                        provider="ollama", base_url="http://localhost:11434/v1")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["status"] == "AWAITING_PHYSICIST_APPROVAL"
    assert d["n_accepted_by_guards"] == 1 and d["n_rejected_by_guards"] == 1
    # the rejected one records WHY, in the file
    bad = [r for r in d["proposals"] if r["raw_name"] == "Parotids"][0]
    assert "asserts a side" in bad["rejected_reason"]


def test_human_approval_cannot_override_the_laterality_guard(tmp_path):
    """Approval is not an override. The guard is re-applied when the pack is written."""
    ps = [validate_proposal(_res("Parotids"), _answer("Parotid_R"), ALLOWED, "m")]
    prop = write_proposals(ps, tmp_path / "p.json", site="HN", provider="ollama", base_url="x")
    pack = approve_to_alias_pack(prop, tmp_path / "pack.json", ["Parotids"])
    assert pack["structure_aliases"] == {}, "an approved-but-refused row must not enter the pack"
    assert pack["refused_at_write_time"], "and the refusal must be recorded"


def test_approved_pack_resolves_with_no_provider_and_no_network(tmp_path, monkeypatch):
    """The property that makes this publishable: identical answers with no model available."""
    ps = [validate_proposal(_res("PharynxConst"), _answer("PharynxConstrictor"), ALLOWED, "m"),
          validate_proposal(_res("Lt Parotid"), _answer("Parotid_L"), ALLOWED, "m")]
    prop = write_proposals(ps, tmp_path / "p.json", site="HN", provider="ollama", base_url="x")
    approve_to_alias_pack(prop, tmp_path / "pack.json", ["PharynxConst", "Lt Parotid"])

    # make any network or provider use impossible
    import socket

    def _no_net(*a, **k):
        raise AssertionError("resolution must not touch the network")

    monkeypatch.setattr(socket, "socket", _no_net)
    monkeypatch.delenv("RBGYANX_AI_PROVIDER", raising=False)
    monkeypatch.delenv("RBGYANX_AI_API_KEY", raising=False)

    first = load_alias_pack(tmp_path / "pack.json")
    second = load_alias_pack(tmp_path / "pack.json")
    assert first == second == {"PharynxConst": "PharynxConstrictor", "Lt Parotid": "Parotid_L"}


def test_pack_is_loadable_by_the_existing_label_mechanism(tmp_path, monkeypatch):
    """Reuse, not reinvention: the scrubber's own discovery must see the approved pack."""
    from rbgyanx.ai import scrubber

    ps = [validate_proposal(_res("PharynxConst"), _answer("PharynxConstrictor"), ALLOWED, "m")]
    prop = write_proposals(ps, tmp_path / "p.json", site="HN", provider="ollama", base_url="x")
    approve_to_alias_pack(prop, tmp_path / "pack.json", ["PharynxConst"])

    files = scrubber._label_files({"RBGYANX_STRUCTURE_LABELS": str(tmp_path)})
    assert any(f.name == "pack.json" for f in files)
    assert "PharynxConst" in scrubber._read_labels(tmp_path / "pack.json")


# ------------------------------------------------------- the guard agrees with the engine's

def test_laterality_predicate_matches_the_engine_guard():
    """Two implementations of one rule must not drift (standing rule 1 in spirit)."""
    pytest.importorskip("dicom_io.structure_mapper")
    from dicom_io.structure_mapper import _SOURCE_ASSERTS_SIDE as ENGINE_RE

    for name in ("Parotids", "Parotid", "Submandibular", "Lt Parotid", "Parotid_L",
                 "FemHead_R", "SpinalCord", "ParotidIps-PTV", "Mandible"):
        assert bool(ENGINE_RE.search(name)) == source_asserts_laterality(name), name
