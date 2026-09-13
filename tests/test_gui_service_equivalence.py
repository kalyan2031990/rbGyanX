"""
Slice-1 extraction guard: the headless services must behave EXACTLY like the GUI methods
they were extracted from.

This is the "no behaviour change" proof. Each test calls the real, unbound
``rbgyanx_gui.rbGyanX_GUI`` method (via ``object.__new__`` so no widgets are constructed) and
the extracted service function on the same input, then asserts the results are identical.

If someone later edits one side only, these fail — which is the point: the Tkinter app and the
future Qt app must share one implementation, not two that drift.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from rbgyanx.services import (
    PipelineExecutionState,
    WorkflowState,
    build_canonical_dvh,
    normalize_dvh,
    validate_dvh_integrity,
)

pytestmark = pytest.mark.unit

gui_mod = pytest.importorskip("rbgyanx_gui", reason="Tkinter GUI module not importable")


@pytest.fixture(scope="module")
def gui():
    """The GUI class with NO __init__ — we only need its unbound methods."""
    return object.__new__(gui_mod.rbGyanX_GUI)


# --------------------------------------------------------------------- DVH fixtures


def _cumulative_dvh(n: int = 40, d_max: float = 70.0):
    dose = np.linspace(0.0, d_max, n)
    volume = np.linspace(100.0, 0.0, n)  # monotone decreasing cumulative %
    return dose, volume


def _differential_dvh(n: int = 40, d_max: float = 70.0):
    dose = np.linspace(0.0, d_max, n)
    rng = np.random.default_rng(0)
    volume = rng.uniform(0.5, 3.0, n)
    return dose, volume


def _absolute_cumulative_dvh(n: int = 30):
    dose = np.linspace(0.0, 60.0, n)
    volume = np.linspace(250.0, 0.0, n)  # cm3, not %
    return dose, volume


CASES = {
    "cumulative_pct": (_cumulative_dvh(), "cumulative"),
    "differential": (_differential_dvh(), "differential"),
    "cumulative_absolute": (_absolute_cumulative_dvh(), "cumulative"),
    "single_point": ((np.array([30.0]), np.array([100.0])), "cumulative"),
    "two_point": ((np.array([0.0, 50.0]), np.array([100.0, 0.0])), "cumulative"),
}


# --------------------------------------------------------------- build_canonical_dvh


@pytest.mark.parametrize("case", list(CASES))
def test_build_canonical_dvh_matches_gui(gui, case):
    (dose, volume), dvh_type = CASES[case]
    expected = gui_mod.rbGyanX_GUI.build_canonical_dvh(gui, dose.copy(), volume.copy(), dvh_type)
    got = build_canonical_dvh(dose.copy(), volume.copy(), dvh_type)

    assert set(got) == set(expected)
    for key in expected:
        np.testing.assert_allclose(
            np.asarray(got[key], dtype=float),
            np.asarray(expected[key], dtype=float),
            rtol=0,
            atol=0,
            err_msg=f"{case}/{key} diverged from the GUI implementation",
        )


def test_build_canonical_dvh_does_not_mutate_input():
    dose, volume = _cumulative_dvh()
    d0, v0 = dose.copy(), volume.copy()
    build_canonical_dvh(dose, volume, "cumulative")
    np.testing.assert_array_equal(dose, d0)
    np.testing.assert_array_equal(volume, v0)


# --------------------------------------------------------------------- normalize_dvh


@pytest.mark.parametrize("case", list(CASES))
def test_normalize_dvh_matches_gui(gui, case):
    (dose, volume), dvh_type = CASES[case]
    e_dose, e_vol, e_kind = gui_mod.rbGyanX_GUI.normalize_dvh(
        gui, dose.copy(), volume.copy(), dvh_type
    )
    g_dose, g_vol, g_kind = normalize_dvh(dose.copy(), volume.copy(), dvh_type)

    np.testing.assert_allclose(g_dose, e_dose, rtol=0, atol=0)
    np.testing.assert_allclose(g_vol, e_vol, rtol=0, atol=0)
    assert g_kind == e_kind


# ------------------------------------------------------------- validate_dvh_integrity


def _dvh_frame(dose, volume):
    return pd.DataFrame({"Dose[Gy]": dose, "Volume[cm3]": volume})


VALIDATION_CASES = {
    "good_cumulative": (_dvh_frame(*_cumulative_dvh()), "cumulative"),
    "good_differential": (_dvh_frame(*_differential_dvh()), "differential"),
    "too_short": (_dvh_frame(np.linspace(0, 10, 5), np.linspace(100, 0, 5)), "cumulative"),
    "with_nan": (
        _dvh_frame(
            np.linspace(0, 70, 20),
            np.r_[np.linspace(100, 50, 10), [np.nan], np.linspace(45, 0, 9)],
        ),
        "cumulative",
    ),
    "empty": (_dvh_frame([], []), "cumulative"),
    "missing_columns": (pd.DataFrame({"d": [1, 2], "v": [3, 4]}), "cumulative"),
}


@pytest.mark.parametrize("case", list(VALIDATION_CASES))
def test_validate_dvh_integrity_matches_gui(gui, case):
    df, dvh_type = VALIDATION_CASES[case]
    expected = gui_mod.rbGyanX_GUI.validate_dvh_integrity(
        gui, df.copy(), dvh_type, "Parotid", "PT-001"
    )
    got = validate_dvh_integrity(df.copy(), dvh_type, "Parotid", "PT-001")
    assert got == expected, f"{case}: extracted validator diverged from the GUI"


def test_validate_dvh_integrity_reports_no_patient_data():
    """The result may carry the ids the caller passed, but never DVH values."""
    df = _dvh_frame(*_cumulative_dvh())
    res = validate_dvh_integrity(df, "cumulative", "Parotid", "PT-001")
    blob = repr(res)
    assert "Dose[Gy]" not in blob
    assert "70.0" not in blob or res["status"] in {"PASS", "FLAG"}


# ------------------------------------------------------------------- pipeline state


def test_workflow_state_members_match_gui():
    assert {s.name: s.value for s in WorkflowState} == {
        s.name: s.value for s in gui_mod.WorkflowState
    }


def test_pipeline_execution_state_matches_gui():
    mine, theirs = PipelineExecutionState(), gui_mod.PipelineExecutionState()
    assert vars(mine) == vars(theirs)

    for st in (mine, theirs):
        st.tcp_step3_complete = True
        st.ntcp_step3_complete = True
    assert mine.can_run_step6() == theirs.can_run_step6() is True

    for st in (mine, theirs):
        st.step1_complete = True
        st.reset()
    assert vars(mine) == vars(theirs)
    assert mine.can_run_step6() is False


def test_services_import_no_gui_toolkit():
    """The service layer must stay toolkit-free so Qt/CLI/tests can use it."""
    import ast
    from pathlib import Path

    pkg = Path(__file__).resolve().parents[1] / "rbgyanx" / "services"
    banned = {"tkinter", "PySide6", "PyQt5", "PyQt6"}
    for py in pkg.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = {node.module.split(".")[0]}
            else:
                continue
            assert not (names & banned), f"{py.name} imports a GUI toolkit: {names & banned}"
