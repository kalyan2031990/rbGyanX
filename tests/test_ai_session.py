"""
Assistant session tests (governed AI assistant, phase 7).

This is the state the panel header renders. It is tested without Qt on purpose: what the
assistant is allowed to do is a property of the configuration, not of the widget that shows it,
and a user has to be able to see that answer at a glance and have it be true.
"""

from __future__ import annotations

import pytest
from rbgyanx.ai.capability import Capability, InstallType
from rbgyanx.ai.session import KILL_SWITCH_NOTE, TOOLS_OFF_NOTE, AssistantSession

NO_ENV: dict[str, str] = {}


def session(**kwargs) -> AssistantSession:
    kwargs.setdefault("env", NO_ENV)
    kwargs.setdefault("install_type", InstallType.SOURCE)
    return AssistantSession(**kwargs)


# --------------------------------------------------------------------- off by default


def test_tools_are_off_by_default():
    """Opt-in means a fresh install has the tool layer inert until someone turns it on."""
    assert AssistantSession().tools_enabled is False


def test_no_tools_are_available_while_the_feature_is_off():
    assert session().available_tools() == []


def test_tools_appear_once_enabled():
    assert session(tools_enabled=True).available_tools()


def test_the_off_state_is_stated_not_silent():
    assert TOOLS_OFF_NOTE in session().notes()


# ------------------------------------------------------------------------- the header


def test_header_names_provider_install_and_capabilities():
    text = session().header_text()
    assert "Provider:" in text and "Install:" in text and "Allowed:" in text
    assert "SOURCE" in text


def test_header_shows_fewer_capabilities_on_a_remote_provider():
    local = session(provider_key="local").header_text()
    remote = session(provider_key="claude").header_text()
    assert "explain patient-level results" in local
    assert "explain patient-level results" not in remote


def test_header_shows_no_capabilities_in_ci():
    text = session(install_type=InstallType.CI).header_text()
    assert "none (CI)" in text


def test_ci_is_called_out_in_the_notes():
    notes = session(install_type=InstallType.CI).notes()
    assert any("disabled entirely" in n for n in notes)


def test_frozen_install_hides_the_source_capabilities():
    text = session(install_type=InstallType.FROZEN).header_text()
    assert "read source code" not in text
    assert "explain aggregate results" in text


# ----------------------------------------------------------------------- data locality


def test_local_provider_says_nothing_leaves():
    assert "nothing leaves this machine" in session().locality_text()


def test_remote_provider_says_patient_data_is_withheld():
    text = session(provider_key="claude").locality_text()
    assert "leave this machine" in text
    assert "withheld" in text


def test_a_local_preset_pointed_off_machine_is_reported_as_remote():
    """The declarative flag is not trusted: the header must not claim local when it is not."""
    s = session(provider_key="local", base_url="https://elsewhere.example/v1")
    assert s.remote is True
    assert "REMOTE" in s.locality_text()
    assert "not on this machine" in s.locality_text()
    assert "explain patient-level results" not in s.header_text()


# ------------------------------------------------------------------------ kill switch


def test_kill_switch_removes_remote_providers_from_the_selection():
    s = session(env={"RBGYANX_AI_DISABLE_REMOTE": "1"})
    assert "claude" not in s.selectable_providers()
    assert "kimi" not in s.selectable_providers()
    assert "local" in s.selectable_providers()


def test_kill_switch_is_explained_in_the_notes():
    s = session(env={"RBGYANX_AI_DISABLE_REMOTE": "1"})
    assert s.kill_switch_engaged is True
    assert KILL_SWITCH_NOTE in s.notes()


def test_a_removed_provider_falls_back_to_a_local_one():
    """Selecting a provider that policy has since removed must not leave a remote one active."""
    s = session(provider_key="claude", env={"RBGYANX_AI_DISABLE_REMOTE": "1"})
    assert s.remote is False
    assert s.provider.key == "local"


def test_no_kill_switch_keeps_every_provider():
    assert set(session().selectable_providers()) == {"local", "claude", "kimi"}


# ------------------------------------------------------------------------ explanations


def test_a_denied_capability_can_explain_itself():
    s = session(provider_key="claude")
    reason = s.explain(Capability.EXPLAIN_PATIENT_LEVEL)
    assert "local" in reason and "remote" in reason


def test_a_granted_capability_also_carries_a_reason():
    assert session().explain(Capability.EXPLAIN_AGGREGATE)


@pytest.mark.parametrize("install", [InstallType.FROZEN, InstallType.SOURCE, InstallType.CI])
def test_every_install_type_produces_a_renderable_header(install):
    text = session(install_type=install).header_text()
    assert text and "Provider:" in text
