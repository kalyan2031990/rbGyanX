"""
The audit log is actually wired into the send path (phase E).

Phase 3 built the log and tested it thoroughly in isolation, and nothing called it. A log that
is correct but never written is worse than no log, because it looks like evidence exists. These
tests cover the wiring rather than the format: that a send produces a record, that the record
describes the send accurately, and that it still carries no payload.

The live counterpart is tests/test_ai_live_provider.py, which is opt-in.

Note on the v1.3.0 fail-closed change: sending suspected PHI to a *remote* provider is now
refused, so these tests send clean text when what they are checking is "a transmission was
recorded". The PHI-specific cases below use a local provider (where a flagged send still goes
through, because nothing leaves the machine) or assert the refusal record directly. Using
PHI-laden text as the generic fixture would now exercise the block instead of the wiring.
"""

from __future__ import annotations

import pytest
from rbgyanx.ai.audit import audit_path, read_records
from rbgyanx.ai.capability import detect_install_type
from rbgyanx.ai.config import AiConfig
from rbgyanx.ai.llm_client import LLMClient, LLMError, LLMMessage, LLMNotConfigured

DIRTY = "PatientID 004512237 - why is the parotid NTCP high for Doe, Jane?"

#: Nothing the scrubber flags, so a remote send is not blocked. Pinned by a test below.
CLEAN = "Why is the parotid NTCP higher than the spinal cord NTCP?"


class Fake:
    """A transport that returns a K3-shaped message."""

    def __init__(self, fail_times: int = 0):
        self.fail_times = fail_times
        self.calls = 0

    def complete_message(self, request, *, base_url, api_key):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("transient upstream error")
        return {"role": "assistant", "content": "explained.", "reasoning_content": "step 1..."}


@pytest.fixture()
def audit_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path))
    return tmp_path


def _send(text=CLEAN, provider="kimi", transport=None, **kw):
    client = LLMClient(AiConfig(provider=provider, api_key="sk-x"), transport=transport or Fake())
    return client.complete([LLMMessage("user", text)], **kw)


# ------------------------------------------------------------------ a send is recorded


def test_a_successful_send_writes_exactly_one_record(audit_dir):
    _send()
    assert len(read_records(audit_path())) == 1


def test_each_send_appends(audit_dir):
    for _ in range(3):
        _send()
    assert len(read_records(audit_path())) == 3


def test_the_record_describes_the_send(audit_dir):
    _send(provider="kimi")
    record = read_records(audit_path())[0]
    assert record["provider"] == "kimi"
    assert record["remote"] is True
    assert record["install_type"] == detect_install_type().value
    assert record["payload_bytes"] > 0
    assert len(record["payload_sha256"]) == 64


def test_the_capability_is_recorded_and_defaults_sensibly(audit_dir):
    _send()
    assert read_records(audit_path())[0]["capability"] == "chat (panel send)"


def test_a_caller_can_name_the_capability(audit_dir):
    _send(capability="explain aggregate results")
    assert read_records(audit_path())[0]["capability"] == "explain aggregate results"


def test_a_local_provider_is_recorded_as_local(audit_dir):
    _send(provider="local")
    record = read_records(audit_path())[0]
    assert record["provider"] == "local"
    assert record["remote"] is False


def test_an_off_machine_local_preset_is_recorded_as_remote(audit_dir):
    """The trail must agree with where the data went, not with the label on the preset."""
    client = LLMClient(
        AiConfig(provider="local", base_url="https://elsewhere.example/v1"), transport=Fake()
    )
    client.complete([LLMMessage("user", "hi")])
    assert read_records(audit_path())[0]["remote"] is True


def test_phi_findings_are_counted_not_stored(audit_dir):
    """A local send of flagged text is recorded, with the findings counted and not stored."""
    _send(DIRTY, provider="local")
    record = read_records(audit_path())[0]
    assert record["outcome"] == "sent"
    assert record["findings_redacted"] >= 1


# --------------------------------------------------- a refusal is recorded as a refusal


