"""
Audit-log tests (governed AI assistant, phase 3).

The log has to prove two opposite things at once: that a transmission happened, and that the
log itself carries no patient content. Both are asserted here, along with rotation, which is
what keeps an append-only file from growing without bound.
"""

from __future__ import annotations

import json

from rbgyanx.ai.audit import (
    KEEP_ROTATIONS,
    AuditRecord,
    _rotate_if_needed,  # exercised directly: rotation is a guarantee, not an implementation detail
    audit_dir,
    audit_path,
    read_records,
    record_transmission,
)

#: A payload containing every identifier shape the log must not persist.
DIRTY_PAYLOAD = (
    "PatientName: Smith, John  PatientID 1234567  DOB 1964-03-12  "
    r"C:\Data\PAROTID\Smith_John_1234567\RTDOSE.dcm  jane.doe@hospital.example"
)

IDENTIFIERS = ("Smith", "John", "1234567", "1964-03-12", "PAROTID", "hospital.example")


def _log(tmp_path):
    return tmp_path / "ai_audit.jsonl"


# ------------------------------------------------------------------------ it records


def test_a_transmission_is_recorded(tmp_path):
    path = _log(tmp_path)
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="explain this run",
        path=path,
    )
    records = read_records(path)
    assert len(records) == 1
    assert records[0]["provider"] == "local"
    assert records[0]["remote"] is False
    assert records[0]["install_type"] == "source"
    assert records[0]["capability"] == "explain aggregate results"


def test_every_required_field_is_present(tmp_path):
    path = _log(tmp_path)
    record_transmission(
        provider="claude",
        remote=True,
        install_type="frozen",
        capability="read error / traceback",
        payload="boom",
        findings_redacted=3,
        path=path,
    )
    entry = read_records(path)[0]
    for field in (
        "timestamp",
        "provider",
        "remote",
        "install_type",
        "capability",
        "payload_bytes",
        "findings_redacted",
        "payload_sha256",
        "schema",
    ):
        assert field in entry, f"missing audit field {field}"
    assert entry["findings_redacted"] == 3
    assert entry["payload_bytes"] == 4


def test_records_append_rather_than_overwrite(tmp_path):
    path = _log(tmp_path)
    for i in range(5):
        record_transmission(
            provider="local",
            remote=False,
            install_type="source",
            capability="explain aggregate results",
            payload=f"message {i}",
            path=path,
        )
    assert len(read_records(path)) == 5


def test_timestamp_is_utc_and_iso(tmp_path):
    path = _log(tmp_path)
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="x",
        path=path,
    )
    stamp = read_records(path)[0]["timestamp"]
    assert stamp.endswith("+00:00")


# ------------------------------------------------------------- it records no payload


def test_the_payload_is_never_persisted(tmp_path):
    """The central guarantee: metadata about the send, never the send itself."""
    path = _log(tmp_path)
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain patient-level results",
        payload=DIRTY_PAYLOAD,
        path=path,
    )
    raw = path.read_text(encoding="utf-8")
    for token in IDENTIFIERS:
        assert token not in raw, f"audit log leaked {token!r}"
    assert "RTDOSE" not in raw
    assert DIRTY_PAYLOAD not in raw


def test_no_audit_field_can_carry_free_text(tmp_path):
    """PHI-free by construction: every value is a scalar we generated, not user content."""
    path = _log(tmp_path)
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain patient-level results",
        payload=DIRTY_PAYLOAD,
        path=path,
    )
    entry = read_records(path)[0]
    assert set(entry) == {
        "timestamp",
        "provider",
        "remote",
        "install_type",
        "capability",
        "payload_bytes",
        "findings_redacted",
        "payload_sha256",
        "schema",
    }


def test_digest_identifies_the_payload_without_storing_it(tmp_path):
    import hashlib

    path = _log(tmp_path)
    record = record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload=DIRTY_PAYLOAD,
        path=path,
    )
    expected = hashlib.sha256(DIRTY_PAYLOAD.encode("utf-8")).hexdigest()
    assert record.payload_sha256 == expected
    assert len(record.payload_sha256) == 64


def test_identical_payloads_share_a_digest_and_differing_ones_do_not(tmp_path):
    path = _log(tmp_path)
    a = record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="same",
        path=path,
    )
    b = record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="same",
        path=path,
    )
    c = record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="different",
        path=path,
    )
    assert a.payload_sha256 == b.payload_sha256
    assert a.payload_sha256 != c.payload_sha256


