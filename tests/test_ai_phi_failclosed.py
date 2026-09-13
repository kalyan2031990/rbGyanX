"""
The PHI guard must fail closed: a flagged payload never reaches a remote provider.

Through v1.2.1 ``LLMClient.complete`` scanned for PHI, attached the findings to the response as a
warning, and then transmitted anyway. README.md and DISCLAIMER.md meanwhile told the reader that
remote providers "never receive patient data". The documentation was aspirational and the code was
not, so the fix was to the code.

These tests assert the guarantee the documentation now makes, in the form a reviewer would check
it: with a transport that records every call, a flagged payload must leave the transport untouched.
A test that only asserted ``PhiBlocked`` was raised would pass even if the request had already gone
out, so the recording transport -- not the exception -- is the actual assertion.

Two further properties are pinned here because both were bugs:

* the guard scans **every role**. Run-derived context is attached as a *system* message, and the
  old scan skipped that role, exempting the one part of the payload actually built from patient
  data;
* "remote" is decided by :attr:`AiConfig.is_remote`, which is loopback-aware. A preset flagged
  local but pointed at an off-machine URL is remote, and is blocked like any other remote.
"""

from __future__ import annotations

import pytest
from rbgyanx.ai import audit as audit_module
from rbgyanx.ai.config import AiConfig
from rbgyanx.ai.context import build_system_prompt
from rbgyanx.ai.llm_client import LLMClient, LLMMessage, PhiBlocked
from rbgyanx.ai.phi_guard import scan_for_phi

pytestmark = pytest.mark.unit

#: Text the scrubber reliably flags: an explicit DICOM field label plus a long digit run.
PHI_TEXT = "Why is NTCP high for PatientID 12345678?"

#: Text with nothing identifiable in it.
CLEAN_TEXT = "Why is the parotid NTCP higher than the spinal cord NTCP?"


