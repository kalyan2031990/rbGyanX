"""
Capability matrix tests (governed AI assistant, phase 1).

Every cell of the 9x5 matrix is asserted explicitly, with the expected value written out as a
literal. These tests deliberately do NOT loop over ``CAPABILITIES``: a test that reads the table
to check the table proves only that the table equals itself. If a cell is ever loosened, one of
the 45 assertions below has to be edited by hand, which is the point.

The matrix under test:

  Capability                    FROZEN+remote  FROZEN+local  SOURCE+remote  SOURCE+local  CI
  explain aggregate results          yes           yes            yes           yes       no
  explain patient-level results      NO            yes            NO            yes       no
  literature quick-compare           yes           yes            yes           yes       no
  read source code                   no            no             yes           yes       no
  modify source code                 no            no             yes           yes       no
  run tests                          no            no             yes           yes       no
  run on synthetic data              no            no             yes           yes       no
  run on real patient data           NO            NO             NO            yes       no
  read error / traceback         yes, scrubbed  yes, raw     yes, scrubbed   yes, raw     no
"""

from __future__ import annotations

import pytest
from rbgyanx.ai.capability import (
    CAPABILITIES,
    Capability,
    Column,
    InstallType,
    available_providers,
    column_for,
    detect_install_type,
    effective_remote,
    granted_capabilities,
    is_allowed,
    is_loopback_host,
    remote_disabled,
    scrub_required,
)
from rbgyanx.ai.config import PROVIDERS, Provider

REMOTE = PROVIDERS["claude"]  # remote=True
LOCAL = PROVIDERS["local"]  # remote=False, http://localhost:11434/v1

FROZEN = InstallType.FROZEN
SOURCE = InstallType.SOURCE
CI = InstallType.CI

#: Empty environment: the kill switch is off and no site config is consulted.
NO_ENV: dict[str, str] = {}


def allow(cap: Capability, provider: Provider, install: InstallType) -> bool:
    """Thin call helper. The expectation is always written out by hand at the call site."""
    return is_allowed(cap, provider, install, env=NO_ENV).allowed


# ------------------------------------------------------------------ row 1: aggregate


def test_explain_aggregate_row():
    assert allow(Capability.EXPLAIN_AGGREGATE, REMOTE, FROZEN) is True
    assert allow(Capability.EXPLAIN_AGGREGATE, LOCAL, FROZEN) is True
    assert allow(Capability.EXPLAIN_AGGREGATE, REMOTE, SOURCE) is True
    assert allow(Capability.EXPLAIN_AGGREGATE, LOCAL, SOURCE) is True
    assert allow(Capability.EXPLAIN_AGGREGATE, LOCAL, CI) is False


# --------------------------------------------------------------- row 2: patient level


def test_explain_patient_level_row():
    assert allow(Capability.EXPLAIN_PATIENT_LEVEL, REMOTE, FROZEN) is False
    assert allow(Capability.EXPLAIN_PATIENT_LEVEL, LOCAL, FROZEN) is True
    assert allow(Capability.EXPLAIN_PATIENT_LEVEL, REMOTE, SOURCE) is False
    assert allow(Capability.EXPLAIN_PATIENT_LEVEL, LOCAL, SOURCE) is True
    assert allow(Capability.EXPLAIN_PATIENT_LEVEL, LOCAL, CI) is False


# ----------------------------------------------------------------- row 3: literature


def test_literature_compare_row():
    assert allow(Capability.LITERATURE_COMPARE, REMOTE, FROZEN) is True
    assert allow(Capability.LITERATURE_COMPARE, LOCAL, FROZEN) is True
    assert allow(Capability.LITERATURE_COMPARE, REMOTE, SOURCE) is True
    assert allow(Capability.LITERATURE_COMPARE, LOCAL, SOURCE) is True
    assert allow(Capability.LITERATURE_COMPARE, LOCAL, CI) is False


# ------------------------------------------------------------------ row 4: read code


def test_read_code_row():
    assert allow(Capability.READ_CODE, REMOTE, FROZEN) is False
    assert allow(Capability.READ_CODE, LOCAL, FROZEN) is False
    assert allow(Capability.READ_CODE, REMOTE, SOURCE) is True
    assert allow(Capability.READ_CODE, LOCAL, SOURCE) is True
    assert allow(Capability.READ_CODE, LOCAL, CI) is False


