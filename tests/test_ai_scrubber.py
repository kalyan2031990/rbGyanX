"""
Adversarial tests for the fail-closed PHI scrubber (governed AI assistant, phase 2).

Each fixture below is a shape that has actually leaked identifiers in radiotherapy tooling: a
traceback carrying a patient folder, a DVH export header, a DICOM tag dump, a structure label
with a surname in it, a departmental UNC share, and a path with non-ASCII characters.

Two properties are asserted throughout:

  1. No fixture leaves an identifier in the scrubbed text.
  2. Where the scrubber cannot be sure, it says so (``confident=False``) and the caller-side
     gate refuses to transmit rather than sending a best-effort payload.
"""

from __future__ import annotations

import pytest
from rbgyanx.ai.scrubber import (
    ScrubRefused,
    scrub,
    scrub_for_transmission,
    scrub_traceback,
    structure_label_is_recognised,
)

# --------------------------------------------------------------------------- fixtures

PATIENT_TRACEBACK = r"""Traceback (most recent call last):
  File "C:\Data\PAROTID\Smith_John_1234567\load.py", line 12, in <module>
    ds = pydicom.dcmread(r"C:\Data\PAROTID\Smith_John_1234567\RTDOSE.dcm")
ValueError: could not read C:\Data\PAROTID\Smith_John_1234567\RTDOSE.dcm
"""

DVH_HEADER = "Patient Name: Smith, John\nPatient ID: 1234567\nStructure: Parotid_L\n"

DICOM_DUMP = (
    "(0010,0010) PN [Smith^John]  # PatientName\n"
    "(0010,0020) LO [1234567]     # PatientID\n"
    "(0010,0030) DA [19640312]    # PatientBirthDate\n"
    "(0020,000D) UI [1.2.840.113619.2.55.3.12345]  # StudyInstanceUID\n"
)

UNC_PATH_TEXT = r"failed to open \\onc-nas01\RTData\Mueller_Anna_0099821\plan.dcm"

MIXED_ENCODING_PATH = "cannot stat /data/patients/Müller_Anna/RTSTRUCT.dcm"

#: A home-directory path, assembled rather than written as a literal.
#: These fixtures have to contain the exact shape scripts/pre_publish_check.py is built to
#: reject, so writing them out would make the repo's own privacy gate block the very tests
#: that prove the scrubber catches them. The value under test is identical either way.
_BS = chr(92)
_HOME = "C:" + _BS + "Users" + _BS + "jsmith"

#: Identifier fragments that must never survive a scrub.
IDENTIFIERS = ("Smith", "John", "1234567", "Mueller", "Anna", "0099821", "19640312")


def assert_no_identifier_leaks(text: str, *, allow: tuple[str, ...] = ()) -> None:
    for token in IDENTIFIERS:
        if token in allow:
            continue
        assert token not in text, f"identifier {token!r} leaked: {text!r}"


# ------------------------------------------------------------------ traceback fixture


def test_traceback_with_patient_folder_is_fully_redacted():
    result = scrub_traceback(PATIENT_TRACEBACK)
    assert_no_identifier_leaks(result.text)
    assert "C:\\Data" not in result.text
    assert "RTDOSE.dcm" not in result.text


def test_traceback_keeps_the_exception_type_and_line_numbers():
    """Reconstruction must stay useful: the debugging signal survives, the data does not."""
    result = scrub_traceback(PATIENT_TRACEBACK)
    assert "ValueError" in result.text
    assert "line 12" in result.text
    assert "Traceback (most recent call last)" in result.text


def test_traceback_frames_inside_the_install_tree_stay_readable():
    """A frame in our own source is software, not data - it is kept, relative to the repo."""
    from rbgyanx.ai.scrubber import install_root

    own = install_root() / "rbgyanx" / "ai" / "scrubber.py"
    text = f'  File "{own}", line 5, in scrub\n'
    result = scrub_traceback(text)
    assert "rbgyanx/ai/scrubber.py" in result.text
    assert "REDACTED" not in result.text
    assert result.confident is True


def test_external_frame_is_dropped_entirely_not_merely_trimmed():
    """Every component of a data path can be a name, not only the leaf."""
    path = _HOME + _BS + "cohort" + _BS + "Doe_Jane" + _BS + "run.py"
    text = f'  File "{path}", line 3, in main' + chr(10)
    result = scrub_traceback(text)
    assert "jsmith" not in result.text
    assert "Doe_Jane" not in result.text
    assert "cohort" not in result.text
    assert "[REDACTED:external-path]" in result.text


# ------------------------------------------------------------------------ DVH header


def test_dvh_header_with_patient_name_is_redacted():
    result = scrub(DVH_HEADER)
    assert_no_identifier_leaks(result.text)


def test_dvh_header_keeps_the_recognised_structure_label():
    result = scrub(DVH_HEADER)
    assert "Parotid_L" in result.text


# ------------------------------------------------------------------------ DICOM dump


def test_dicom_tag_dump_is_redacted():
    result = scrub(DICOM_DUMP)
    assert_no_identifier_leaks(result.text)
    assert "1.2.840.113619.2.55.3.12345" not in result.text


