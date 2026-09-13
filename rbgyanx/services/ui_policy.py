"""
Centralised BASIC / ADVANCED policy for the user interfaces (v2 Phase 4 · Slice 4).

Every screen asks this module what is allowed; no screen decides for itself. That is what keeps
the clinic-safe contract enforceable — a new panel cannot accidentally expose a research control
in BASIC mode, because visibility is data here, not scattered ``if`` statements.

This wraps the existing governance model in :mod:`rbgyanx.logic.mode_controller` (``RunMode`` +
``CAPABILITIES``) rather than inventing a second one, so the Qt UI, the Tkinter UI and the
engine all answer to the same authority.

Toolkit-free by design (see the services guard test), so the same policy drives Qt, Tkinter
and headless runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from rbgyanx.logic.mode_controller import CAPABILITIES, ModeController, RunMode

__all__ = ["UiFeature", "UiPolicy", "BASIC_MODELS", "ADVANCED_MODELS"]


class UiFeature:
    """Named UI surfaces whose availability depends on mode."""

    INPUT_SOURCE_CHOICE = "input_source_choice"  # DICOM vs DVH text
    ML_TOGGLE = "ml_toggle"
    EXTRA_NTCP_MODELS = "extra_ntcp_models"
    INTERACTIVE_EXPORT = "interactive_export"
    SANKEY_VIEW = "sankey_view"
    COHORT_FLOW_VIEW = "cohort_flow_view"
    SHAP_VIEW = "shap_view"
    LIVE_RUN_VIEW = "live_run_view"
    PARAMETER_EDITOR = "parameter_editor"
    AI_PANEL = "ai_panel"

    #: UI feature -> governed capability in mode_controller.CAPABILITIES (or None = mode only).
    CAPABILITY_MAP = {
        EXTRA_NTCP_MODELS: "model_comparison",
        PARAMETER_EDITOR: "parameter_sweep",
        SHAP_VIEW: "sensitivity_analysis",
        AI_PANEL: "ai_integration",
    }

    #: Features available in BASIC (the clinic-safe subset). Everything else is ADVANCED-only.
    BASIC_ALLOWED = frozenset({SANKEY_VIEW, COHORT_FLOW_VIEW, LIVE_RUN_VIEW})


#: NTCP models offered per mode. BASIC shows one well-understood model; ADVANCED adds the rest.
BASIC_MODELS: dict[str, dict[str, Any]] = {
    "LKB probit": {"model": "lkb_probit", "params": {"TD50_gy": 39.9, "m": 0.40}},
}
ADVANCED_MODELS: dict[str, dict[str, Any]] = {
    **BASIC_MODELS,
    "LKB log-logistic": {"model": "lkb_loglogit", "params": {"TD50_gy": 28.4, "gamma50": 0.6}},
    "Relative seriality": {
        "model": "rs_poisson",
        "params": {"D50_gy": 28.4, "gamma": 1.0, "s": 0.25},
    },
}


@dataclass
class UiPolicy:
    """Answers 'may this surface be shown?' for one mode."""

    mode: RunMode = RunMode.BASIC

    @classmethod
    def basic(cls) -> UiPolicy:
        return cls(RunMode.BASIC)

    @classmethod
    def advanced(cls) -> UiPolicy:
        return cls(RunMode.ADVANCED)

    @classmethod
    def from_name(cls, name: str) -> UiPolicy:
        return cls(RunMode.ADVANCED if str(name).strip().lower() == "advanced" else RunMode.BASIC)

    # ------------------------------------------------------------------ queries

    @property
    def is_advanced(self) -> bool:
        return self.mode is RunMode.ADVANCED

    @property
    def name(self) -> str:
        return "ADVANCED" if self.is_advanced else "BASIC"

    def allows(self, feature: str) -> bool:
        """True if ``feature`` may be shown/enabled in this mode.

        A feature mapped to a governed capability defers to :class:`ModeController`, so UI
        gating and engine gating cannot drift apart.
        """
        capability = UiFeature.CAPABILITY_MAP.get(feature)
        if capability is not None and capability in CAPABILITIES:
            return ModeController(self.mode).is_capability_enabled(capability)
        if feature in UiFeature.BASIC_ALLOWED:
            return True
        return self.is_advanced

    def models(self) -> dict[str, dict[str, Any]]:
        """NTCP model set for this mode."""
        return ADVANCED_MODELS if self.allows(UiFeature.EXTRA_NTCP_MODELS) else BASIC_MODELS

    def banner(self) -> str:
        """One-line mode statement for the status area."""
        return f"{self.name} mode — " + (
            "research controls enabled" if self.is_advanced else "clinic-safe defaults"
        )

    def contract_message(self) -> str:
        """The governance contract text for this mode (from the engine's authority)."""
        return ModeController(self.mode).get_contract_message()
