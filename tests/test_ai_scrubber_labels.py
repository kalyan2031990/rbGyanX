"""
Non-English and site-specific structure labels (phase B).

The residual checks are calibrated on English structure names, and the non-ASCII check treats
any non-ASCII letter as possibly a name with diacritics. That is right for "Mueller" and wrong
for a department whose structures are named in German, Spanish, Japanese or Russian - those
would refuse constantly, and a safety control that fires constantly gets switched off. That is
the real failure mode, and it is worse than the leak the control was protecting against.

The policy implemented here: a site DECLARES its label vocabulary once, and thereafter its
labels pass. Latin-script labels with no recognised anatomical segment are already neutral. What
is deliberately NOT done is shipping a partial multilingual alias set - that works for the
languages that happen to be included and fails for the next one.

Throughout: `Parotid_L_Smith` must still refuse. A policy that lets a surname through has not
solved the problem, it has removed the control.
"""

from __future__ import annotations

import json

import pytest
from rbgyanx.ai.scrubber import (
    LABELS_ENV_VAR,
    reset_label_cache,
    scrub,
    structure_label_is_recognised,
)

# Real-world shapes: German, Spanish, French, Japanese, Russian, Polish.
GERMAN = "Ohrspeicheldrüse_L"
GERMAN_ASCII = "Ohrspeicheldruese_L"
SPANISH = "Parotida_izq"
FRENCH = "Glande_parotide_G"
JAPANESE = "耳下腺_L"
RUSSIAN = "Околоушная_L"
POLISH = "Ślinianka_przyuszna_L"

NAME_APPENDED = "Parotid_L_Smith"
BARE_SURNAME = "Müller"


@pytest.fixture(autouse=True)
def _clean_label_cache():
    """The vocabulary is cached; every test starts from a known state."""
    reset_label_cache()
    yield
    reset_label_cache()


@pytest.fixture()
def declared(tmp_path, monkeypatch):
    """Register a site vocabulary, the way a department would."""

    def _register(labels):
        (tmp_path / "site.labels.json").write_text(
            json.dumps({"structure_labels": list(labels)}), encoding="utf-8"
        )
        monkeypatch.setenv(LABELS_ENV_VAR, str(tmp_path))
        reset_label_cache()

    return _register


def _confident(label: str) -> bool:
    return scrub(f"mean dose for {label} was 26.4 Gy").confident


# ------------------------------------------- (a) Latin-script labels are already neutral


@pytest.mark.parametrize("label", [GERMAN_ASCII, SPANISH, FRENCH])
def test_latin_script_labels_pass_without_any_declaration(label):
    """No recognised anatomical segment means no reason to suspect an appended name."""
    assert _confident(label) is True


def test_an_unknown_latin_word_alone_is_not_suspicious():
    assert scrub("dose to Speicheldruese was 22.1 Gy").confident is True


# ------------------------------- undeclared non-Latin scripts still refuse, by design


@pytest.mark.parametrize("label", [GERMAN, JAPANESE, RUSSIAN, POLISH])
def test_undeclared_non_ascii_labels_refuse(label):
    """Honest default: without a declaration, a non-ASCII token could be a patient's name."""
    assert _confident(label) is False


def test_the_refusal_explains_how_to_fix_it_permanently(tmp_path):
    """A refusal with a remedy gets fixed; a refusal without one gets the feature switched off."""
    from rbgyanx.ai.scrubber import ScrubRefused, scrub_for_transmission

    with pytest.raises(ScrubRefused) as excinfo:
        scrub_for_transmission(f"dose for {JAPANESE}", remote=True)
    assert LABELS_ENV_VAR in str(excinfo.value)
    assert "declare it once" in str(excinfo.value)


# ------------------------------------------ (c) declaration lifts the refusal


@pytest.mark.parametrize("label", [GERMAN, JAPANESE, RUSSIAN, POLISH])
def test_a_declared_label_is_recognised(declared, label):
    declared([GERMAN, JAPANESE, RUSSIAN, POLISH])
    assert structure_label_is_recognised(label) is True


@pytest.mark.parametrize("label", [GERMAN, JAPANESE, RUSSIAN, POLISH])
def test_a_declared_label_no_longer_refuses(declared, label):
    declared([GERMAN, JAPANESE, RUSSIAN, POLISH])
    assert _confident(label) is True


