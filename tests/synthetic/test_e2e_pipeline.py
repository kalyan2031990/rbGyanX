"""End-to-end pipeline on synthetic TPS DVH (no PHI)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rbgyanx_engine import RunConfig, run_analysis
from tests.synthetic.tps_factory import write_synthetic_cohort

pytestmark = [pytest.mark.e2e, pytest.mark.integration]


def test_e2e_tcp_ntcp_txt_basic(tmp_path: Path) -> None:
    dvh_dir = tmp_path / "dvh_in"
    out_dir = tmp_path / "engine_out"
    write_synthetic_cohort(dvh_dir)

    cfg = RunConfig(
        endpoint="both",
        input_kind="dvh_txt",
        input_dir=dvh_dir,
        output_dir=out_dir,
        site="HN",
        enable_ml=False,
        mode="basic",
        no_uncertainty=True,
        cohort=False,
        dvh_glob="*.txt",
    )
    result = run_analysis(cfg)
    assert result.exit_code == 0
    assert len(result.tcp_results) >= 1
    # TPS txt reader maps structures to PTV/GTV/CTV only — OAR NTCP needs DICOM or engine path
    assert result.provenance_json is not None and result.provenance_json.is_file()
    assert result.qa_report_json is not None and result.qa_report_json.is_file()

    prov = json.loads(result.provenance_json.read_text(encoding="utf-8"))
    assert prov.get("engine") == "rbgyanx-engine"
    assert prov.get("input_kind") == "dvh_txt"

    if result.ntcp_benchmark_xlsx:
        assert result.ntcp_benchmark_xlsx.is_file()
    if result.tcp_benchmark_xlsx:
        assert result.tcp_benchmark_xlsx.is_file()


def test_e2e_advanced_mode_no_ml(tmp_path: Path) -> None:
    dvh_dir = tmp_path / "dvh_in"
    out_dir = tmp_path / "engine_adv"
    write_synthetic_cohort(dvh_dir)

    cfg = RunConfig(
        endpoint="tcp",
        input_kind="dvh_txt",
        input_dir=dvh_dir,
        output_dir=out_dir,
        site="HN",
        enable_ml=False,
        mode="advanced",
        no_uncertainty=True,
        dvh_glob="*.txt",
    )
    result = run_analysis(cfg)
    assert result.exit_code == 0
    assert len(result.tcp_results) >= 1