# ---------------------------------------------------------------- row 5: modify code


def test_modify_code_row():
    assert allow(Capability.MODIFY_CODE, REMOTE, FROZEN) is False
    assert allow(Capability.MODIFY_CODE, LOCAL, FROZEN) is False
    assert allow(Capability.MODIFY_CODE, REMOTE, SOURCE) is True
    assert allow(Capability.MODIFY_CODE, LOCAL, SOURCE) is True
    assert allow(Capability.MODIFY_CODE, LOCAL, CI) is False


# ------------------------------------------------------------------ row 6: run tests


def test_run_tests_row():
    assert allow(Capability.RUN_TESTS, REMOTE, FROZEN) is False
    assert allow(Capability.RUN_TESTS, LOCAL, FROZEN) is False
    assert allow(Capability.RUN_TESTS, REMOTE, SOURCE) is True
    assert allow(Capability.RUN_TESTS, LOCAL, SOURCE) is True
    assert allow(Capability.RUN_TESTS, LOCAL, CI) is False


# -------------------------------------------------------------- row 7: run synthetic


def test_run_synthetic_row():
    assert allow(Capability.RUN_SYNTHETIC, REMOTE, FROZEN) is False
    assert allow(Capability.RUN_SYNTHETIC, LOCAL, FROZEN) is False
    assert allow(Capability.RUN_SYNTHETIC, REMOTE, SOURCE) is True
    assert allow(Capability.RUN_SYNTHETIC, LOCAL, SOURCE) is True
    assert allow(Capability.RUN_SYNTHETIC, LOCAL, CI) is False


# ------------------------------------------------------------ row 8: real patient data


def test_run_real_patient_data_row():
    assert allow(Capability.RUN_REAL_PATIENT_DATA, REMOTE, FROZEN) is False
    assert allow(Capability.RUN_REAL_PATIENT_DATA, LOCAL, FROZEN) is False
    assert allow(Capability.RUN_REAL_PATIENT_DATA, REMOTE, SOURCE) is False
    assert allow(Capability.RUN_REAL_PATIENT_DATA, LOCAL, SOURCE) is True
    assert allow(Capability.RUN_REAL_PATIENT_DATA, LOCAL, CI) is False


# ----------------------------------------------------------------- row 9: read error


def test_read_error_row():
    assert allow(Capability.READ_ERROR, REMOTE, FROZEN) is True
    assert allow(Capability.READ_ERROR, LOCAL, FROZEN) is True
    assert allow(Capability.READ_ERROR, REMOTE, SOURCE) is True
    assert allow(Capability.READ_ERROR, LOCAL, SOURCE) is True
    assert allow(Capability.READ_ERROR, LOCAL, CI) is False


# --------------------------------------------------------------- scrubbed vs raw


def test_read_error_is_scrubbed_for_remote_and_raw_for_local():
    """The 'yes, scrubbed' / 'yes, raw' distinction in row 9 is enforced, not cosmetic."""
    assert scrub_required(Capability.READ_ERROR, REMOTE, FROZEN) is True
    assert scrub_required(Capability.READ_ERROR, REMOTE, SOURCE) is True
    assert scrub_required(Capability.READ_ERROR, LOCAL, FROZEN) is False
    assert scrub_required(Capability.READ_ERROR, LOCAL, SOURCE) is False


def test_test_output_is_scrubbed_for_remote():
    assert scrub_required(Capability.RUN_TESTS, REMOTE, SOURCE) is True
    assert scrub_required(Capability.RUN_TESTS, LOCAL, SOURCE) is False


# ------------------------------------------------------------------- reason strings


def test_patient_level_refusal_names_the_provider_condition():
    decision = is_allowed(Capability.EXPLAIN_PATIENT_LEVEL, REMOTE, SOURCE, env=NO_ENV)
    assert decision.allowed is False
    assert "local" in decision.reason and "remote" in decision.reason


