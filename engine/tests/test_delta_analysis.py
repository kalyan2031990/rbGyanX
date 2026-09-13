"""Unit tests for plan comparison (ΔNTCP) without full DICOM I/O."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd

from rbgyanx_engine.delta_analysis import compare_plans
from rbgyanx_engine.run_config import EngineResult


def _fake_ntcp(pid: str, struct: str, ntcp: float) -> dict:
    return {
        "AnonPatientID": pid,
        "structure": struct,
        "site": "HN",
        "NTCP_LKB_loglogit": ntcp,
        "NTCP_LKB_probit": ntcp * 0.9,
        "NTCP_RS": ntcp * 0.8,
    }


def _fake_tcp(pid: str) -> dict:
    return {
        "AnonPatientID": pid,
        "TCP_Poisson": 0.7,
        "TCP_mean": 0.65,
        "UTCP": 0.6,
    }


def test_compare_plans_delta_and_recommendation(tmp_path, monkeypatch):
    mock_run = MagicMock(side_effect=[
        EngineResult(
            exit_code=0,
            output_dir=tmp_path / "plan_a",
            ntcp_results=[_fake_ntcp("P1", "Parotid_L", 0.30), _fake_ntcp("P1", "SpinalCord", 0.05)],
            tcp_results=[_fake_tcp("P1")],
        ),
        EngineResult(
            exit_code=0,
            output_dir=tmp_path / "plan_b",
            ntcp_results=[_fake_ntcp("P1", "Parotid_L", 0.20), _fake_ntcp("P1", "SpinalCord", 0.04)],
            tcp_results=[_fake_tcp("P1")],
        ),
    ])
    monkeypatch.setattr("rbgyanx_engine.delta_analysis.run_analysis", mock_run)
    delta, out = compare_plans(
        plan_a_dir=Path("a"),
        plan_b_dir=Path("b"),
        output_dir=tmp_path,
        delta_threshold_pct=5.0,
    )
    assert out.is_file()
    parotid = delta[delta["structure"] == "Parotid_L"].iloc[0]
    assert parotid["delta_NTCP_loglogit_pct"] == 10.0
    assert parotid["recommendation"] == "prefer_Plan_B"
    assert (tmp_path / "delta_tcp.xlsx").is_file()


def test_compare_plans_empty_ntcp(tmp_path, monkeypatch):
    mock_run = MagicMock(side_effect=[
        EngineResult(exit_code=0, output_dir=tmp_path / "a", ntcp_results=[]),
        EngineResult(exit_code=0, output_dir=tmp_path / "b", ntcp_results=[]),
    ])
    monkeypatch.setattr("rbgyanx_engine.delta_analysis.run_analysis", mock_run)
    delta, out = compare_plans(Path("a"), Path("b"), tmp_path)
    assert delta.empty
    assert out.is_file()
    pd.read_excel(out)
