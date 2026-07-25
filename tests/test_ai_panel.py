"""
AI panel — Phase 5 Slice A (no live network).

Covers the safety-critical, non-network foundation:
  * the PHI guard detects the patterns that matter and WARNS (never blocks);
  * provider config resolves keys from the env only and never leaks them;
  * the context builder is aggregate-by-default (no per-patient identifiers);
  * the client runs the guard, self-corrects/retries, and — with the default NullTransport —
    cannot reach any network;
  * ADVANCED-only gating for the panel feature.

A FakeTransport stands in for the real HTTP transport (which arrives in Slice B), so nothing
here touches the network.
"""

from __future__ import annotations

import pytest
from rbgyanx.ai import (
    AiConfig,
    LLMClient,
    LLMError,
    LLMMessage,
    LLMNotConfigured,
    NullTransport,
    build_system_prompt,
    redact,
    scan_for_phi,
    summarise_run,
)
from rbgyanx.ai.config import PROVIDERS

pytestmark = pytest.mark.unit


# ------------------------------------------------------------------- PHI guard


@pytest.mark.parametrize(
    "text,category",
    [
        ("PatientID: 12345", "dicom_field"),
        ("MRN 004512237", "id_number"),
        ("dob 1974-03-02", "date"),
        ("123-45-6789", "ssn"),
        ("Study 1.2.840.10008.1.2.1", "dicom_uid"),
        ("Contact jane.doe@hospital.org", "email"),
        ("Smith, John had a good response", "name_like"),
        (r"loaded C:\patients\PAR-016\dvh.txt", "file_path"),
    ],
)
def test_guard_flags_phi_patterns(text, category):
    findings = scan_for_phi(text)
    assert any(f.category == category for f in findings), f"missed {category} in {text!r}"


def test_guard_is_clean_on_aggregate_text():
    text = "LKB probit NTCP ranged 0.12-0.34 (mean 0.21) across 16 structures; AUC 0.60."
    assert scan_for_phi(text) == []


def test_guard_never_retains_raw_values():
    """Findings carry a masked sample, not the raw PHI."""
    findings = scan_for_phi("PatientID 004512237")
    idnum = next(f for f in findings if f.category == "id_number")
    assert idnum.sample != "004512237"
    assert set(idnum.sample) <= set("0*4...7 ") or "*" in idnum.sample


def test_guard_warns_but_does_not_raise():
    """The guard reports; it must never throw on content (warn-not-block)."""
    findings = scan_for_phi("PatientName: Doe, Jane  MRN 12345678")
    assert findings  # it warns
    # no exception == does not block


def test_redact_replaces_every_finding():
    text = "PatientID 12345678 dob 1974-03-02"
    out = redact(text)
    assert "12345678" not in out and "1974-03-02" not in out
    assert "[REDACTED:" in out


# --------------------------------------------------------------------- config


def test_config_resolves_key_from_env_only():
    cfg = AiConfig.from_env("kimi", env={"MOONSHOT_API_KEY": "sk-secret"})
    assert cfg.api_key == "sk-secret"
    assert cfg.is_remote and cfg.is_ready


def test_local_provider_needs_no_key_and_is_not_remote():
    cfg = AiConfig.from_env("local", env={})
    assert not cfg.is_remote
    assert cfg.is_ready  # local is always ready
    assert cfg.resolved_base_url.startswith("http://localhost")


def test_remote_without_key_is_not_ready():
    cfg = AiConfig.from_env("claude", env={})
    assert cfg.is_remote and not cfg.is_ready


def test_key_never_appears_in_repr_or_redacted():
    cfg = AiConfig.from_env("claude", env={"ANTHROPIC_API_KEY": "sk-topsecret"})
    assert "sk-topsecret" not in repr(cfg)
    assert cfg.redacted().api_key is None


def test_three_presets_exist():
    assert set(PROVIDERS) == {"local", "claude", "kimi"}


def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match="unknown AI provider"):
        AiConfig(provider="gpt-nope")


# -------------------------------------------------------------------- context