def test_read_code_refusal_names_the_install_condition():
    decision = is_allowed(Capability.READ_CODE, LOCAL, FROZEN, env=NO_ENV)
    assert decision.allowed is False
    assert "SOURCE" in decision.reason and "FROZEN" in decision.reason


def test_real_data_refusal_on_frozen_remote_names_both_conditions():
    decision = is_allowed(Capability.RUN_REAL_PATIENT_DATA, REMOTE, FROZEN, env=NO_ENV)
    assert decision.allowed is False
    assert "SOURCE" in decision.reason and "remote" in decision.reason


def test_ci_refusal_names_ci():
    decision = is_allowed(Capability.EXPLAIN_AGGREGATE, LOCAL, CI, env=NO_ENV)
    assert decision.allowed is False
    assert "CI" in decision.reason


def test_decision_unpacks_as_bool_and_reason():
    allowed, reason = is_allowed(Capability.EXPLAIN_AGGREGATE, LOCAL, SOURCE, env=NO_ENV)
    assert allowed is True
    assert isinstance(reason, str) and reason


# --------------------------------------------------------------------- CI disables all


def test_ci_disables_every_capability():
    """CI is a hard off switch: no capability survives it, for either provider."""
    for provider in (LOCAL, REMOTE):
        for cap in Capability:
            assert is_allowed(cap, provider, CI, env=NO_ENV).allowed is False
    assert granted_capabilities(LOCAL, CI, env=NO_ENV) == []
    assert granted_capabilities(REMOTE, CI, env=NO_ENV) == []


# ----------------------------------------------------------------------- kill switch


def test_kill_switch_env_removes_all_remote_providers():
    env = {"RBGYANX_AI_DISABLE_REMOTE": "1"}
    remaining = available_providers(PROVIDERS, env=env)
    assert remaining  # the local provider survives
    assert all(not p.remote for p in remaining.values())
    assert "claude" not in remaining
    assert "kimi" not in remaining
    assert "local" in remaining


def test_kill_switch_off_keeps_remote_providers():
    remaining = available_providers(PROVIDERS, env=NO_ENV)
    assert set(remaining) == set(PROVIDERS)


def test_kill_switch_refuses_a_remote_provider_that_slips_through():
    """Defence in depth: even if a remote provider is passed directly, it is refused."""
    env = {"RBGYANX_AI_DISABLE_REMOTE": "1"}
    decision = is_allowed(Capability.EXPLAIN_AGGREGATE, REMOTE, SOURCE, env=env)
    assert decision.allowed is False
    assert "institutional policy" in decision.reason


def test_kill_switch_does_not_restrict_local_providers():
    env = {"RBGYANX_AI_DISABLE_REMOTE": "1"}
    assert is_allowed(Capability.EXPLAIN_PATIENT_LEVEL, LOCAL, SOURCE, env=env).allowed is True


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_kill_switch_accepts_common_truthy_spellings(value):
    assert remote_disabled({"RBGYANX_AI_DISABLE_REMOTE": value}) is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_kill_switch_ignores_falsey_spellings(value):
    assert remote_disabled({"RBGYANX_AI_DISABLE_REMOTE": value}) is False


def test_kill_switch_from_site_config_file(tmp_path):
    site = tmp_path / "site.yaml"
    site.write_text("ai:\n  disable_remote: true\n", encoding="utf-8")
    env = {"RBGYANX_SITE_CONFIG": str(site)}
    assert remote_disabled(env) is True
    assert "claude" not in available_providers(PROVIDERS, env=env)


def test_site_config_without_the_flag_leaves_remote_enabled(tmp_path):
    site = tmp_path / "site.yaml"
    site.write_text("ai:\n  disable_remote: false\n", encoding="utf-8")
    env = {"RBGYANX_SITE_CONFIG": str(site)}
    assert remote_disabled(env) is False


def test_missing_site_config_is_not_an_error():
    env = {"RBGYANX_SITE_CONFIG": "/nonexistent/definitely/not/here.yaml"}
    assert remote_disabled(env) is False


# ------------------------------------------------------- axis 1 hardening: loopback


@pytest.mark.parametrize(
    "host", ["localhost", "LOCALHOST", "127.0.0.1", "127.1.2.3", "::1", "[::1]", "app.localhost"]
)
def test_loopback_hosts_are_local(host):
    assert is_loopback_host(host) is True


