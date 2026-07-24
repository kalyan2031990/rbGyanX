"""
Centralised BASIC/ADVANCED policy (v2 Phase 4 · Slice 4).

The clinic-safe contract is only enforceable if there is ONE authority. These tests pin that:
UI gating defers to the engine's ``ModeController`` capabilities, BASIC never exposes a research
surface, and no Qt screen re-implements the decision locally.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from rbgyanx.logic.mode_controller import RunMode
from rbgyanx.services.ui_policy import (
    ADVANCED_MODELS,
    BASIC_MODELS,
    UiFeature,
    UiPolicy,
)

pytestmark = pytest.mark.unit

ALL_FEATURES = [
    getattr(UiFeature, n)
    for n in dir(UiFeature)
    if n.isupper() and isinstance(getattr(UiFeature, n), str)
]


# ------------------------------------------------------------------ construction


def test_policy_from_name_is_case_insensitive():
    assert UiPolicy.from_name("advanced").is_advanced
    assert UiPolicy.from_name("ADVANCED").is_advanced
    assert not UiPolicy.from_name("basic").is_advanced
    assert not UiPolicy.from_name("").is_advanced  # unknown -> safest mode


def test_default_is_the_clinic_safe_mode():
    assert UiPolicy().mode is RunMode.BASIC
    assert UiPolicy.basic().name == "BASIC"
    assert UiPolicy.advanced().name == "ADVANCED"


# ---------------------------------------------------------------------- gating


def test_basic_denies_every_research_surface():
    policy = UiPolicy.basic()
    for feature in (
        UiFeature.ML_TOGGLE,
        UiFeature.EXTRA_NTCP_MODELS,
        UiFeature.INTERACTIVE_EXPORT,
        UiFeature.INPUT_SOURCE_CHOICE,
        UiFeature.SHAP_VIEW,
        UiFeature.PARAMETER_EDITOR,
        UiFeature.AI_PANEL,
    ):
        assert not policy.allows(feature), f"BASIC must not expose {feature}"


def test_advanced_allows_every_feature_the_engine_permits():
    """ADVANCED unlocks research surfaces — EXCEPT ones the engine governs off entirely.

    ``parameter_sweep`` ("vary biological parameters systematically") and
    ``applicability_override`` ("calculate outside validated domains") are disabled in
    ModeController even in ADVANCED. The UI must honour that rather than open its own door,
    so the parameter editor stays unavailable in both modes.
    """
    from rbgyanx.logic.mode_controller import ModeController

    policy = UiPolicy.advanced()
    engine_caps = ModeController(RunMode.ADVANCED).get_capabilities()

    for feature in ALL_FEATURES:
        capability = UiFeature.CAPABILITY_MAP.get(feature)
        governed_off = capability is not None and not engine_caps.get(capability, False)
        if governed_off:
            assert not policy.allows(feature), (
                f"{feature} maps to '{capability}', which the engine disables even in ADVANCED; "
                "the UI must not expose it"
            )
        else:
            assert policy.allows(feature), f"ADVANCED should allow {feature}"


def test_parameter_editor_stays_closed_in_both_modes():
    """Regression guard for the governance rule above."""
    assert not UiPolicy.basic().allows(UiFeature.PARAMETER_EDITOR)
    assert not UiPolicy.advanced().allows(UiFeature.PARAMETER_EDITOR)


def test_clinic_safe_views_are_available_in_both_modes():
    """Sankey / cohort-flow / live-run are explanatory, not research controls."""
    for feature in (UiFeature.SANKEY_VIEW, UiFeature.COHORT_FLOW_VIEW, UiFeature.LIVE_RUN_VIEW):
        assert UiPolicy.basic().allows(feature)
        assert UiPolicy.advanced().allows(feature)


def test_gating_defers_to_the_engine_capability_model():
    """Features mapped to a governed capability must follow ModeController, not a local rule."""
    from rbgyanx.logic.mode_controller import CAPABILITIES, ModeController

    for feature, capability in UiFeature.CAPABILITY_MAP.items():
        assert capability in CAPABILITIES, f"{feature} maps to unknown capability {capability}"
        for mode in (RunMode.BASIC, RunMode.ADVANCED):
            expected = ModeController(mode).is_capability_enabled(capability)
            assert UiPolicy(mode).allows(feature) == expected, feature


def test_ai_panel_is_governed_and_denied_in_basic():
    """Phase 5 pre-condition: the AI panel is capability-gated, off in the clinic."""
    assert UiFeature.CAPABILITY_MAP[UiFeature.AI_PANEL] == "ai_integration"
    assert not UiPolicy.basic().allows(UiFeature.AI_PANEL)
    assert UiPolicy.advanced().allows(UiFeature.AI_PANEL)


# ---------------------------------------------------------------------- models


def test_model_sets_follow_mode():
    assert UiPolicy.basic().models() == BASIC_MODELS
    assert UiPolicy.advanced().models() == ADVANCED_MODELS
    assert len(BASIC_MODELS) == 1
    assert set(BASIC_MODELS) <= set(ADVANCED_MODELS)


def test_every_model_names_an_engine_model():
    from validation.ntcp_benchmark import NTCP_MODELS

    for label, cfg in ADVANCED_MODELS.items():
        assert cfg["model"] in NTCP_MODELS, f"{label} is not an engine model"
        assert cfg["params"], f"{label} has no fixed parameters"


def test_banner_and_contract_mention_the_mode():
    assert "BASIC" in UiPolicy.basic().banner()
    assert "ADVANCED" in UiPolicy.advanced().banner()
    assert UiPolicy.basic().contract_message()


# ------------------------------------------------- single-authority enforcement


def test_qt_screens_do_not_reimplement_mode_logic():
    """No screen may branch on a mode string; it must ask the policy."""
    qtapp = Path(__file__).resolve().parents[1] / "rbgyanx" / "qtapp"
    offenders: list[str] = []
    for py in qtapp.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Flag comparisons against a literal mode name, e.g. `self.mode == "ADVANCED"`.
            if isinstance(node, ast.Compare):
                for comparator in node.comparators:
                    if (
                        isinstance(comparator, ast.Constant)
                        and isinstance(comparator.value, str)
                        and comparator.value.upper() in {"ADVANCED", "BASIC"}
                    ):
                        offenders.append(f"{py.name}:{node.lineno}")
    assert not offenders, "mode compared literally instead of via UiPolicy.allows(): " + ", ".join(
        offenders
    )


def test_ui_policy_is_toolkit_free():
    src = (Path(__file__).resolve().parents[1] / "rbgyanx" / "services" / "ui_policy.py").read_text(
        encoding="utf-8"
    )
    for banned in ("PySide6", "tkinter", "PyQt"):
        assert banned not in src, f"ui_policy must not import {banned}"
