"""
Qt shell smoke tests (v2 Phase 4 · Slice 3).

Runs the real window under the ``offscreen`` platform plugin, so it exercises actual Qt
widgets in CI without a display. Skips cleanly when PySide6 is absent — the Tkinter app and
the engine must stay testable on machines without Qt.

Covers: construction with branding, BASIC/ADVANCED gating, widgets -> RunRequest, a full
headless run rendered into the results table, and the embedded interactive DVH HTML.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from rbgyanx.qtapp import is_available

pytestmark = pytest.mark.unit

if not is_available():  # pragma: no cover - environment dependent
    pytest.skip("PySide6 not installed", allow_module_level=True)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from rbgyanx.qtapp.main_window import (  # noqa: E402 - must follow the platform setting
    AppMode,
    MainWindow,
)
from rbgyanx.services.run_controller import RunController  # noqa: E402
from rbgyanx.services.run_request import RunRequest  # noqa: E402
from rbgyanx.services.ui_policy import (  # noqa: E402
    ADVANCED_MODELS,
    BASIC_MODELS,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "data" / "dvh_txt"


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp):
    w = MainWindow()
    yield w
    w.close()


# ------------------------------------------------------------------ construction


def test_window_constructs_with_branding(window):
    assert window.windowTitle().startswith("rbGyanX")
    tabs = [window.tabs.tabText(i) for i in range(window.tabs.count())]
    assert tabs == ["Workflow", "Run", "Results"]
    # The existing rbGyanX icon is reused, not replaced.
    from rbgyanx.qtapp.branding import icon_path

    if icon_path() is not None:
        assert not window.windowIcon().isNull()


def test_existing_branding_assets_are_used():
    from rbgyanx.qtapp.branding import asset_dir, icon_path, splash_path

    assert asset_dir().name == "assets"
    assert icon_path() is not None and icon_path().name == "icon.png"
    assert splash_path() is not None and splash_path().name == "splash.png"


# -------------------------------------------------------------- BASIC / ADVANCED


def test_basic_mode_hides_research_controls(window):
    window.set_mode(AppMode.BASIC)
    assert window.mode == AppMode.BASIC
    assert not window.ml_check.isVisible()
    assert window.source_combo.currentText() == "dvh_txt"
    assert window.models == BASIC_MODELS
    assert len(window.models) == 1  # clinic sees one well-understood model


def test_advanced_mode_exposes_research_controls(window):
    window.set_mode(AppMode.ADVANCED)
    assert window.models == ADVANCED_MODELS
    assert len(window.models) > len(BASIC_MODELS)
    assert window.source_combo.isEnabled()


def test_mode_banner_reflects_mode(window):
    window.set_mode(AppMode.ADVANCED)
    assert "ADVANCED" in window.mode_banner.text()
    window.set_mode(AppMode.BASIC)
    assert "BASIC" in window.mode_banner.text()


# ------------------------------------------------------------ view -> model seam


def test_build_request_maps_widgets_to_headless_request(window):
    window.input_edit.setText(str(EXAMPLES))
    window.mode_combo.setCurrentText("NTCP")
    req = window.build_request()
    assert isinstance(req, RunRequest)
    assert req.analysis_mode == "NTCP"
    assert Path(req.input_path) == EXAMPLES


def test_invalid_request_is_rejected_before_running(window):
    window.input_edit.setText("")
    result = RunController().validate(window.build_request())
    assert not result.ok
    assert any("Input folder not selected" in e for e in result.errors)


# --------------------------------------------------------------- full run + plot


@pytest.fixture(scope="module")
def run_result():
    req = RunRequest(
        analysis_mode="NTCP",
        input_path=EXAMPLES,
        output_dir=Path.cwd(),
        input_source="dvh_txt",
    )
    return RunController().run_dvh_text(req, ntcp_models=BASIC_MODELS)


def test_headless_run_on_shipped_synthetic_data(run_result):
    assert run_result.ok
    assert run_result.n_files > 0
    assert len(run_result.structures) == run_result.n_files
    assert all(s.mean_dose_gy == s.mean_dose_gy for s in run_result.structures)  # not NaN


def test_results_table_is_populated(window, run_result):
    window.populate_results(run_result)
    assert window.table.rowCount() == len(run_result.structures)
    assert window.table.item(0, 0).text()  # structure name
    assert window.table.item(0, 2).text()  # mean dose


def test_embedded_dvh_html_is_interactive_plotly(window, run_result):
    html = window.dvh_html(run_result)
    assert "plotly" in html.lower()
    assert len(html) > 1000
    assert "<script" in html.lower()  # interactive, not a static image


def test_dvh_html_handles_empty_result(window):
    from rbgyanx.services.run_controller import RunResult

    html = window.dvh_html(RunResult(ok=True, structures=[]))
    assert "No plottable DVH" in html


def test_qtwebengine_is_available_for_embedding():
    """The interactive view needs QtWebEngine; flag early if the wheel lacks it."""
    pytest.importorskip("PySide6.QtWebEngineWidgets")


# ------------------------------------------------------------------------ PHI


def test_window_writes_nothing_on_run(window, run_result, tmp_path, monkeypatch):
    """Rendering results must not persist anything (export is explicit + user-chosen)."""
    monkeypatch.chdir(tmp_path)
    window.populate_results(run_result)
    assert not list(tmp_path.iterdir()), "the results view wrote files without being asked"


# --------------------------------------------------- Workflow screen (Slice 4)


def test_workflow_tab_is_present(window):
    assert window.tabs.tabText(0) == "Workflow"
    assert window.tabs.count() == 3


def test_workflow_lists_every_pipeline_step(window):
    from rbgyanx.qtapp.screens.workflow import STEPS

    assert len(STEPS) == 7  # 6 numbered steps, TCP and NTCP split at step 3
    for _label, attr in STEPS:
        assert attr in window.workflow._step_labels


def test_workflow_step_status_tracks_shared_pipeline_state(window):
    wf = window.workflow
    wf.state.step1_complete = True
    wf.refresh_status()
    assert wf._step_labels["step1_complete"].text() == "complete"
    assert wf._step_labels["step2_complete"].text() == "not started"


def test_step6_is_blocked_until_both_arms_complete(window):
    """Mirrors PipelineExecutionState.can_run_step6 — the same rule the Tkinter app uses."""
    wf = window.workflow
    wf.state.reset()
    wf.refresh_status()
    assert "blocked" in wf._step_labels["step6_complete"].text()

    wf.state.tcp_step3_complete = True
    wf.state.ntcp_step3_complete = True
    wf.refresh_status()
    assert wf._step_labels["step6_complete"].text() == "not started"


def test_workflow_values_convert_to_request_kwargs(window, tmp_path):
    wf = window.workflow
    wf.input_edit.setText(str(EXAMPLES))
    wf.output_edit.setText(str(tmp_path))
    wf.mode_combo.setCurrentText("BOTH")
    kwargs = wf.to_request_kwargs()
    assert kwargs["analysis_mode"] == "BOTH"
    assert Path(kwargs["input_path"]) == EXAMPLES
    # Plain data only: no Qt objects leak into the headless layer.
    assert all(not type(v).__module__.startswith("PySide6") for v in kwargs.values())
    RunRequest(**kwargs)  # must be constructible


def test_workflow_respects_central_policy(window):
    from rbgyanx.services.ui_policy import UiPolicy

    window.set_mode(AppMode.BASIC)
    assert not window.workflow.ml_check.isVisible()
    assert not window.workflow.source_combo.isEnabled()
    assert window.workflow.source_combo.currentText() == "dvh_txt"

    window.set_mode(AppMode.ADVANCED)
    assert window.workflow.source_combo.isEnabled()
    assert window.workflow.policy.is_advanced
    assert window.models == UiPolicy.advanced().models()