@pytest.mark.parametrize(
    "host",
    [
        "192.168.1.5",
        "10.0.0.7",
        "api.anthropic.com",
        "example.com",
        "0.0.0.0",
        "",
        None,
        "localhost.evil.com",
    ],
)
def test_non_loopback_hosts_are_remote(host):
    assert is_loopback_host(host) is False


def test_local_preset_pointed_off_machine_is_treated_as_remote():
    """The declarative flag alone is not a guarantee - base_url is user-overridable."""
    assert effective_remote(LOCAL) is False
    assert effective_remote(LOCAL, "https://elsewhere.example/v1") is True
    assert effective_remote(LOCAL, "http://192.168.1.5:11434/v1") is True


def test_patient_data_is_refused_when_a_local_preset_points_off_machine():
    """The whole point of the loopback check: this must not be rated safe for patient data."""
    decision = is_allowed(
        Capability.EXPLAIN_PATIENT_LEVEL,
        LOCAL,
        SOURCE,
        base_url="https://elsewhere.example/v1",
        env=NO_ENV,
    )
    assert decision.allowed is False


def test_remote_preset_cannot_be_made_local_by_a_loopback_url():
    """A remote-flagged provider stays remote even if pointed at localhost."""
    assert effective_remote(REMOTE, "http://localhost:11434/v1") is True


def test_unparseable_base_url_fails_closed():
    assert effective_remote(LOCAL, "http://[unterminated") is True


# ------------------------------------------------------------------ install detection


def test_ci_env_var_wins_over_everything(tmp_path):
    (tmp_path / ".git").mkdir()
    assert detect_install_type({"CI": "true"}, root=tmp_path, frozen=True) is InstallType.CI


@pytest.mark.parametrize(
    "var", ["CI", "CONTINUOUS_INTEGRATION", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL"]
)
def test_each_ci_marker_is_detected(var, tmp_path):
    assert detect_install_type({var: "1"}, root=tmp_path) is InstallType.CI


def test_frozen_binary_is_detected(tmp_path):
    (tmp_path / ".git").mkdir()
    assert detect_install_type({}, root=tmp_path, frozen=True) is InstallType.FROZEN


def test_git_checkout_is_a_source_install(tmp_path):
    (tmp_path / ".git").mkdir()
    assert detect_install_type({}, root=tmp_path, frozen=False) is InstallType.SOURCE


def test_wheel_install_without_git_defaults_to_frozen(tmp_path):
    """No git and not frozen: fall back to the more restrictive of the two."""
    assert detect_install_type({}, root=tmp_path, frozen=False) is InstallType.FROZEN


def test_ci_false_is_not_ci(tmp_path):
    (tmp_path / ".git").mkdir()
    assert detect_install_type({"CI": "false"}, root=tmp_path, frozen=False) is InstallType.SOURCE


# ------------------------------------------------------------------------ table shape


def test_matrix_covers_every_capability_and_column():
    """Structural guard: a new capability or column must be filled in, not defaulted."""
    assert len(CAPABILITIES) == len(Capability) == 9
    for cap in Capability:
        assert set(CAPABILITIES[cap]) == set(Column), f"{cap} is missing a column"
    assert sum(len(row) for row in CAPABILITIES.values()) == 45


def test_column_mapping():
    assert column_for(FROZEN, True) is Column.FROZEN_REMOTE
    assert column_for(FROZEN, False) is Column.FROZEN_LOCAL
    assert column_for(SOURCE, True) is Column.SOURCE_REMOTE
    assert column_for(SOURCE, False) is Column.SOURCE_LOCAL
    assert column_for(CI, True) is Column.CI
    assert column_for(CI, False) is Column.CI


def test_module_imports_no_llm_or_network_code():
    """Acceptance criterion: the gate must not depend on the thing it gates."""
    import rbgyanx.ai.capability as mod

    source = __import__("pathlib").Path(mod.__file__).read_text(encoding="utf-8")
    for forbidden in ("llm_client", "http_transport", "urllib.request", "import requests"):
        assert forbidden not in source, f"capability.py must not reference {forbidden}"