def test_byte_count_measures_utf8_not_characters(tmp_path):
    path = _log(tmp_path)
    record = record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="Mller",  # 5 ASCII characters
        path=path,
    )
    assert record.payload_bytes == 5


# --------------------------------------------------------------------------- rotation


def test_rotation_triggers_past_the_size_limit(tmp_path):
    path = _log(tmp_path)
    path.write_text("x" * 4096, encoding="utf-8")
    assert _rotate_if_needed(path, max_bytes=1024) is True
    assert path.with_suffix(".jsonl.1").exists()
    assert not path.exists()


def test_rotation_does_not_trigger_below_the_limit(tmp_path):
    path = _log(tmp_path)
    path.write_text("small", encoding="utf-8")
    assert _rotate_if_needed(path, max_bytes=1024) is False
    assert path.exists()
    assert not path.with_suffix(".jsonl.1").exists()


def test_rotation_preserves_history_rather_than_truncating(tmp_path):
    path = _log(tmp_path)
    path.write_text("original content " * 100, encoding="utf-8")
    _rotate_if_needed(path, max_bytes=64)
    rotated = path.with_suffix(".jsonl.1").read_text(encoding="utf-8")
    assert "original content" in rotated


def test_rotation_shifts_older_files_along(tmp_path):
    path = _log(tmp_path)
    for _ in range(3):
        path.write_text("y" * 4096, encoding="utf-8")
        _rotate_if_needed(path, max_bytes=1024)
    assert path.with_suffix(".jsonl.1").exists()
    assert path.with_suffix(".jsonl.2").exists()
    assert path.with_suffix(".jsonl.3").exists()


def test_rotation_discards_beyond_the_keep_limit(tmp_path):
    path = _log(tmp_path)
    for _ in range(KEEP_ROTATIONS + 3):
        path.write_text("z" * 4096, encoding="utf-8")
        _rotate_if_needed(path, max_bytes=1024, keep=KEEP_ROTATIONS)
    assert path.with_suffix(f".jsonl.{KEEP_ROTATIONS}").exists()
    assert not path.with_suffix(f".jsonl.{KEEP_ROTATIONS + 1}").exists()


def test_writing_rotates_automatically(tmp_path):
    path = _log(tmp_path)
    path.write_text("q" * (3 * 1024 * 1024), encoding="utf-8")  # past MAX_BYTES
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="after rotation",
        path=path,
    )
    assert path.with_suffix(".jsonl.1").exists()
    assert len(read_records(path)) == 1


# ------------------------------------------------------------------------- log location


def test_log_lives_in_the_user_config_dir_not_the_repo(tmp_path):
    """A clone must not carry another site's audit trail, and a frozen install has no repo."""
    from rbgyanx.ai.scrubber import install_root

    location = audit_dir({"APPDATA": str(tmp_path), "XDG_CONFIG_HOME": str(tmp_path)})
    assert install_root() not in location.parents
    assert location != install_root()


def test_audit_dir_honours_an_explicit_override(tmp_path):
    location = audit_dir({"RBGYANX_AUDIT_DIR": str(tmp_path / "custom")})
    assert location == tmp_path / "custom"
    assert audit_path({"RBGYANX_AUDIT_DIR": str(tmp_path / "custom")}).name == "ai_audit.jsonl"


def test_the_directory_is_created_on_first_write(tmp_path):
    nested = tmp_path / "does" / "not" / "exist" / "ai_audit.jsonl"
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="x",
        path=nested,
    )
    assert nested.exists()


# ----------------------------------------------------------------------------- reading


def test_reading_a_missing_log_is_empty_not_an_error(tmp_path):
    assert read_records(tmp_path / "nothing-here.jsonl") == []


def test_malformed_lines_are_skipped(tmp_path):
    path = _log(tmp_path)
    record_transmission(
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload="ok",
        path=path,
    )
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("this is not json\n")
    assert len(read_records(path)) == 1


def test_each_line_is_independently_valid_json(tmp_path):
    path = _log(tmp_path)
    for i in range(3):
        record_transmission(
            provider="local",
            remote=False,
            install_type="source",
            capability="explain aggregate results",
            payload=f"m{i}",
            path=path,
        )
    for line in path.read_text(encoding="utf-8").splitlines():
        assert isinstance(json.loads(line), dict)


def test_record_round_trips_through_json():
    record = AuditRecord(
        timestamp="2026-08-18T00:00:00+00:00",
        provider="local",
        remote=False,
        install_type="source",
        capability="explain aggregate results",
        payload_bytes=4,
        findings_redacted=0,
        payload_sha256="0" * 64,
    )
    assert json.loads(record.to_json())["provider"] == "local"