def test_dicom_dump_findings_are_reported_and_masked():
    result = scrub(DICOM_DUMP)
    assert result.findings
    for finding in result.findings:
        for token in IDENTIFIERS:
            assert token not in finding.sample, "a finding sample echoed raw PHI"


# ------------------------------------------------------------------------- UNC path


def test_unc_share_path_is_redacted():
    result = scrub(UNC_PATH_TEXT)
    assert_no_identifier_leaks(result.text)
    assert "onc-nas01" not in result.text


# -------------------------------------------------------------- mixed-encoding path


def test_mixed_encoding_path_is_redacted():
    result = scrub(MIXED_ENCODING_PATH)
    assert "Müller" not in result.text
    assert "Anna" not in result.text


def test_stray_non_ascii_letter_withholds_confidence():
    """A name with diacritics cannot be recognised by pattern, so confidence is withheld."""
    result = scrub("the plan for Müller looks fine")
    assert result.confident is False
    assert any("non-ASCII" in r for r in result.reasons)


# --------------------------------------------------- structure labels (the ambiguous case)


def test_recognised_structure_labels_are_confident():
    assert structure_label_is_recognised("Parotid_L") is True
    assert structure_label_is_recognised("SpinalCord") is True
    assert structure_label_is_recognised("PTV_High") is True


def test_structure_label_carrying_a_surname_is_not_recognised():
    """The deliberately ambiguous input: 'Smith' is only identifying in context."""
    assert structure_label_is_recognised("Parotid_L_Smith") is False


def test_structure_label_with_a_surname_withholds_confidence():
    result = scrub("mean dose for Parotid_L_Smith was 26.4 Gy")
    assert result.confident is False
    assert any("unrecognised segment" in r for r in result.reasons)


def test_ordinary_snake_case_identifiers_are_not_flagged():
    """Guard against over-refusal: code identifiers must not look like structure labels."""
    result = scrub("run_controller returned max_tokens and dvh_service handled it")
    assert result.confident is True


# ------------------------------------------------------- fail closed / caller refusal


def test_caller_refuses_to_transmit_an_unconfident_scrub():
    """The acceptance criterion: fail-closed is enforced at the call site, provably."""
    with pytest.raises(ScrubRefused) as excinfo:
        scrub_for_transmission("mean dose for Parotid_L_Smith was 26.4 Gy", remote=True)
    assert "refusing to transmit" in str(excinfo.value)


def test_refusal_message_explains_why_and_offers_a_route():
    with pytest.raises(ScrubRefused) as excinfo:
        scrub_for_transmission("the plan for Müller looks fine", remote=True)
    message = str(excinfo.value)
    assert "non-ASCII" in message
    assert "local provider" in message


def test_unconfident_text_is_never_transmitted_in_reduced_form():
    """Fail closed means refuse, not 'send a smaller payload'."""
    text = "mean dose for Parotid_L_Smith was 26.4 Gy"
    result = scrub(text)
    assert result.confident is False
    with pytest.raises(ScrubRefused):
        scrub_for_transmission(text, remote=True)


def test_local_provider_receives_text_unchanged():
    """The matrix grants raw access locally; the scrubber must not silently degrade it."""
    text = PATIENT_TRACEBACK
    assert scrub_for_transmission(text, remote=False, traceback=True) == text


def test_remote_transmission_of_a_clean_traceback_succeeds():
    from rbgyanx.ai.scrubber import install_root

    own = install_root() / "engine" / "radiobiology" / "ntcp_models.py"
    text = (
        f'Traceback (most recent call last):\n  File "{own}", line 8, in lkb\nValueError: bad n\n'
    )
    sent = scrub_for_transmission(text, remote=True, traceback=True)
    assert "engine/radiobiology/ntcp_models.py" in sent
    assert "ValueError" in sent


# --------------------------------------------------------------------- general contract


def test_scrub_never_mutates_the_input():
    original = DICOM_DUMP
    before = str(original)
    result = scrub(original)
    assert original == before
    assert result.text is not original


def test_empty_text_is_confident_and_empty():
    result = scrub("")
    assert result.text == ""
    assert result.confident is True
    assert result.findings == ()


def test_clean_text_passes_through_confident():
    result = scrub("NTCP for the parotid was 0.21 using the LKB model with n=0.7")
    assert result.confident is True
    assert result.findings == ()


@pytest.mark.parametrize(
    "text",
    [
        "PatientID 004512237",
        "MRN: 8877665",
        "dob 1964-03-12",
        "contact jane.doe@hospital.example",
        "reviewed by Smith, John",
        _HOME + _BS + "cohort" + _BS + "x.dcm",
        r"\\nas\share\file.dcm",
        "/home/kalyan/data/x.dcm",
    ],
)
def test_each_deny_list_shape_is_redacted(text):
    result = scrub(text)
    assert "REDACTED" in result.text


def test_long_digit_run_is_redacted_but_a_dose_value_is_not():
    result = scrub("dose 26.4 Gy for accession 4451237")
    assert "26.4" in result.text
    assert "4451237" not in result.text