class RecordingTransport:
    """A transport that records calls instead of making them.

    ``calls`` is the evidence: if the guard works, it stays empty for every blocked payload. This
    deliberately implements only ``complete`` (not ``complete_message``) so a call through either
    code path in :meth:`LLMClient.complete` would still be recorded here.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def complete(self, request, *, base_url, api_key):
        self.calls.append({"request": request, "base_url": base_url, "api_key": api_key})
        return "transport was reached"


def remote_config(**kw) -> AiConfig:
    """A genuinely remote provider with a key present, so ``is_ready`` is true."""
    return AiConfig(provider="claude", api_key="test-key-not-real", **kw)


def local_config(**kw) -> AiConfig:
    """The loopback provider. Nothing leaves the machine, so the guard only warns."""
    return AiConfig(provider="local", **kw)


# --------------------------------------------------------------------- sanity


def test_phi_text_is_actually_flagged() -> None:
    """Guard the fixture itself: if this text stopped being flagged, the tests below would pass vacuously."""
    assert scan_for_phi(PHI_TEXT), "fixture text must trip the scrubber for these tests to mean anything"


def test_clean_text_is_not_flagged() -> None:
    assert not scan_for_phi(CLEAN_TEXT)


def test_static_system_prompt_scans_clean() -> None:
    """The system prompt is scanned now, so a false positive in it would block every remote send."""
    assert not scan_for_phi(build_system_prompt())


# ------------------------------------------------------- the core requirement


def test_flagged_payload_is_never_transmitted_to_remote() -> None:
    """The requirement, stated directly: nothing reaches the transport."""
    transport = RecordingTransport()
    client = LLMClient(remote_config(), transport=transport)

    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)])

    assert transport.calls == [], "a flagged payload reached the transport -- the guard leaked"


def test_block_happens_before_the_transport_is_consulted() -> None:
    """Even a transport that raises on contact is never contacted."""

    class ExplodingTransport:
        def complete(self, request, *, base_url, api_key):
            raise AssertionError("the transport must not be reached for a flagged payload")

    client = LLMClient(remote_config(), transport=ExplodingTransport())
    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)])


def test_clean_payload_still_sends_to_remote() -> None:
    """Fail-closed must not mean fail-always: unflagged text goes through normally."""
    transport = RecordingTransport()
    client = LLMClient(remote_config(), transport=transport)

    response = client.complete([LLMMessage("user", CLEAN_TEXT)])

    assert len(transport.calls) == 1
    assert response.text == "transport was reached"
    assert not response.had_phi_warning


def test_local_provider_still_sends_flagged_text() -> None:
    """Local providers are exempt: the data never leaves the machine, and the user is warned."""
    transport = RecordingTransport()
    client = LLMClient(local_config(), transport=transport)

    response = client.complete([LLMMessage("user", PHI_TEXT)])

    assert len(transport.calls) == 1, "local sends must not be blocked"
    assert response.had_phi_warning, "the user should still be told what was spotted"


# ------------------------------------------------------------ no user override


def test_no_keyword_argument_can_override_the_block() -> None:
    """``complete`` exposes no force/allow/override parameter, and gains one only deliberately."""
    import inspect

    params = set(inspect.signature(LLMClient.complete).parameters)
    for forbidden in ("force", "allow_phi", "override", "confirm", "allow_remote", "acknowledge"):
        assert forbidden not in params, f"complete() grew an override parameter: {forbidden}"


@pytest.mark.parametrize(
    "env_var",
    [
        "RBGYANX_ALLOW_PHI",
        "RBGYANX_AI_ALLOW_PHI",
        "RBGYANX_DISABLE_PHI_GUARD",
        "RBGYANX_PHI_OVERRIDE",
        "RBGYANX_FORCE_SEND",
    ],
)
def test_no_environment_variable_can_override_the_block(monkeypatch, env_var: str) -> None:
    """No env var relaxes the guard. A future one added by accident fails here."""
    monkeypatch.setenv(env_var, "1")
    transport = RecordingTransport()
    client = LLMClient(remote_config(), transport=transport)

    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)])
    assert transport.calls == []


def test_retry_loop_does_not_smuggle_a_blocked_payload_through() -> None:
    """The block sits outside the retry loop, so retries cannot be a second chance at sending."""
    transport = RecordingTransport()
    client = LLMClient(remote_config(max_retries=5), transport=transport)

    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)])
    assert transport.calls == []


# ------------------------------------------------- every role, including system


def test_phi_in_an_attached_system_context_is_blocked() -> None:
    """The bypass that mattered most.

    The panel attaches run-derived context as a *system* message. The old scan filtered
    ``role != "system"``, so this payload scanned clean and was transmitted.
    """
    transport = RecordingTransport()
    client = LLMClient(remote_config(), transport=transport)

    messages = [
        LLMMessage("system", build_system_prompt()),
        LLMMessage("system", "Run summary: PatientID 87654321, mean dose 30 Gy"),
        LLMMessage("user", CLEAN_TEXT),
    ]

    with pytest.raises(PhiBlocked):
        client.complete(messages)
    assert transport.calls == []


def test_scan_covers_system_messages() -> None:
    """State it at the unit level too, so the cause is obvious when the test above fails."""
    client = LLMClient(remote_config())
    findings = client.scan([LLMMessage("system", "PatientID 12345678")])
    assert findings, "scan() must not skip system messages"


def test_phi_in_conversation_history_is_blocked() -> None:
    """History is replayed on every turn, so a flagged earlier turn must block later ones."""
    transport = RecordingTransport()
    client = LLMClient(remote_config(), transport=transport)

    messages = [
        LLMMessage("user", PHI_TEXT),
        LLMMessage("assistant", "Here is an explanation."),
        LLMMessage("user", CLEAN_TEXT),
    ]

    with pytest.raises(PhiBlocked):
        client.complete(messages)
    assert transport.calls == []


# ------------------------------------------------ loopback-aware remote rating


def test_preset_flagged_local_but_pointed_off_machine_is_blocked() -> None:
    """A "local" preset aimed at a remote URL is remote, and is blocked accordingly."""
    cfg = local_config(base_url="https://elsewhere.example/v1")
    assert cfg.is_remote, "a local preset pointed off-machine must rate as remote"

    transport = RecordingTransport()
    client = LLMClient(cfg, transport=transport)

    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)])
    assert transport.calls == []


def test_lan_endpoint_counts_as_remote_and_is_blocked() -> None:
    """DISCLAIMER.md says a LAN endpoint counts as remote. Hold the code to it."""
    cfg = local_config(base_url="http://192.168.1.5:11434/v1")
    assert cfg.is_remote

    transport = RecordingTransport()
    client = LLMClient(cfg, transport=transport)
    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)])
    assert transport.calls == []


@pytest.mark.parametrize("url", ["http://localhost:11434/v1", "http://127.0.0.1:11434/v1"])
def test_loopback_urls_are_not_blocked(url: str) -> None:
    """The exemption has to actually work for the providers it is meant for."""
    cfg = local_config(base_url=url)
    assert not cfg.is_remote

    transport = RecordingTransport()
    client = LLMClient(cfg, transport=transport)
    client.complete([LLMMessage("user", PHI_TEXT)])
    assert len(transport.calls) == 1


# ----------------------------------------------------------------- audit trail


def test_a_block_is_recorded_as_a_refusal(monkeypatch) -> None:
    """A refusal is an auditable event: it must be recorded, and recorded as "refused"."""
    captured: list[dict] = []

    def fake_record_refusal(**kw):
        captured.append(kw)

    # _audit_refusal imports at call time, so patching the module attribute is enough.
    monkeypatch.setattr(audit_module, "record_refusal", fake_record_refusal)

    client = LLMClient(remote_config(), transport=RecordingTransport())
    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)], capability="chat (test)")

    assert len(captured) == 1
    assert captured[0]["remote"] is True
    assert captured[0]["findings_redacted"] >= 1
    assert "payload" not in captured[0], "a refusal must not fingerprint what it declined to send"


def test_a_failing_audit_write_does_not_turn_a_block_into_something_else(monkeypatch) -> None:
    """Bookkeeping failure must not downgrade the refusal or leak the payload."""

    def boom(**kw):
        raise OSError("disk full")

    monkeypatch.setattr(audit_module, "record_refusal", boom)

    transport = RecordingTransport()
    client = LLMClient(remote_config(), transport=transport)
    with pytest.raises(PhiBlocked):
        client.complete([LLMMessage("user", PHI_TEXT)])
    assert transport.calls == []


# ------------------------------------------------------------- the exception


def test_blocked_exception_names_categories_but_never_values() -> None:
    """The error message has to be useful without echoing the identifier it found."""
    client = LLMClient(remote_config(), transport=RecordingTransport())

    with pytest.raises(PhiBlocked) as excinfo:
        client.complete([LLMMessage("user", PHI_TEXT)])

    text = str(excinfo.value)
    assert "12345678" not in text, "the exception echoed the flagged value"
    assert "dicom_field" in text or "id_number" in text
    assert excinfo.value.findings
