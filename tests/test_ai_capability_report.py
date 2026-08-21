"""
Pre-run capability report (phase H).

The owner needs to know what a remote provider will refuse BEFORE a cohort run, not discover it
half way through and mistake it for a bug. This script answers that, and it reads the implemented
matrix rather than restating the design in prose, so it cannot drift from what the code does.
"""

from __future__ import annotations

import importlib.util

import pytest
from rbgyanx.ai.capability import InstallType
from rbgyanx.ai.scrubber import install_root


def _module():
    spec = importlib.util.spec_from_file_location(
        "ai_capability_report", install_root() / "scripts" / "ai_capability_report.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


report_mod = _module()


# --------------------------------------------------------------- what Kimi will see


def test_kimi_denies_exactly_the_two_patient_capabilities():
    """The headline fact the owner needs going in."""
    text = report_mod.report("kimi", InstallType.SOURCE)
    assert "DENIED  (2): explain patient-level results, run on real patient data" in text
    assert "GRANTED (7)" in text


def test_kimi_is_reported_as_remote():
    text = report_mod.report("kimi", InstallType.SOURCE)
    assert "REMOTE - data leaves this machine" in text


def test_kimi_reports_the_k3_model_and_effort():
    text = report_mod.report("kimi", InstallType.SOURCE)
    assert "kimi-k3" in text
    assert "reasoning effort: max" in text


def test_each_denial_carries_its_reason():
    text = report_mod.report("kimi", InstallType.SOURCE)
    assert "requires a local on-machine provider" in text


def test_a_remote_denial_is_labelled_correct_behaviour():
    """A denial that looks like a defect gets worked around; one that is explained does not."""
    text = report_mod.report("kimi", InstallType.SOURCE)
    assert "correct behaviour, not a defect" in text
    assert "switch to the local provider" in text


# ------------------------------------------------------------------ other contexts


def test_local_grants_everything_on_a_source_install():
    text = report_mod.report("local", InstallType.SOURCE)
    assert "DENIED  (0): none" in text
    assert "LOCAL - nothing leaves this machine" in text


def test_ci_grants_nothing():
    text = report_mod.report("kimi", InstallType.CI)
    assert "GRANTED (0): none" in text


def test_a_frozen_install_hides_the_source_capabilities():
    text = report_mod.report("local", InstallType.FROZEN)
    assert "read source code               DENIED" in text
    assert "explain aggregate results      GRANTED" in text


def test_claude_denies_the_same_two_as_kimi():
    text = report_mod.report("claude", InstallType.SOURCE)
    assert "DENIED  (2): explain patient-level results, run on real patient data" in text


# ------------------------------------------------------------------------- the CLI


def test_cli_defaults_to_the_local_provider(capsys):
    assert report_mod.main([]) == 0
    assert "LOCAL - nothing leaves this machine" in capsys.readouterr().out


def test_cli_reports_a_named_provider(capsys):
    assert report_mod.main(["--provider", "kimi"]) == 0
    assert "kimi-k3" in capsys.readouterr().out


def test_cli_rejects_an_unknown_provider(capsys):
    assert report_mod.main(["--provider", "gpt5"]) == 2
    assert "unknown provider" in capsys.readouterr().err


def test_cli_can_override_the_install_type(capsys):
    assert report_mod.main(["--provider", "kimi", "--install", "ci"]) == 0
    assert "GRANTED (0): none" in capsys.readouterr().out


def test_cli_all_covers_every_selectable_provider(capsys):
    assert report_mod.main(["--all"]) == 0
    out = capsys.readouterr().out
    for label in ("Local (Ollama / llama.cpp)", "Claude (Anthropic)", "Kimi (Moonshot)"):
        assert label in out


def test_cli_all_respects_the_kill_switch(monkeypatch, capsys):
    monkeypatch.setenv("RBGYANX_AI_DISABLE_REMOTE", "1")
    assert report_mod.main(["--all"]) == 0
    out = capsys.readouterr().out
    assert "Kimi (Moonshot)" not in out
    assert "Local (Ollama / llama.cpp)" in out


def test_the_kill_switch_is_announced(monkeypatch):
    monkeypatch.setenv("RBGYANX_AI_DISABLE_REMOTE", "1")
    assert "kill switch     : ENGAGED" in report_mod.report("local", InstallType.SOURCE)


# ------------------------------------------------- it reads the matrix, not a copy of it


@pytest.mark.parametrize("provider", ["local", "claude", "kimi"])
def test_the_report_agrees_with_the_matrix(provider):
    """Guard against the report becoming prose that drifts from the implementation."""
    from rbgyanx.ai.capability import Capability, is_allowed
    from rbgyanx.ai.config import AiConfig

    cfg = AiConfig.from_env(provider)
    text = report_mod.report(provider, InstallType.SOURCE)
    for capability in Capability:
        expected = is_allowed(capability, cfg.preset, InstallType.SOURCE, base_url=cfg.base_url)
        verdict = "GRANTED" if expected.allowed else "DENIED"
        assert f"{capability.value:<30}"[: len(capability.value)] in text
        line = next(ln for ln in text.splitlines() if ln.strip().startswith(capability.value))
        assert verdict in line, f"{provider}/{capability.value} disagrees with the matrix"


def test_an_off_machine_local_preset_is_reported_as_remote(monkeypatch):
    """The report must not repeat the claim the preset makes about itself."""
    from rbgyanx.ai.config import AiConfig

    real = AiConfig.from_env

    def _patched(provider, env=None, **kw):
        return real(provider, env, base_url="https://elsewhere.example/v1", **kw)

    monkeypatch.setattr("rbgyanx.ai.config.AiConfig.from_env", staticmethod(_patched))
    text = report_mod.report("local", InstallType.SOURCE)
    assert "REMOTE - data leaves this machine" in text
    assert "explain patient-level results  DENIED" in text
