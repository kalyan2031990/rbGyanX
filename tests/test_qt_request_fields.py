"""Every control the Qt app collects must reach the engine.

The Qt window used to call ``RunController.run_dvh_text``, which reads TPS DVH text and computes
classical NTCP only. It consumed ``input_path`` and nothing else, so the operator's analysis mode,
cancer site, input source, clinical file and ML toggle were collected, validated and then
discarded — and the output folder the validator insisted on was never written to. The cancer site
never even reached ``RunRequest``.

These tests fail if any of that regresses. Standing rule 4: no claim without a test that would
fail if the claim were false — a widget in the window is a claim.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from unittest.mock import patch

import pytest
from rbgyanx.services.run_controller import RunController
from rbgyanx.services.run_request import RunRequest

pytestmark = pytest.mark.unit


class _Recorded:
    """Stand-in EngineResult; only the fields the adapter reads."""

    exit_code = 0
    message = ""
    tcp_results = [
        {
            "raw_name": "PTV70",
            "AnonPatientID": "SYN-1",
            "Dmean_gy": 70.0,
            "target_type": "PTV",
            "TCP_Poisson": 0.91,
            "TCP_gEUD": 0.77,
            "TCP_mean": 0.84,  # an aggregate, not a model — must not appear as one
        }
    ]
    ntcp_results = [
        {
            "structure": "Larynx",
            "AnonPatientID": "SYN-1",
            "Dmean_gy": 30.0,
            "NTCP_LKB_probit": 0.12,
            "NTCP_RS": 0.08,
        }
    ]


def _request(tmp_path: Path, **over) -> RunRequest:
    (tmp_path / "case.txt").write_text("dvh", encoding="utf-8")
    kwargs = dict(
        analysis_mode="BOTH",
        input_path=tmp_path,
        output_dir=tmp_path / "out",
        input_source="dvh_txt",
        basic_mode=False,
        site="HN",
    )
    kwargs.update(over)
    return RunRequest(**kwargs)


# ------------------------------------------------------------------ the request carries the site


def test_run_request_has_a_site_field():
    """Without this the cancer-site selector cannot reach the engine at all."""
    names = {f.name for f in dataclasses.fields(RunRequest)}
    assert "site" in names


def test_normalised_preserves_the_site():
    assert RunRequest(site="  PROSTATE  ").normalised().site == "PROSTATE"


# ------------------------------------------------------------------ the controller forwards them


def test_run_engine_forwards_every_control(tmp_path):
    """The whole point: each collected control must arrive at the engine bridge."""
    seen: dict = {}

    def fake_bridge(**kwargs):
        seen.update(kwargs)
        return _Recorded(), ["[engine] ok"]

    with patch("rbgyanx.logic.engine_bridge.run_engine_analysis", fake_bridge):
        clinical = tmp_path / "clinical.csv"
        clinical.write_text("id,outcome\n", encoding="utf-8")
        req = _request(tmp_path, site="PROSTATE", enable_ml=True, clinical_file=clinical)
        result = RunController().run_engine(req)

    assert seen["endpoint"] == "both", "analysis_mode BOTH must map to the 'both' endpoint"
    assert seen["site_override"] == "PROSTATE", "the cancer site must reach the engine"
    assert seen["enable_ml"] is True, "the ML toggle must reach the engine"
    assert seen["outcome_csv"] == clinical, "the clinical file must reach the engine"
    assert seen["mode"] == "advanced", "basic_mode=False must select advanced mode"
    assert seen["input_dir"] == tmp_path
    assert seen["output_dir"] == tmp_path / "out", "the output folder must be used, not ignored"
    assert result.ok


@pytest.mark.parametrize(
    ("mode", "endpoint"), [("TCP", "tcp"), ("NTCP", "ntcp"), ("BOTH", "both")]
)
def test_analysis_mode_selects_the_endpoint(tmp_path, mode, endpoint):
    """Selecting TCP used to yield NTCP, because the mode was never read."""
    seen: dict = {}

    def fake_bridge(**kwargs):
        seen.update(kwargs)
        return _Recorded(), []

    with patch("rbgyanx.logic.engine_bridge.run_engine_analysis", fake_bridge):
        RunController().run_engine(_request(tmp_path, analysis_mode=mode))
    assert seen["endpoint"] == endpoint


def test_empty_site_means_let_the_engine_detect(tmp_path):
    """An unset selector must not be forwarded as the empty string."""
    seen: dict = {}

    def fake_bridge(**kwargs):
        seen.update(kwargs)
        return _Recorded(), []

    with patch("rbgyanx.logic.engine_bridge.run_engine_analysis", fake_bridge):
        RunController().run_engine(_request(tmp_path, site=""))
    assert seen["site_override"] is None


# ------------------------------------------------------------------ the result reaches the views


def test_engine_result_is_adapted_for_the_views(tmp_path):
    """TCP must survive into the result; before this it had nowhere to go."""
    with patch("rbgyanx.logic.engine_bridge.run_engine_analysis",
               lambda **k: (_Recorded(), [])):
        res = RunController().run_engine(_request(tmp_path))

    assert res.ok
    by_label = {s.label: s for s in res.structures}
    assert set(by_label) == {"PTV70", "Larynx"}

    ptv = by_label["PTV70"]
    assert ptv.is_target and ptv.target_type == "PTV"
    assert ptv.tcp == {"Poisson": 0.91, "gEUD": 0.77}, "TCP_mean is an aggregate, not a model"
    assert ptv.ntcp == {}, "a target must never carry an NTCP"

    oar = by_label["Larynx"]
    assert not oar.is_target
    assert oar.ntcp == {"LKB_probit": 0.12, "RS": 0.08}
    assert oar.tcp == {}, "an OAR must never carry a TCP"

    assert res.n_files == 1, "one patient, not one file per structure"


def test_engine_failure_is_reported_not_silently_empty(tmp_path):
    """A non-zero exit must surface as an error, never as a successful empty run."""

    class _Failed(_Recorded):
        exit_code = 2
        message = "engine refused: no target structure"
        tcp_results: list = []
        ntcp_results: list = []

    with patch("rbgyanx.logic.engine_bridge.run_engine_analysis", lambda **k: (_Failed(), [])):
        res = RunController().run_engine(_request(tmp_path))

    assert not res.ok
    assert any("refused" in e for e in res.errors)


def test_bridge_exception_is_reported(tmp_path):
    def boom(**kwargs):
        raise ValueError("unrecognised input")

    with patch("rbgyanx.logic.engine_bridge.run_engine_analysis", boom):
        res = RunController().run_engine(_request(tmp_path))
    assert not res.ok
    assert any("unrecognised input" in e for e in res.errors)


# ------------------------------------------------------------------ the engine is usable installed


def test_engine_path_resolves_when_the_package_is_importable():
    """In the frozen app and in a pip install there is no engine directory on disk.

    ``get_engine_root`` searches for ``engine_bundle/`` or ``engine/`` and finds neither, so this
    used to raise FileNotFoundError in every environment a user installs, while the engine sat
    importable in the bundle.
    """
    from rbgyanx.logic import engine_bridge

    with patch.object(engine_bridge, "get_engine_root",
                      side_effect=AssertionError("must not need a disk root")):
        assert engine_bridge.ensure_engine_on_path() is None


def test_engine_path_still_honours_an_explicit_root(tmp_path):
    from rbgyanx.logic import engine_bridge

    assert engine_bridge.ensure_engine_on_path(tmp_path) == tmp_path.resolve()


# ------------------------------------------------------------------ the window uses that path


def test_qt_worker_runs_the_engine(tmp_path):
    """The window must drive run_engine; run_dvh_text ignores five of the six controls."""
    pytest.importorskip("PySide6.QtWidgets")
    from rbgyanx.qtapp.main_window import _RunWorker

    called: list[str] = []

    def fake_run_engine(self, request):
        called.append(request.site)
        return RunController._adapt_engine_result(_Recorded())

    worker = _RunWorker(_request(tmp_path, site="LUNG"), {})
    with patch.object(RunController, "run_engine", fake_run_engine):
        worker.run()  # QThread.run is an ordinary method; no event loop needed

    assert called == ["LUNG"], "the worker must call run_engine and pass the operator's request"


def test_workflow_screen_emits_every_request_field():
    """A widget that collects a value nobody forwards is the defect this guards."""
    pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtWidgets import QApplication
    from rbgyanx.qtapp.screens.workflow import WorkflowScreen
    from rbgyanx.services.ui_policy import UiPolicy

    app = QApplication.instance() or QApplication([])
    assert app is not None
    screen = WorkflowScreen(UiPolicy.advanced())
    kwargs = screen.to_request_kwargs()

    # Every field the request understands must be supplied by the screen, or it is a dead control.
    expected = {f.name for f in dataclasses.fields(RunRequest)}
    assert expected - set(kwargs) == set(), f"not forwarded: {sorted(expected - set(kwargs))}"
    # And it must construct without error.
    RunRequest(**kwargs)
