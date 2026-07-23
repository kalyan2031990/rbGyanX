"""
P2 de-duplication invariants.

Keeps the quarantine honest: no supported module may import the retired lineage code, and
the documented single benchmarking entry point must dispatch to the two separate paths.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from validation.benchmark import run_arm_benchmark

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[1]
LEGACY_NAMES = {
    "code1_dvh_preprocess",
    "code2_dvh_plot_and_summary",
    "code3_ntcp_analysis_ml",
    "code4_ntcp_output_QA_reporter",
    "code5_ntcp_factors_analysis",
    "code6_tcp_analysis",
    "code7_tcp_ntcp_integration",
    "qa_comprehensive_test_suite",
    "rbgyanx_qa_test_suite",
}
# Directories that make up the supported tool.
SUPPORTED = (
    "engine",
    "rbgyanx",
    "clinical",
    "utils",
    "qa",
    "models",
    "external_validation",
    "examples",
    "scripts",
    "tests",
)


def _imported_modules(py: Path) -> set[str]:
    try:
        tree = ast.parse(py.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_supported_code_does_not_import_legacy():
    offenders: list[str] = []
    for top in SUPPORTED:
        base = ROOT / top
        if not base.is_dir():
            continue
        for py in base.rglob("*.py"):
            if LEGACY_NAMES & _imported_modules(py):
                offenders.append(str(py.relative_to(ROOT)))
    assert not offenders, f"supported modules import quarantined legacy code: {offenders}"


def test_legacy_is_quarantined_not_at_repo_root():
    for name in LEGACY_NAMES:
        assert not (ROOT / f"{name}.py").exists(), f"{name}.py should live under legacy/"
        assert (ROOT / "legacy" / f"{name}.py").exists(), f"legacy/{name}.py missing"
    assert (ROOT / "legacy" / "README.md").exists()


def test_single_entry_point_rejects_unknown_kind():
    with pytest.raises(ValueError, match="unknown benchmark kind"):
        run_arm_benchmark(pd.DataFrame({"y": [0, 1]}), kind="bogus", endpoint="y")


def test_single_entry_point_requires_engine_model_for_ntcp():
    """The NTCP arm must not be runnable without naming an engine model + params."""
    df = pd.DataFrame({"y": [0, 1, 0, 1], "dose": [10.0, 50.0, 20.0, 60.0]})
    with pytest.raises(ValueError, match="requires an engine model"):
        run_arm_benchmark(df, kind="ntcp", endpoint="y", dose_metric_col="dose")


def test_single_entry_point_runs_the_ntcp_path():
    import numpy as np

    rng = np.random.default_rng(0)
    dose = rng.uniform(10, 60, 60)
    y = (rng.uniform(size=60) < 1 / (1 + np.exp(-(dose - 35) / 6))).astype(int)
    df = pd.DataFrame({"tox": y, "OAR_gEUD_gy": dose})
    table, extras = run_arm_benchmark(
        df,
        kind="ntcp",
        endpoint="tox",
        model="lkb_probit",
        params={"TD50_gy": 35.0, "m": 0.3},
        dose_metric_col="OAR_gEUD_gy",
        n_splits=3,
    )
    assert extras["classical_is_engine_model"] is True
    assert "T1" in set(table["tier"])