def test_a_whole_german_structure_set_passes(declared):
    """The acceptance criterion: a real department's set does not trigger refusal."""
    german_set = [
        "Ohrspeicheldrüse_L",
        "Ohrspeicheldrüse_R",
        "Unterkieferspeicheldrüse_L",
        "Rückenmark",
        "Hirnstamm",
        "Schilddrüse",
        "Speiseröhre",
        "Kehlkopf",
    ]
    declared(german_set)
    report = "; ".join(f"{label} 26.4 Gy" for label in german_set)
    result = scrub(report)
    assert result.confident is True, result.reasons


def test_declared_segments_also_work_inside_compound_labels(declared):
    declared(["Ohrspeicheldruese"])
    assert _confident("Ohrspeicheldruese_L_PRV") is True


def test_a_bare_json_list_is_accepted(tmp_path, monkeypatch):
    """A site should not have to learn a schema to declare eight strings."""
    path = tmp_path / "labels.json"
    path.write_text(json.dumps([GERMAN, JAPANESE]), encoding="utf-8")
    monkeypatch.setenv(LABELS_ENV_VAR, str(path))
    reset_label_cache()
    assert structure_label_is_recognised(GERMAN) is True


def test_a_reference_pack_may_carry_labels_alongside_its_entries(tmp_path, monkeypatch):
    """Labels live where the site's other declarations already live."""
    (tmp_path / "dept.json").write_text(
        json.dumps(
            {
                "pack_id": "dept",
                "pack_version": "1.0",
                "entries": [],
                "structure_labels": [GERMAN, JAPANESE],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(LABELS_ENV_VAR, str(tmp_path))
    reset_label_cache()
    assert structure_label_is_recognised(JAPANESE) is True


# -------------------------------------- the control is not weakened by any of this


def test_an_appended_surname_still_refuses_with_no_declaration():
    assert structure_label_is_recognised(NAME_APPENDED) is False
    assert _confident(NAME_APPENDED) is False


def test_an_appended_surname_still_refuses_after_a_declaration(declared):
    """The whole point: declaring German labels must not make Parotid_L_Smith acceptable."""
    declared([GERMAN, JAPANESE, RUSSIAN])
    assert structure_label_is_recognised(NAME_APPENDED) is False
    assert _confident(NAME_APPENDED) is False


def test_a_bare_surname_still_refuses_after_a_declaration(declared):
    declared([GERMAN, JAPANESE])
    assert _confident(BARE_SURNAME) is False


def test_declaring_one_label_does_not_vouch_for_a_different_one(declared):
    declared([GERMAN])
    assert structure_label_is_recognised(GERMAN) is True
    assert structure_label_is_recognised(JAPANESE) is False


def test_a_site_can_still_shoot_itself_in_the_foot_only_deliberately(declared):
    """Declaring a name-bearing label is a site's explicit act, not an accident."""
    declared([NAME_APPENDED])
    assert structure_label_is_recognised(NAME_APPENDED) is True


def test_patient_identifiers_are_still_redacted_alongside_declared_labels(declared):
    declared([GERMAN])
    result = scrub(f"PatientID 004512237 {GERMAN} 26.4 Gy")
    assert "004512237" not in result.text
    assert "REDACTED" in result.text


# ------------------------------------------------------------------- robustness


def test_a_missing_labels_path_is_not_an_error(monkeypatch):
    monkeypatch.setenv(LABELS_ENV_VAR, "/nonexistent/labels.json")
    reset_label_cache()
    assert structure_label_is_recognised("Parotid_L") is True
    assert _confident(GERMAN) is False


def test_a_malformed_labels_file_is_ignored(tmp_path, monkeypatch):
    path = tmp_path / "labels.json"
    path.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv(LABELS_ENV_VAR, str(path))
    reset_label_cache()
    assert _confident(GERMAN) is False, "a broken file must not silently vouch for anything"


def test_an_empty_declaration_changes_nothing(declared):
    declared([])
    assert _confident(GERMAN) is False
    assert _confident("Parotid_L") is True


def test_english_labels_keep_working_when_a_site_declares_others(declared):
    declared([GERMAN, JAPANESE])
    assert structure_label_is_recognised("Parotid_L") is True
    assert structure_label_is_recognised("SpinalCord") is True
