"""
Phase 4 acceptance — computation-layer verification locks.

The heavy lifting is already covered by existing suites (kept green, unchanged):
  * DVH integrity reject-not-repair — `tests/test_dvh_integrity.py`
  * NaN-never-zero (gEUD / NTCP on empty / zero-volume / degenerate params) — `tests/test_edge_cases_hardening.py`
  * dosiomics / ML / XAI / PINN / Bayesian — `engine/tests/test_dosiomics.py`, `test_xai.py`,
    `test_pinn_registry.py`, `test_train_pinn.py`, `test_bayesian_ntcp.py`

This file locks the two Phase-4 points not already asserted: the NTCP parameter provenance now recorded
in the run manifest (4.3), and a direct re-affirmation of the reject-not-repair + NaN-not-zero contracts.
"""

from __future__ import annotations

import json
import math
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from dicom_io.dvh_integrity import DVHIntegrityError, validate_cumulative_dvh
from radiobiology.geud_tcp import compute_geud
from rbgyanx_engine.engine import _write_provenance

pytestmark = pytest.mark.unit


def test_provenance_records_ntcp_param_keys(tmp_path):
    """4.3 — the run manifest records which NTCP parameter set(s) were applied, de-duplicated & sorted."""
    cfg = SimpleNamespace(endpoint="ntcp", input_kind="dicom", mode="basic", input_dir=tmp_path)
    result = SimpleNamespace(
        output_dir=tmp_path,
        tcp_results=[],
        ntcp_results=[
            {"site_params_key": "HN"},
            {"site_params_key": "HN"},
            {"site_params_key": "LUNG"},
            {"canonical": "no_key_here"},
        ],
        physical_results=[],
        exit_code=0,
    )
    prov = json.loads(_write_provenance(cfg, result).read_text(encoding="utf-8"))
    assert prov["ntcp_site_params_keys"] == ["HN", "LUNG"]  # distinct, sorted, missing keys ignored


def test_provenance_key_present_even_with_no_ntcp(tmp_path):
    cfg = SimpleNamespace(endpoint="tcp", input_kind="dvh_txt", mode="basic", input_dir=tmp_path)
    result = SimpleNamespace(
        output_dir=tmp_path, tcp_results=[{}], ntcp_results=[], physical_results=[], exit_code=0
    )
    prov = json.loads(_write_provenance(cfg, result).read_text(encoding="utf-8"))
    assert prov["ntcp_site_params_keys"] == []  # always written, empty when no NTCP


def test_dvh_integrity_rejects_inverted_accepts_valid():
    """4.1 — a rising cumulative DVH is rejected (not repaired); a valid one is accepted & sorted."""
    d, v = validate_cumulative_dvh(
        np.array([0.0, 10.0, 20.0]), np.array([100.0, 60.0, 10.0]), structure="OAR"
    )
    assert v[0] >= v[-1]  # monotone non-increasing after sort
    with pytest.raises(DVHIntegrityError, match="RISES with dose"):
        validate_cumulative_dvh(
            np.array([0.0, 10.0, 20.0]), np.array([10.0, 60.0, 100.0]), structure="OAR"
        )


def test_metric_nan_never_becomes_zero():
    """4.2 — degenerate input yields NaN, never a silent 0.0."""
    zero_vol = pd.DataFrame({"dose_gy": [10.0], "volume_frac": [0.0]})
    assert math.isnan(compute_geud(None, 1.0))
    assert math.isnan(compute_geud(zero_vol, 1.0))
