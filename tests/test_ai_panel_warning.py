"""
Send-confirmation warning path (phase A).

The tool layer was already loopback-aware, but the confirmation dialog read ``cfg.is_remote``,
which was not. A preset flagged local and pointed at a remote endpoint therefore got the tool
gate right and the *user-facing* reassurance wrong: the dialog said the data was staying on the
machine while it left. The dialog is the one place a human looks for that reassurance, so it is
the one place it must not be wrong.
"""

from __future__ import annotations

import os

import pytest
from rbgyanx.ai.config import PROVIDERS, AiConfig
from rbgyanx.qtapp import is_available

pytestmark = pytest.mark.unit

if not is_available():  # pragma: no cover - environment dependent
    pytest.skip("PySide6 not installed", allow_module_level=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from rbgyanx.qtapp.screens.ai_panel import AiPanelScreen  # noqa: E402


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def panel(app):
    return AiPanelScreen()


OFF_MACHINE = "https://elsewhere.example/v1"


# ------------------------------------------------------- the property itself


def test_local_preset_on_loopback_is_not_remote():
    assert AiConfig(provider="local").is_remote is False


def test_local_preset_pointed_off_machine_is_remote():
    """The defect: this used to return False and the dialog reassured the user."""
    assert AiConfig(provider="local", base_url=OFF_MACHINE).is_remote is True


def test_local_preset_on_a_lan_host_is_remote():
    assert AiConfig(provider="local", base_url="http://192.168.1.5:11434/v1").is_remote is True


def test_remote_preset_stays_remote_even_on_loopback():
    cfg = AiConfig(provider="claude", base_url="http://localhost:11434/v1")
    assert cfg.is_remote is True


def test_is_ready_stays_keyed_on_the_declared_flag():
    """A self-hosted LAN endpoint is remote for data locality but needs no API key."""
    cfg = AiConfig(provider="local", base_url="http://192.168.1.5:11434/v1")
    assert cfg.is_remote is True
    assert cfg.is_ready is True, "a keyless self-hosted endpoint must not become unusable"


# --------------------------------------------------------- the panel warning path


def test_local_endpoint_gets_the_question_icon_and_local_wording(panel):
    warn, text = panel.confirmation_prompt(AiConfig(provider="local"), [])
    assert warn is False
    assert "LOCAL endpoint" in text
    assert "stays on your machine" in text


def test_off_machine_local_preset_gets_the_warning_icon(panel):
    """The acceptance criterion for phase A."""
    cfg = AiConfig(provider="local", base_url=OFF_MACHINE)
    warn, text = panel.confirmation_prompt(cfg, [])
    assert warn is True, "an off-machine endpoint must raise the warning icon"


def test_off_machine_local_preset_gets_remote_caution_text(panel):
    cfg = AiConfig(provider="local", base_url=OFF_MACHINE)
    _warn, text = panel.confirmation_prompt(cfg, [])
    assert "REMOTE" in text
    assert "NOT " in text and "on this machine" in text
    assert "stays on your machine" not in text


def test_off_machine_wording_names_the_endpoint(panel):
    """A user who chose 'Local' and sees a remote warning has to be told why."""
    cfg = AiConfig(provider="local", base_url=OFF_MACHINE)
    _warn, text = panel.confirmation_prompt(cfg, [])
    assert OFF_MACHINE in text


def test_declared_remote_provider_gets_the_warning_icon(panel):
    warn, text = panel.confirmation_prompt(AiConfig(provider="claude", api_key="k"), [])
    assert warn is True
    assert "REMOTE provider" in text


def test_findings_alone_raise_the_warning_on_a_local_endpoint(panel):
    """A local endpoint still warns -- and must explain that the data is not leaving.

    This previously asserted the dialog said "warning, not a block". That wording was correct
    when the guard warned and sent anyway; since v1.3.0 the remote case never reaches a dialog at
    all, so describing a waived block would be misleading. Reaching this branch with findings now
    implies the endpoint is local.
    """
    from rbgyanx.ai.phi_guard import scan_for_phi

    findings = scan_for_phi("PatientID 004512237")
    assert findings
    cfg = AiConfig(provider="local")
    assert not cfg.is_remote

    warn, text = panel.confirmation_prompt(cfg, findings)
    assert warn is True
    assert "PHI guard flagged" in text
    assert "on your machine" in text
    assert "not a block" not in text, "the dialog must not describe a waived block"


# ------------------------------------------------------- the remote case is blocked, not warned


def test_a_flagged_remote_send_is_blocked_outright(panel):
    """The v1.3.0 contract at the UI layer: no dialog, no choice.

    ``is_blocked`` mirrors the rule enforced in ``LLMClient.complete``; the panel consults it
    before building any confirmation dialog, so there is nothing for the user to click past.
    """
    from rbgyanx.ai.phi_guard import scan_for_phi

    findings = scan_for_phi("PatientID 004512237")
    cfg = AiConfig(provider="claude", api_key="k")

    assert panel.is_blocked(cfg, findings) is True


def test_a_clean_remote_send_is_not_blocked(panel):
    """Fail-closed must not mean fail-always."""
    cfg = AiConfig(provider="claude", api_key="k")
    assert panel.is_blocked(cfg, []) is False


def test_a_flagged_local_send_is_not_blocked(panel):
    """Local providers are exempt: nothing leaves the machine."""
    from rbgyanx.ai.phi_guard import scan_for_phi

    findings = scan_for_phi("PatientID 004512237")
    assert panel.is_blocked(AiConfig(provider="local"), findings) is False


def test_an_off_machine_local_preset_is_blocked(panel):
    """The loopback-aware rule applies to the block, not just to the wording."""
    from rbgyanx.ai.phi_guard import scan_for_phi

    findings = scan_for_phi("PatientID 004512237")
    cfg = AiConfig(provider="local", base_url=OFF_MACHINE)
    assert cfg.is_remote
    assert panel.is_blocked(cfg, findings) is True


def test_the_block_message_names_categories_but_not_values(panel):
    """The refusal has to be actionable without echoing the identifier it found."""
    from rbgyanx.ai.phi_guard import scan_for_phi

    findings = scan_for_phi("PatientID 004512237")
    cfg = AiConfig(provider="claude", api_key="k")

    message = panel.block_message(cfg, findings)

    assert "NOT sent" in message
    assert "004512237" not in message, "the block message echoed the flagged value"
    assert "cannot be overridden" in message
    assert "Local" in message, "the message must say what the user can do instead"


def test_a_clean_local_send_raises_nothing(panel):
    warn, _text = panel.confirmation_prompt(AiConfig(provider="local"), [])
    assert warn is False


@pytest.mark.parametrize("key", sorted(PROVIDERS))
def test_every_preset_produces_a_renderable_prompt(panel, key):
    warn, text = panel.confirmation_prompt(AiConfig(provider=key, api_key="k"), [])
    assert isinstance(warn, bool)
    assert text.startswith("Send this text to ")


# ------------------------------------------------------------- no stale call sites


def test_no_call_site_reads_the_raw_preset_flag_for_a_safety_decision():
    """Guard against the defect reappearing somewhere new."""
    from pathlib import Path

    from rbgyanx.ai.scrubber import install_root

    panel_src = Path(install_root(), "rbgyanx", "qtapp", "screens", "ai_panel.py").read_text(
        encoding="utf-8"
    )
    # The panel may read preset.remote only to explain *why* something is remote, never to
    # decide whether it is.
    assert "if cfg.preset.remote" not in panel_src
    assert "cfg.preset.remote or" not in panel_src
