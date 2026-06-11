"""Mode governance and classical-output immutability (paper §2.A)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from rbgyanx.logic.engine_bridge import run_engine_analysis
from rbgyanx.logic.mode_controller import ModeController, RunMode


def _fake_result():
    class R:
        exit_code = 0
        tcp_results = []
        ntcp_results = []
        logs = []
        tcp_benchmark_xlsx = None
        ntcp_benchmark_xlsx = None
        quantec_flags_csv = None
        plan_quality_xlsx = None
        patient_pdf = None
        site_detection_csv = None

    return R()


def test_basic_mode_disables_advanced_capabilities():
    mc = ModeController(RunMode.BASIC)
    assert not mc.is_capability_enabled("model_comparison")
    assert not mc.is_capability_enabled("ai_integration")


def test_enable_ml_ignored_in_basic_mode():
    """enable_ml=True without advanced mode must not activate ML in RunConfig."""
    captured = {}

    def fake_run(cfg):
        captured["enable_ml"] = cfg.enable_ml
        captured["mode"] = cfg.mode
        return _fake_result()

    patches = (
        patch("rbgyanx_engine.run_analysis", fake_run),
        patch("rbgyanx.logic.engine_bridge.detect_input_kind", return_value="dicom"),
        patch("rbgyanx.logic.engine_bridge.ensure_engine_on_path", return_value=Path(".")),
        patch("rbgyanx.logic.engine_bridge.publish_engine_outputs"),
    )
    for p in patches:
        p.start()
    try:
        run_engine_analysis(
            input_dir=Path("."),
            output_dir=Path("."),
            endpoint="ntcp",
            mode="basic",
            enable_ml=True,
        )
    finally:
        for p in patches:
            p.stop()
    assert captured.get("enable_ml") is False
    assert captured.get("mode") == "basic"


def test_advanced_mode_allows_ml_flag():
    captured = {}

    def fake_run(cfg):
        captured["enable_ml"] = cfg.enable_ml
        return _fake_result()

    patches = (
        patch("rbgyanx_engine.run_analysis", fake_run),
        patch("rbgyanx.logic.engine_bridge.detect_input_kind", return_value="dicom"),
        patch("rbgyanx.logic.engine_bridge.ensure_engine_on_path", return_value=Path(".")),
        patch("rbgyanx.logic.engine_bridge.publish_engine_outputs"),
    )
    for p in patches:
        p.start()
    try:
        run_engine_analysis(
            input_dir=Path("."),
            output_dir=Path("."),
            endpoint="ntcp",
            mode="advanced",
            enable_ml=True,
        )
    finally:
        for p in patches:
            p.stop()
    assert captured.get("enable_ml") is True
