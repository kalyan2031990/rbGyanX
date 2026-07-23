"""Mode governance: Ask rbGyanX / LLM only in ADVANCED."""

from rbgyanx.logic.mode_controller import ModeController, RunMode


def test_basic_mode_disables_ai_integration():
    mc = ModeController(RunMode.BASIC)
    assert not mc.is_capability_enabled("ai_integration")


def test_advanced_mode_enables_ai_integration():
    mc = ModeController(RunMode.ADVANCED)
    assert mc.is_capability_enabled("ai_integration")
