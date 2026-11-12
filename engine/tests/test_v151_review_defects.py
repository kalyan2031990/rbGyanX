"""Defects #61, #62 and the Rancati citation string, all found by review of the v1.5.0 evidence.

Each test fails on v1.5.0 and passes after the fix.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd
import pytest
import yaml

PARAMS = Path(__file__).resolve().parents[1] / "config" / "site_params_ntcp_default.yaml"


# ------------------------------------------------------------------ #62
def _tcp_row(monkeypatch, refusal_reasons: list[str]) -> dict:
    """Drive TCPCalculator over a two-bin DVH, with and without an upstream refusal."""
    from config.site_params import load_site_params
    from radiobiology import tcp_calculator as mod
    from radiobiology.tcp_calculator import TCPCalculator

    dvh = pd.DataFrame({"dose_gy": [35.0, 70.0], "volume_frac": [0.5, 0.5]})
    # The calculator builds its frame from dvh_result.dvh_object; substitute the adapter so the
    # test drives a known DVH rather than constructing a dicompyler object.
    monkeypatch.setattr(mod, "dvh_object_to_dataframe", lambda _obj: dvh.copy())

    class _DvhResult:
        canonical_name = "PTV"
        quality_flag = "OK"
        dvh_object = object()

    meta = {
        "n_fractions": 35,
        "dose_per_fraction_gy": 2.0,
        "prescription_dose_gy": 70.0,
        "tcp_refusal_reasons": refusal_reasons,
    }
    calc = TCPCalculator()
    return calc.compute_all(_DvhResult(), meta, load_site_params("HN"), target_type="PTV")


def test_a_refused_target_keeps_its_percentile_dose_statistics(monkeypatch):
    """#62: D2/D50/D98 are read off the DVH and need no prescription.

    On v1.5.0 a SIB_LEVEL_UNKNOWN refusal returned before the shape features were computed, so
    all three came back absent. Measured on one arm: 129 of 245 targets refused, all 129 lost all
    three.
    """
    row = _tcp_row(monkeypatch, ["SIB_LEVEL_UNKNOWN"])
    assert row["tcp_refused"] is True
    assert "SIB_LEVEL_UNKNOWN" in row["tcp_refusal_reason"]
    for field in ("D2_gy", "D50_gy", "D98_gy"):
        assert field in row, f"{field} missing from a refused row"
        assert row[field] is not None and math.isfinite(float(row[field])), (
            f"{field} is not a finite number on a refused row: {row.get(field)!r}"
        )


def test_the_refused_row_reports_the_same_dose_statistics_as_a_scored_one(monkeypatch):
    """Refusing a TCP must not change a dose statistic: the DVH is the same DVH."""
    refused = _tcp_row(monkeypatch, ["SIB_LEVEL_UNKNOWN"])
    scored = _tcp_row(monkeypatch, [])
    assert scored["tcp_refused"] is False
    for field in ("D2_gy", "D50_gy", "D98_gy"):
        assert float(refused[field]) == pytest.approx(float(scored[field]))


def test_a_refused_target_still_reports_no_tcp(monkeypatch):
    """The refusal itself must survive the fix -- #62 is about what it takes with it."""
    row = _tcp_row(monkeypatch, ["SIB_LEVEL_UNKNOWN"])
    assert math.isnan(float(row["TCP_Poisson"]))


# ------------------------------------------------------------------ #61
def test_the_advanced_tcp_models_register_before_any_patient_is_processed():
    """#61: registration used to be a side effect of the ADVANCED stage, which runs after the
    patient loop, so the first patient of every process was scored without the model and every
    later one with it. The row set of tcp_results.csv then depended on how the run was batched.
    """
    from rbgyanx_engine.engine import _register_advanced_tcp_models

    class _Cfg:
        mode = "advanced"
        site = "HN"
        pinn_model_dir = None

    from radiobiology.model_registry import iter_tcp_models

    before = set(iter_tcp_models())
    assert _register_advanced_tcp_models(_Cfg()) is True
    after = set(iter_tcp_models())
    assert "PINN_STUB" in after, f"PINN_STUB not registered; registry holds {sorted(after)}"
    assert before <= after


# ------------------------------------------------------------------ the citation
def test_the_rancati_source_names_the_real_authors():
    """The source line named 'Fellin G', who is not an author of this paper.

    Rancati T, Fiorino C, Sanguineti G. NTCP modeling of subacute/late laryngeal edema scored by
    fiberoptic examination. Int J Radiat Oncol Biol Phys 2009;75(3):915-23.
    doi:10.1016/j.ijrobp.2009.04.087 -- three authors, verified against PubMed (PMID 19747783).
    """
    text = PARAMS.read_text(encoding="utf-8")
    # Only lines that carry an AUTHOR LIST -- 'Rancati 2009, p. 919' is a page pointer, not one.
    rancati_lines = [
        ln for ln in text.splitlines()
        if "Rancati T" in ln and "not an author" not in ln
    ]
    assert rancati_lines, "no Rancati citation found in the parameter file"
    for ln in rancati_lines:
        assert "Fellin" not in ln, f"'Fellin G' is still cited as an author: {ln.strip()}"
        assert "Sanguineti" in ln, f"Sanguineti G is missing from: {ln.strip()}"


def test_the_larynx_parameters_still_match_the_paper():
    """The values were right even while the author string was wrong; pin them so they stay right.

    LEUD best-fit, Rancati 2009: n = 1.17, m = 0.23, TD50 = 47.3 Gy.
    """
    data = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    larynx = data["HN"]["organs"]["Larynx"]
    probit = larynx["LKB_probit"]
    assert float(probit["TD50_gy"]) == pytest.approx(47.3)
    assert float(probit["m"]) == pytest.approx(0.23)
    assert float(probit["n"]) == pytest.approx(1.17)


def test_the_larynx_provenance_states_an_eqd2_basis():
    """#63's corroboration: the parameter file always said the fit is on EQD2 DVHs.

    The paper's own methods say the DVHs were "corrected into a linear quadratic equivalent one at
    2 Gy/fr with alpha/beta = 3 Gy". v1.5.0's code fed this fit physical dose anyway. If this
    assertion ever fails, #63's justification has gone with it.
    """
    data = yaml.safe_load(PARAMS.read_text(encoding="utf-8"))
    prov = data["HN"]["organs"]["Larynx"]["provenance"]["LKB_probit"]
    assert re.search(r"eqd2", str(prov.get("fractionation_basis", "")), re.I)
    assert float(data["HN"]["organs"]["Larynx"]["alpha_beta_gy"]) == pytest.approx(3.0)