def test_the_clean_fixture_really_is_clean():
    """If CLEAN ever started tripping the guard, most tests here would fail confusingly."""
    from rbgyanx.ai.phi_guard import scan_for_phi

    assert not scan_for_phi(CLEAN)


def test_a_blocked_remote_send_is_recorded_as_refused(audit_dir):
    """The block is an auditable event, distinguishable from a transmission."""
    from rbgyanx.ai.llm_client import PhiBlocked

    with pytest.raises(PhiBlocked):
        _send(DIRTY, provider="kimi")

    records = read_records(audit_path())
    assert len(records) == 1
    assert records[0]["outcome"] == "refused"
    assert records[0]["remote"] is True
    assert records[0]["findings_redacted"] >= 1


def test_a_refusal_records_no_payload_at_all(audit_dir):
    """Nothing was sent, so there is nothing to measure or fingerprint."""
    from rbgyanx.ai.llm_client import PhiBlocked

    with pytest.raises(PhiBlocked):
        _send(DIRTY, provider="kimi")

    record = read_records(audit_path())[0]
    assert record["payload_bytes"] == 0
    raw = audit_path().read_text(encoding="utf-8")
    for token in ("004512237", "parotid", "Doe", "Jane", DIRTY):
        assert token not in raw, f"a refusal record leaked {token!r}"


# ------------------------------------------------------------- it still holds no payload


def test_the_payload_never_reaches_the_log(audit_dir):
    """Local provider, so the flagged text really is transmitted and really is recorded."""
    _send(DIRTY, provider="local")
    raw = audit_path().read_text(encoding="utf-8")
    for token in ("004512237", "parotid", "Doe", "Jane", DIRTY):
        assert token not in raw, f"the audit log leaked {token!r}"


def test_the_response_never_reaches_the_log(audit_dir):
    _send()
    raw = audit_path().read_text(encoding="utf-8")
    assert "explained." not in raw
    assert "step 1" not in raw


def test_the_api_key_never_reaches_the_log(audit_dir):
    _send()
    assert "sk-x" not in audit_path().read_text(encoding="utf-8")


# --------------------------------------------------------------- failures are not recorded


def test_a_failed_send_writes_no_record(audit_dir):
    client = LLMClient(
        AiConfig(provider="kimi", api_key="sk-x", max_retries=0), transport=Fake(fail_times=5)
    )
    with pytest.raises(LLMError):
        client.complete([LLMMessage("user", "hi")])
    assert read_records(audit_path()) == [], "a transmission that never happened was recorded"


def test_an_unconfigured_client_writes_no_record(audit_dir):
    client = LLMClient(AiConfig(provider="local"))  # NullTransport
    with pytest.raises(LLMNotConfigured):
        client.complete([LLMMessage("user", "hi")])
    assert read_records(audit_path()) == []


def test_a_retried_send_records_once(audit_dir):
    """One transmission, one record - retries are attempts, not separate transmissions."""
    client = LLMClient(
        AiConfig(provider="kimi", api_key="sk-x", max_retries=2), transport=Fake(fail_times=1)
    )
    resp = client.complete([LLMMessage("user", "hi")])
    assert resp.attempts == 2
    assert len(read_records(audit_path())) == 1


# --------------------------------------------------------------------- robustness


def test_an_unwritable_audit_dir_does_not_lose_the_answer(monkeypatch, tmp_path):
    """Bookkeeping must never cost the user their reply; this is the one quiet failure allowed."""
    monkeypatch.setenv("RBGYANX_AUDIT_DIR", str(tmp_path / "nested"))

    def _boom(*a, **k):
        raise OSError("read-only filesystem")

    monkeypatch.setattr("rbgyanx.ai.audit.record_transmission", _boom, raising=True)
    resp = _send()
    assert resp.text == "explained."


def test_the_suite_does_not_write_to_the_real_config_dir():
    """conftest redirects the audit dir for the whole session; this pins that it is in force."""
    import os

    assert os.environ.get("RBGYANX_AUDIT_DIR"), "the audit dir is not isolated during tests"