def _fake_result():
    from rbgyanx.services.run_controller import RunResult, StructureResult

    return RunResult(
        ok=True,
        n_files=2,
        structures=[
            StructureResult("Parotid_L", "PAT-1", mean_dose_gy=26.0, ntcp={"LKB": 0.21}),
            StructureResult("Parotid_R", "PAT-2", mean_dose_gy=24.0, ntcp={"LKB": 0.18}),
        ],
    )


def test_summary_is_aggregate_and_hides_patient_ids_by_default():
    text = summarise_run(_fake_result())
    assert "LKB" in text and "structures analysed: 2" in text
    assert "PAT-1" not in text and "PAT-2" not in text  # no per-patient identifiers
    assert scan_for_phi(text) == []  # the summary itself is PHI-clean


def test_summary_empty_for_no_structures():
    from rbgyanx.services.run_controller import RunResult

    assert summarise_run(RunResult(ok=True, structures=[])) == ""


# --------------------------------------------------------------------- client


class FakeTransport:
    """Records the request and returns a canned reply. Stands in for the real HTTP transport."""

    def __init__(self, reply="Here is an explanation.", fail_times=0):
        self.reply = reply
        self.fail_times = fail_times
        self.calls: list = []

    def complete(self, request, *, base_url, api_key):
        self.calls.append((request, base_url, api_key))
        if len(self.calls) <= self.fail_times:
            raise RuntimeError("transient upstream error")
        return self.reply


def _msgs(user_text):
    return [LLMMessage("system", build_system_prompt()), LLMMessage("user", user_text)]


def test_default_client_cannot_reach_the_network():
    """The shipped default is NullTransport — a live call is impossible in Slice A."""
    client = LLMClient(AiConfig.from_env("local"))
    assert isinstance(client.transport, NullTransport)
    with pytest.raises(LLMNotConfigured):
        client.complete(_msgs("explain this NTCP"))


def test_client_completes_over_a_transport():
    client = LLMClient(AiConfig.from_env("local"), transport=FakeTransport("hello"))
    resp = client.complete(_msgs("explain LKB probit"))
    assert resp.text == "hello"
    assert resp.attempts == 1
    assert not resp.had_phi_warning


def test_client_warns_on_phi_but_still_sends():
    """warn-not-block: a PHI hit attaches a warning yet the request still goes out."""
    fake = FakeTransport("ok")
    client = LLMClient(AiConfig.from_env("local"), transport=fake)
    resp = client.complete(_msgs("PatientID 12345678 — why is NTCP high?"))
    assert resp.had_phi_warning  # user is warned
    assert resp.text == "ok"  # but the send happened
    assert len(fake.calls) == 1


def test_client_self_corrects_and_retries():
    fake = FakeTransport("recovered", fail_times=2)
    client = LLMClient(AiConfig.from_env("local", max_retries=2), transport=fake)
    resp = client.complete(_msgs("draft a QA note"))
    assert resp.text == "recovered"
    assert resp.attempts == 3  # 1 + 2 retries


def test_client_gives_up_after_retries():
    fake = FakeTransport(fail_times=99)
    client = LLMClient(AiConfig.from_env("local", max_retries=1), transport=fake)
    with pytest.raises(LLMError, match="failed after 2 attempts"):
        client.complete(_msgs("hello"))


def test_system_prompt_never_leaves_via_outgoing_text():
    """The PHI scan and 'what would be sent' both exclude the system prompt only when intended."""
    client = LLMClient(AiConfig.from_env("local"), transport=FakeTransport())
    req = client.build_request(_msgs("hello world"))
    assert "hello world" in req.outgoing_text()
    assert build_system_prompt() not in req.outgoing_text()


# ---------------------------------------------------------------- gating


def test_ai_panel_is_advanced_only():
    from rbgyanx.services.ui_policy import UiFeature, UiPolicy

    assert not UiPolicy.basic().allows(UiFeature.AI_PANEL)
    assert UiPolicy.advanced().allows(UiFeature.AI_PANEL)
