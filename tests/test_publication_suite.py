"""
rbGyanX v1.x — Publication Test Suite
=======================================
Comprehensive validation for rbGyanX software paper submission.

Tests all engine modules with realistic synthetic data and published parameter values.
No patient DICOM data required — all fixtures are synthetic.

Key literature references:
  Emami et al. IJROBP 1991;21:109 · QUANTEC IJROBP 2010;76(3)
  Källman et al. Phys Med Biol 1992;37:871 · Zaider & Minerbo PMB 2000;45:279
  Brenner & Hall NEJM 1999;341:1581 · Park et al. Med Phys 2008;35:3252
  Deasy et al. IJROBP 2010;76:S10 · van Calster et al. Lancet Digit Health 2019

Run:
    pytest tests/test_publication_suite.py -v --tb=short
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Path setup — engine and repo root must be importable
# ---------------------------------------------------------------------------
_REPO = Path(__file__).parents[1]
_ENGINE = _REPO / "engine"
_ENGINE_ADV = _REPO / "engine_advanced"
for _p in (_REPO, _ENGINE, _ENGINE_ADV):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ---------------------------------------------------------------------------
# Shared DVH helpers with verified Dmean values
# ---------------------------------------------------------------------------

def make_uniform_dvh(dose_gy: float, n_bins: int = 50) -> pd.DataFrame:
    """Differential DVH: 100% volume at dose_gy (±1%)."""
    d = np.linspace(dose_gy * 0.99, dose_gy * 1.01, n_bins)
    return pd.DataFrame({"dose_gy": d, "volume_frac": np.ones(n_bins) / n_bins})


def make_ramp_dvh(d_min: float, d_max: float, n_bins: int = 100) -> pd.DataFrame:
    """Linear differential DVH from d_min to d_max."""
    d = np.linspace(d_min, d_max, n_bins)
    return pd.DataFrame({"dose_gy": d, "volume_frac": np.ones(n_bins) / n_bins})


def make_hn_ptv_dvh(d_prescribed: float = 70.0, n_bins: int = 200) -> pd.DataFrame:
    """Realistic HN PTV: Gaussian spread ±4% around Rx dose."""
    rng = np.random.default_rng(42)
    d = np.sort(np.clip(rng.normal(d_prescribed, d_prescribed * 0.04, n_bins),
                        d_prescribed * 0.85, d_prescribed * 1.10))
    return pd.DataFrame({"dose_gy": d, "volume_frac": np.ones(n_bins) / n_bins})


def make_oar_dvh_nonzero(d_mean: float, d_max: float, n_bins: int = 100) -> pd.DataFrame:
    """
    OAR differential DVH with non-zero minimum dose.
    Doses span [d_mean*0.1, d_max] with exponential fall-off.
    Avoids D98=0 which would make D2/D98 ratio NaN.
    """
    d = np.linspace(d_mean * 0.1, d_max, n_bins)
    w = np.exp(-d / d_mean)
    return pd.DataFrame({"dose_gy": d, "volume_frac": w / w.sum()})


def make_dicompyler_dvh_result(dvh_df: pd.DataFrame, name: str = "Parotid_L",
                                category: str = "OAR"):
    """Build a DVHResult with dicompyler-core DVH so NTCPCalculator.compute_all works."""
    from dicompylercore.dvh import DVH
    from dicom_io.dvh_extractor import DVHResult

    doses = dvh_df["dose_gy"].values
    vols  = dvh_df["volume_frac"].values
    total = vols.sum()
    if total > 0:
        vols = vols / total

    n = len(doses)
    if n < 2:
        bins = np.array([0.0, max(doses[0] + 0.01, 0.01)]) if n == 1 \
               else np.array([0.0, 1.0])
        counts_cum = np.array([1000.0]) if n == 1 else np.array([])
    else:
        step = doses[1] - doses[0] if doses[1] > doses[0] else 0.01
        bins = np.concatenate([[max(0.0, doses[0] - step / 2)],
                               doses + step / 2])
        counts_diff = vols * 1000.0
        counts_cum  = np.cumsum(counts_diff[::-1])[::-1]

    dvh_obj = DVH(
        counts=counts_cum,
        bins=bins[:len(counts_cum) + 1],
        dvh_type="cumulative",
        dose_units="Gy",
        volume_units="cm3",
    )
    dmean = float((doses * vols).sum()) if n > 0 else 0.0
    return DVHResult(
        roi_number=1, raw_name=name, canonical_name=name, category=category,
        total_volume_cc=float(vols.sum() * 100),
        dmin_gy=float(doses.min()) if n > 0 else 0.0,
        dmean_gy=dmean,
        dmax_gy=float(doses.max()) if n > 0 else 0.0,
        dvh_object=dvh_obj, quality_flag="OK",
    )


# ---------------------------------------------------------------------------
# PART 1 — LQ model analytical verification
# ---------------------------------------------------------------------------

class TestLQModel:

    def setup_method(self):
        from radiobiology.lq_model import (bed, eqd2, eqd2_usc,
                                            survival_fraction_lq,
                                            treatment_time_days)
        self.bed   = bed
        self.eqd2  = eqd2
        self.eusc  = eqd2_usc
        self.sf    = survival_fraction_lq
        self.ttd   = treatment_time_days

    def test_bed_hn_conventional(self):
        """BED = D(1 + d/αβ): 70 Gy/2 Gy/αβ=10 → 84 Gy."""
        assert abs(self.bed(70.0, 2.0, 10.0) - 84.0) < 0.01

    def test_eqd2_identity_at_2gy(self):
        """EQD2(d=2 Gy) ≡ D for any total dose."""
        for D in [30.0, 50.0, 70.0]:
            assert abs(self.eqd2(D, 2.0, 10.0) - D) < 0.01

    def test_eqd2_hypo_gt_dose_high_ab(self):
        """SBRT d>2 Gy: EQD2 > D for high α/β tissue."""
        assert self.eqd2(36.25, 7.25, 10.0) > 36.25

    def test_eqd2_prostate_sbrt_equivalent(self):
        """Prostate α/β=1.5: SBRT 7.25×5 and conv 78/39 in similar EQD2 range."""
        assert abs(self.eqd2(36.25, 7.25, 1.5) - self.eqd2(78.0, 2.0, 1.5)) < 25.0

    def test_bed_monotone_with_dpf(self):
        beds = [self.bed(60.0, d, 10.0) for d in [1.5, 2.0, 3.0, 6.0]]
        assert all(beds[i] < beds[i + 1] for i in range(len(beds) - 1))

    def test_sf_zero_dose_is_1(self):
        assert self.sf(0.0, 0.3, 0.03) == 1.0

    def test_sf_exact_formula(self):
        α, β, d = 0.3, 0.03, 2.0
        assert abs(self.sf(d, α, β) - math.exp(-α * d - β * d ** 2)) < 1e-10

    def test_sf_decreases_with_dose(self):
        sfs = [self.sf(d, 0.3, 0.03) for d in [0.5, 1.0, 2.0, 4.0]]
        assert all(sfs[i] > sfs[i + 1] for i in range(len(sfs) - 1))

    def test_eqd2_usc_near_lq_below_transition(self):
        assert abs(self.eqd2(60.0, 3.0, 10.0) -
                   self.eusc(60.0, 3.0, 10.0, d_transition_gy=10.0)) < 3.0

    def test_treatment_time_35fx(self):
        assert 48 <= self.ttd(35, 5.0) <= 51

    def test_treatment_time_single_fraction(self):
        assert self.ttd(1) == 1.0

    def test_nan_on_zero_dose(self):
        assert math.isnan(self.bed(0.0, 2.0, 10.0))

    def test_nan_on_zero_ab(self):
        assert math.isnan(self.bed(60.0, 2.0, 0.0))


# ---------------------------------------------------------------------------
# PART 2 — TCP models
# ---------------------------------------------------------------------------

class TestPoissonTCP:

    def setup_method(self):
        from radiobiology.poisson_tcp import PoissonTCPCalculator
        from config.site_params import load_site_params
        self.calc = PoissonTCPCalculator()
        self.hn   = load_site_params("HN")
        self.pro  = load_site_params("PROSTATE")

    def test_tcp_bounded(self):
        r = self.calc.compute_tcp_dvh(make_hn_ptv_dvh(), 35, self.hn)
        if not math.isnan(r["tcp"]):
            assert 0.0 <= r["tcp"] <= 1.0

    def test_tcp_monotone_with_dose(self):
        """TCP increases with total dose."""
        tcps = [self.calc.compute_tcp_dvh(
            make_uniform_dvh(float(d)), int(d / 2), self.hn)["tcp"]
                for d in [40, 50, 60, 70, 80]]
        valid = [t for t in tcps if not math.isnan(t)]
        assert all(valid[i] <= valid[i + 1] + 0.01 for i in range(len(valid) - 1))

    def test_volume_normalisation_non_unity(self):
        """Non-unity volume sums: Dmean = weighted mean (CURSOR_FIXES §5)."""
        from radiobiology.poisson_tcp import _dvh_dmean
        dvh = pd.DataFrame({"dose_gy": [30.0, 50.0, 70.0],
                             "volume_frac": [2.0, 3.0, 5.0]})
        # Expected Dmean = (2×30 + 3×50 + 5×70)/10 = 56 Gy
        assert abs(_dvh_dmean(dvh) - 56.0) < 0.1

    def test_lq_caution_flag_sbrt(self):
        """DPF >> threshold: lq_caution must be True."""
        dvh = make_uniform_dvh(60.0, n_bins=20)  # 60 Gy/3 fx = 20 Gy/fx
        r = self.calc.compute_tcp_dvh(dvh, 3, self.hn)
        assert r["lq_caution"] is True

    def test_empty_dvh_gives_nan(self):
        from radiobiology.poisson_tcp import compute_n_eff_from_dvh
        n_eff, _, _ = compute_n_eff_from_dvh(pd.DataFrame(), 35, self.hn, "GTV", 49.0)
        assert math.isnan(n_eff)

    def test_required_output_keys(self):
        r = self.calc.compute_tcp_dvh(make_hn_ptv_dvh(), 35, self.hn)
        for k in ("tcp", "N_eff", "SF_total", "BED_gy", "EQD2_gy",
                  "repop_factor", "lq_caution", "Dmean_gy", "D95_gy"):
            assert k in r

    def test_prostate_alpha_beta(self):
        """Prostate α/β = 1.5 Gy (Brenner & Hall 1999)."""
        assert abs(self.pro.alpha_beta_gy - 1.5) < 0.1


class TestZaiderMinerboTCP:

    def setup_method(self):
        from radiobiology.zaider_minerbo import ZMTCPCalculator
        from config.site_params import load_site_params
        self.calc = ZMTCPCalculator(dead_fraction=0.85, t_obs_days=730.0)
        self.hn   = load_site_params("HN")

    def test_p0_bounded(self):
        b = math.log(2) / 7.0
        for t in [100, 365, 730]:
            p0 = self.calc._p0_single_cell(t, b, b * 0.85)
            assert 0.0 <= p0 <= 1.0

    def test_p0_increases_over_time(self):
        b, mu = 0.10, 0.08
        assert self.calc._p0_single_cell(10000, b, mu) >= \
               self.calc._p0_single_cell(30, b, mu)

    def test_zm_tcp_bounded(self):
        r = self.calc.compute_tcp_dvh(make_hn_ptv_dvh(), 35, self.hn)
        if not math.isnan(r["tcp"]):
            assert 0.0 <= r["tcp"] <= 1.0


class TestGEUDTCP:

    def setup_method(self):
        from radiobiology.geud_tcp import compute_geud
        self.geud = compute_geud

    def test_geud_a1_equals_dmean(self):
        """gEUD(a=1) = Dmean."""
        dvh  = make_uniform_dvh(60.0)
        dmean = float((dvh["dose_gy"] * dvh["volume_frac"]).sum())
        assert abs(self.geud(dvh, a=1.0) - dmean) < 0.5

    def test_geud_serial_gte_mean(self):
        dvh   = make_ramp_dvh(10.0, 70.0)
        dmean = float((dvh["dose_gy"] * dvh["volume_frac"]).sum())
        assert self.geud(dvh, a=10.0) >= dmean * 0.9

    def test_geud_parallel_lte_max(self):
        assert self.geud(make_ramp_dvh(0.0, 60.0), a=0.5) <= 60.0


class TestTCPEnsemble:

    def setup_method(self):
        from radiobiology.tcp_calculator import TCPCalculator
        from config.site_params import load_site_params
        self.calc = TCPCalculator()
        self.hn   = load_site_params("HN")
        self.plan = {"prescription_dose_gy": 70.0,
                     "n_fractions": 35, "dose_per_fraction_gy": 2.0}

    def test_all_four_models_present(self):
        r = self.calc.compute_all(make_hn_ptv_dvh(), self.plan, self.hn)
        for k in ("TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic"):
            assert k in r

    def test_tcp_mean_between_min_max(self):
        r    = self.calc.compute_all(make_hn_ptv_dvh(), self.plan, self.hn)
        vals = [r[k] for k in ("TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic")
                if not math.isnan(r[k])]
        if len(vals) >= 2 and not math.isnan(r["TCP_mean"]):
            assert min(vals) - 0.01 <= r["TCP_mean"] <= max(vals) + 0.01

    def test_tcp_range_non_negative(self):
        r = self.calc.compute_all(make_hn_ptv_dvh(), self.plan, self.hn)
        if not math.isnan(r["TCP_range"]):
            assert r["TCP_range"] >= 0.0

    def test_registered_model_in_ensemble(self):
        """Plugin via model registry appears in TCP output (CURSOR_FIXES §18)."""
        from radiobiology.model_registry import register_tcp_model

        class Const77:
            def compute_tcp_dvh(self, *a, **k):
                return {"tcp": 0.77, "model": "Const77"}

        register_tcp_model("PUB_CONST77", Const77())
        r = self.calc.compute_all(make_hn_ptv_dvh(), self.plan, self.hn)
        assert r.get("TCP_PUB_CONST77") == pytest.approx(0.77)


# ---------------------------------------------------------------------------
# PART 3 — NTCP model tests
# ---------------------------------------------------------------------------

class TestLKBFormulas:

    def setup_method(self):
        from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
        from radiobiology.ntcp.lkb_probit   import calculate_ntcp_lkb_probit
        from radiobiology.ntcp.rs_poisson    import calculate_ntcp_rs_poisson
        self.loglogit = calculate_ntcp_lkb_loglogit
        self.probit   = calculate_ntcp_lkb_probit
        self.rs       = calculate_ntcp_rs_poisson

    def test_loglogit_05_at_td50(self):
        """NTCP = 0.5 when gEUD = TD50 (parotid QUANTEC: TD50=26 Gy)."""
        assert abs(self.loglogit(26.0, 26.0, 3.0) - 0.5) < 0.01

    def test_probit_05_at_td50(self):
        assert abs(self.probit(26.0, 26.0, 0.40) - 0.5) < 0.01

    def test_loglogit_monotone(self):
        ntcps = [self.loglogit(g, 26.0, 3.0) for g in [5, 15, 26, 35, 50]]
        assert all(ntcps[i] < ntcps[i + 1] for i in range(len(ntcps) - 1))

    def test_ntcp_bounded_01(self):
        for g in [0.0, 10.0, 26.0, 50.0, 100.0]:
            assert 0.0 <= self.loglogit(g, 26.0, 3.0) <= 1.0

    def test_parotid_below_50pct_at_25gy(self):
        assert self.loglogit(25.0, 26.0, 3.0) < 0.5

    def test_rs_ntcp_bounded(self):
        """RS NTCP in [0,1] for a ramp OAR DVH."""
        dvh = make_ramp_dvh(5.0, 50.0)
        n   = self.rs(dvh, 66.5, 4.0, 0.14)  # spinal cord RS params
        assert 0.0 <= n <= 1.0

    def test_rs_ntcp_empty_dvh_zero(self):
        """Empty DVH -> 0 (no dose, no complication)."""
        assert self.rs(pd.DataFrame(), 66.5, 4.0, 0.14) == 0.0

    def test_rs_ntcp_bounded_single_bin(self):
        """RS NTCP in [0,1] for any single-bin DVH input."""
        for d in [5, 26, 60]:
            dvh = pd.DataFrame({"dose_gy": [float(d)], "volume_frac": [1.0]})
            n = self.rs(dvh, 26.0, 3.0, 0.50)
            assert 0.0 <= n <= 1.0, f"RS NTCP={n} out of bounds at d={d} Gy"

    def test_dual_implementation_agreement(self):
        """rbgyanx/core/ntcp re-exports engine implementation (CURSOR_FIXES §12)."""
        from rbgyanx.core.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit as app_fn
        for geud in [10.0, 26.0, 40.0]:
            assert abs(self.loglogit(geud, 26.0, 3.0) - app_fn(geud, 26.0, 3.0)) < 1e-9


class TestNTCPCalculatorFull:
    """NTCPCalculator with proper dicompyler DVHResult fixtures."""

    def setup_method(self):
        from radiobiology.ntcp_calculator import NTCPCalculator
        from config.site_ntcp_params import load_site_ntcp_params
        self.calc   = NTCPCalculator()
        self.hn     = load_site_ntcp_params("HN")

    def _organ(self, name: str):
        return self.hn.organs.get(name)

    def test_parotid_ntcp_finite(self):
        organ = self._organ("Parotid_L")
        if organ is None:
            pytest.skip("Parotid_L not in HN config")
        dvr = make_dicompyler_dvh_result(make_oar_dvh_nonzero(20.0, 45.0), "Parotid_L")
        row = self.calc.compute_all(dvr, {"n_fractions": 35, "dose_per_fraction_gy": 2.0},
                                    organ, "HN")
        ntcp = row.get("NTCP_LKB_loglogit", math.nan)
        if not math.isnan(ntcp):
            assert 0.0 <= ntcp <= 1.0

    def test_bdvh_applied_for_high_dpf(self):
        """bDVH correction when DPF > 2.3 Gy (CURSOR_FIXES §3)."""
        organ = self._organ("Parotid_L")
        if organ is None:
            pytest.skip("Parotid_L not in HN config")
        dvr = make_dicompyler_dvh_result(make_oar_dvh_nonzero(20.0, 40.0), "Parotid_L")
        row_ns = self.calc.compute_all(dvr, {"n_fractions": 20, "dose_per_fraction_gy": 3.0},
                                       organ, "HN")
        row_s  = self.calc.compute_all(dvr, {"n_fractions": 35, "dose_per_fraction_gy": 2.0},
                                       organ, "HN")
        assert row_ns.get("bdvh_applied") is True
        assert row_s.get("bdvh_applied") is False

    def test_empty_dvh_gives_nan_ntcp(self):
        """Empty OAR DVH → NaN NTCP, not spurious zero (CURSOR_FIXES §3)."""
        organ = self._organ("Parotid_L")
        if organ is None:
            pytest.skip("Parotid_L not in HN config")
        empty = make_dicompyler_dvh_result(
            pd.DataFrame({"dose_gy": [], "volume_frac": []}), "Parotid_L")
        row = self.calc.compute_all(
            empty, {"n_fractions": 35, "dose_per_fraction_gy": 2.0}, organ, "HN")
        for col in ("NTCP_LKB_loglogit", "NTCP_LKB_probit", "NTCP_RS"):
            if col in row and row[col] is not None:
                assert math.isnan(row[col]), \
                    f"{col}={row[col]} must be NaN for empty DVH"


# ---------------------------------------------------------------------------
# PART 4 — UTCP
# ---------------------------------------------------------------------------

class TestUTCP:

    def setup_method(self):
        from radiobiology.utcp import compute_utcp, attach_utcp_to_tcp_results
        self.compute = compute_utcp
        self.attach  = attach_utcp_to_tcp_results
        self.tcp = {
            "AnonPatientID": "HN001",
            "TCP_Poisson": 0.75, "TCP_gEUD": 0.72,
            "TCP_ZM": 0.70, "TCP_Logistic": 0.68,
        }
        self.ntcp = [
            {"AnonPatientID": "HN001", "structure": "SpinalCord",
             "NTCP_LKB_loglogit": 0.03},
            {"AnonPatientID": "HN001", "structure": "Parotid_L",
             "NTCP_LKB_loglogit": 0.18},
            {"AnonPatientID": "HN001", "structure": "Parotid_R",
             "NTCP_LKB_loglogit": 0.15},
        ]

    def test_utcp_formula(self):
        """UTCP = TCP × Π(1−NTCP_k) for scored OARs."""
        r = self.compute(self.tcp, self.ntcp, "HN")
        assert abs(r.UTCP - r.TCP_used * r.NTCP_product) < 0.001

    def test_utcp_leq_tcp(self):
        r = self.compute(self.tcp, self.ntcp, "HN")
        assert r.UTCP <= r.TCP_used + 1e-6

    def test_utcp_zero_ntcps_equals_tcp(self):
        ntcp_zero = [{"AnonPatientID": "HN001", "structure": s,
                      "NTCP_LKB_loglogit": 0.0}
                     for s in ("SpinalCord", "Parotid_L", "Parotid_R")]
        r = self.compute(self.tcp, ntcp_zero, "HN")
        assert abs(r.UTCP - r.TCP_used) < 0.01

    def test_utcp_nan_tcp_gives_nan(self):
        r = self.compute({"AnonPatientID": "X", "TCP_Poisson": math.nan},
                         self.ntcp, "HN")
        assert math.isnan(r.UTCP)

    def test_multi_patient_no_cross_contamination(self):
        """CURSOR_FIXES §13: patient OARs must not mix."""
        tcp  = [{"AnonPatientID": "P1", "TCP_Poisson": 0.70},
                {"AnonPatientID": "P2", "TCP_Poisson": 0.60}]
        ntcp = [
            {"AnonPatientID": "P1", "structure": "Parotid_L", "NTCP_LKB_loglogit": 0.15},
            {"AnonPatientID": "P2", "structure": "Parotid_L", "NTCP_LKB_loglogit": 0.40},
        ]
        self.attach(tcp, ntcp, "HN")
        u1, u2 = tcp[0].get("UTCP", math.nan), tcp[1].get("UTCP", math.nan)
        assert not math.isnan(u1) and not math.isnan(u2)
        assert u2 < u1

    def test_lung_alias_is_lung_conv(self):
        """LUNG → LUNG_CONV (not LUNG_SBRT) after CURSOR_FIXES §10."""
        from radiobiology.utcp import _UTCP_SITE_ALIASES
        assert _UTCP_SITE_ALIASES.get("LUNG") == "LUNG_CONV"


# ---------------------------------------------------------------------------
# PART 5 — QUANTEC 2010
# ---------------------------------------------------------------------------

class TestQUANTEC:

    def setup_method(self):
        from validation.quantec_checker import check_quantec_constraints
        self.check = check_quantec_constraints

    def test_cord_violation_55gy(self):
        assert any(r.severity == "VIOLATION"
                   for r in self.check(make_uniform_dvh(55.0), "SpinalCord"))

    def test_cord_clean_38gy(self):
        assert self.check(make_uniform_dvh(38.0), "SpinalCord") == []

    def test_parotid_warning_near_25gy(self):
        """Dmean 23.5 Gy is within 10% of 25 Gy QUANTEC limit → WARNING."""
        dvh = make_ramp_dvh(10.0, 37.0)  # Dmean = 23.5 Gy
        assert len(self.check(dvh, "Parotid_L")) >= 1

    def test_hippocampus_rtog0933(self):
        assert len(self.check(make_uniform_dvh(8.0), "Hippocampus_L")) >= 1

    def test_rectum_v70_added(self):
        """Rectum QUANTEC added by CURSOR_FIXES §11."""
        doses = np.concatenate([np.linspace(0, 69.9, 74), np.linspace(70, 80, 26)])
        dvh   = pd.DataFrame({"dose_gy": doses, "volume_frac": np.ones(100) / 100})
        assert len(self.check(dvh, "Rectum")) > 0

    def test_bladder_present(self):
        from validation.quantec_checker import QUANTEC_CONSTRAINTS
        assert "Bladder" in QUANTEC_CONSTRAINTS

    def test_liver_present(self):
        from validation.quantec_checker import QUANTEC_CONSTRAINTS
        assert "Liver" in QUANTEC_CONSTRAINTS

    def test_unknown_organ_empty(self):
        assert self.check(make_uniform_dvh(50.0), "NonExistent_XYZ") == []

    def test_empty_dvh_no_crash(self):
        assert self.check(pd.DataFrame(), "SpinalCord") == []

    def test_results_have_reference(self):
        for r in self.check(make_uniform_dvh(55.0), "SpinalCord"):
            assert r.reference and r.endpoint


# ---------------------------------------------------------------------------
# PART 6 — Site detection
# ---------------------------------------------------------------------------

class TestSiteDetection:

    def setup_method(self):
        from dicom_io.site_detector import detect_site
        self.detect = detect_site

    def _plan(self, label, rx=70.0, nfx=35, dpf=2.0):
        return {"plan_label": label, "prescription_dose_gy": rx,
                "n_fractions": nfx, "dose_per_fraction_gy": dpf}

    def _oars(self, *names):
        return [{"canonical": n} for n in names]

    def test_hn_keyword(self):
        assert self.detect(self._plan("HN OROPHARYNX"), [])["site"] == "HN"

    def test_hn_from_parotid_oar(self):
        assert self.detect(self._plan("PLAN01"),
                           self._oars("Parotid_L", "Mandible"))["site"] == "HN"

    def test_lung_keyword(self):
        assert self.detect(self._plan("NSCLC LUNG 60GY"), [])["site"] == "LUNG"

    def test_breast_keyword(self):
        assert self.detect(self._plan("LEFT BREAST PMRT"), [])["site"] == "BREAST"

    def test_brain_gbm_histology(self):
        r = self.detect(self._plan("GBM 60GY"), [])
        assert r["site"] == "BRAIN" and r["histology"] == "GBM"

    def test_brain_mets_histology(self):
        r = self.detect(self._plan("BRAIN METS WBRT"), [])
        assert r["site"] == "BRAIN" and r["histology"] == "METS"

    def test_prostate_keyword(self):
        """Prostate detection added in CURSOR_FIXES §22."""
        r = self.detect(self._plan("PROSTATE 78GY/39FX", 78.0, 39, 2.0),
                        self._oars("PTV", "Rectum"))
        assert r["site"] == "PROSTATE"

    def test_prostate_oar_detection(self):
        r = self.detect(self._plan("PLAN_ANON", 78.0, 39, 2.0),
                        self._oars("PTV", "Rectum", "Bladder", "FemoralHead_L"))
        assert r["site"] == "PROSTATE"

    def test_liver_keyword(self):
        r = self.detect(self._plan("HCC LIVER SBRT", 50.0, 5, 10.0), [])
        assert r["site"] == "LIVER"

    def test_ambiguous_plan_is_unknown(self):
        """Regression: was silently HN (CURSOR_FIXES §1)."""
        r = self.detect(self._plan("PATIENT_ANON", 76.0, 38, 2.0), self._oars("PTV"))
        assert r["site"] == "UNKNOWN"

    def test_high_confidence_from_keyword(self):
        assert self.detect(self._plan("HN LARYNX"), [])["confidence"] in ("HIGH", "USER")

    def test_user_override_confidence(self):
        from dicom_io.site_detector import resolve_pipeline_site
        detection = self.detect(self._plan("ANON"), [])
        _, info = resolve_pipeline_site("HN", detection)
        assert info["confidence"] == "USER"


# ---------------------------------------------------------------------------
# PART 7 — Statistical validation metrics
# ---------------------------------------------------------------------------

class TestValidationMetrics:

    def setup_method(self):
        from validation.validation_metrics import (
            validate_ntcp_model, compute_auc, compute_brier,
            hosmer_lemeshow, expected_calibration_error, bootstrap_ci,
        )
        self.validate  = validate_ntcp_model
        self.auc       = compute_auc
        self.brier     = compute_brier
        self.hl        = hosmer_lemeshow
        self.ece       = expected_calibration_error
        self.bootstrap = bootstrap_ci

        rng           = np.random.default_rng(42)
        n             = 300
        self.y_pred   = rng.beta(2, 10, n)
        self.y_true   = rng.binomial(1, self.y_pred * 0.95).astype(float)

    def test_auc_above_chance(self):
        assert self.auc(self.y_true, self.y_pred) > 0.5

    def test_auc_perfect(self):
        y_true = np.array([0.0] * 50 + [1.0] * 50)
        y_pred = np.array([0.1] * 50 + [0.9] * 50)
        assert abs(self.auc(y_true, y_pred) - 1.0) < 0.01

    def test_auc_random_near_half(self):
        rng    = np.random.default_rng(99)
        y_true = rng.binomial(1, 0.3, 500).astype(float)
        y_pred = rng.uniform(0, 1, 500)
        assert 0.40 < self.auc(y_true, y_pred) < 0.60

    def test_brier_perfect_zero(self):
        y = np.array([0.0, 1.0, 0.0, 1.0])
        assert self.brier(y, y) == 0.0

    def test_brier_worst_one(self):
        assert abs(self.brier(np.array([0.0, 1.0]), np.array([1.0, 0.0])) - 1.0) < 0.01

    def test_hl_pvalue_range(self):
        _, p, _ = self.hl(self.y_true, self.y_pred)
        assert 0.0 <= p <= 1.0

    def test_hl_adequate_calibration(self):
        _, p, _ = self.hl(self.y_true, self.y_pred)
        assert p > 0.05

    def test_ece_bounded(self):
        assert 0.0 <= self.ece(self.y_true, self.y_pred) <= 1.0

    def test_bootstrap_ci_ordered(self):
        lo, hi = self.bootstrap(self.y_true, self.y_pred, self.auc, n_bootstrap=200)
        assert lo <= hi

    def test_bootstrap_ci_contains_estimate(self):
        auc    = self.auc(self.y_true, self.y_pred)
        lo, hi = self.bootstrap(self.y_true, self.y_pred, self.auc, n_bootstrap=300)
        assert lo <= auc <= hi

    def test_full_validation_no_nan(self):
        vr = self.validate(self.y_true, self.y_pred, "LKB_PUB", n_bootstrap=200)
        assert not math.isnan(vr.auc)
        assert not math.isnan(vr.brier_score)
        assert not math.isnan(vr.hl_p_value)
        assert not math.isnan(vr.ece)
        assert vr.n_patients == 300

    def test_dict_has_brier_ci(self):
        """CURSOR_FINAL_FIXES FIX-6: Brier_95CI added to dict output."""
        from validation.validation_metrics import validation_result_to_dict
        vr = self.validate(self.y_true, self.y_pred, "LKB_DICT", n_bootstrap=100)
        d  = validation_result_to_dict(vr)
        assert "Brier_95CI" in d

    def test_dict_has_cal_adequate(self):
        """CURSOR_FINAL_FIXES FIX-6: cal_adequate flag in dict."""
        from validation.validation_metrics import validation_result_to_dict
        vr = self.validate(self.y_true, self.y_pred, "LKB_CAL", n_bootstrap=0)
        d  = validation_result_to_dict(vr)
        assert "cal_adequate" in d
        assert d["cal_adequate"] in (True, False, None)


# ---------------------------------------------------------------------------
# PART 8 — MLE NTCP calibration
# ---------------------------------------------------------------------------

class TestNTCPCalibration:

    def setup_method(self):
        from validation.ntcp_calibration import (
            fit_lkb_parameters, _lkb_probit_ntcp, _compute_geud,
            FittedNTCPParams, fitted_params_to_yaml, _neg_log_likelihood_lkb,
        )
        self.fit    = fit_lkb_parameters
        self.ntcp   = _lkb_probit_ntcp
        self.geud   = _compute_geud
        self.Params = FittedNTCPParams
        self.yaml   = fitted_params_to_yaml
        self.nll    = _neg_log_likelihood_lkb

        rng  = np.random.default_rng(42)
        n    = 200
        dmeans          = rng.uniform(5.0, 50.0, n)
        true_ntcp       = np.array([self.ntcp(d, 26.0, 0.40) for d in dmeans])
        self.dvh_list   = [{"doses": np.array([d]), "vols": np.array([1.0])}
                           for d in dmeans]
        self.outcomes   = rng.binomial(1, true_ntcp).astype(float)

    def test_geud_single_bin_equals_dose(self):
        assert abs(self.geud(np.array([30.0]), np.array([1.0]), n=1.0) - 30.0) < 0.01

    def test_lkb_probit_midpoint(self):
        assert abs(self.ntcp(26.0, 26.0, 0.40) - 0.5) < 0.01

    def test_nll_exposed(self):
        """_neg_log_likelihood_lkb exposed for testability (CURSOR_FIXES §25)."""
        nll = self.nll(26.0, 0.40, 1.0, self.dvh_list[:10], self.outcomes[:10])
        assert math.isfinite(nll) and nll > 0.0

    def test_mle_converges(self):
        r = self.fit(self.dvh_list, self.outcomes, "Parotid_L", "HN",
                     init_td50=30.0, init_m=0.30, n_bootstrap=0, fix_n=True)
        assert r.converged

    def test_mle_td50_plausible(self):
        r = self.fit(self.dvh_list, self.outcomes, "Parotid_L", "HN",
                     init_td50=30.0, init_m=0.30, n_bootstrap=0, fix_n=True)
        assert 5.0 < r.TD50_gy < 70.0

    def test_mle_m_positive(self):
        r = self.fit(self.dvh_list, self.outcomes, "Parotid_L", "HN",
                     init_td50=30.0, init_m=0.30, n_bootstrap=0, fix_n=True)
        assert r.m > 0.0

    def test_bootstrap_ci_finite_with_diverse_events(self):
        """Bootstrap CI non-NaN when ≥5 events and ≥5 non-events."""
        r = self.fit(self.dvh_list, self.outcomes, "Parotid_L", "HN",
                     init_td50=30.0, init_m=0.30, n_bootstrap=100, fix_n=True)
        n_ev  = r.n_events
        n_nev = r.n_patients - n_ev
        if n_ev >= 5 and n_nev >= 5:
            assert not math.isnan(r.TD50_ci[0]), \
                f"TD50 CI NaN with n_events={n_ev}, n_non={n_nev}"
            assert r.TD50_ci[0] < r.TD50_ci[1]

    def test_yaml_output_parseable(self):
        import yaml
        param = self.Params(
            organ="Parotid_L", site="HN",
            TD50_gy=26.0, m=0.40, n=1.0,
            TD50_ci=(22.0, 30.0), m_ci=(0.35, 0.45),
            n_patients=200, n_events=52, converged=True,
        )
        parsed = yaml.safe_load(self.yaml([param], "HN"))
        assert "HN" in parsed
        assert "Parotid_L" in parsed["HN"]["organs"]


# ---------------------------------------------------------------------------
# PART 9 — DVH shape features
# ---------------------------------------------------------------------------

class TestDVHShapeFeatures:

    def setup_method(self):
        from dicom_io.dvh_shape_features import compute_dvh_shape_features
        self.compute = compute_dvh_shape_features

    def test_required_keys(self):
        feat = self.compute(make_hn_ptv_dvh())
        for k in ("D2_gy", "D50_gy", "D98_gy", "D2_D98_ratio",
                  "dose_skewness", "dose_kurtosis", "V95_rx_frac", "dose_std_gy"):
            assert k in feat

    def test_d2_gt_d50_gt_d98(self):
        dvh  = make_ramp_dvh(10.0, 70.0)
        feat = self.compute(dvh)
        assert feat["D2_gy"] > feat["D50_gy"] > feat["D98_gy"]

    def test_no_nan_nonzero_dvh(self):
        """Non-zero minimum DVH: all features should be finite."""
        dvh  = make_oar_dvh_nonzero(20.0, 50.0)
        feat = self.compute(dvh)
        nans = [k for k, v in feat.items() if isinstance(v, float) and math.isnan(v)]
        assert len(nans) == 0, f"Unexpected NaN in non-zero DVH: {nans}"

    def test_empty_dvh_all_nan(self):
        feat = self.compute(pd.DataFrame())
        assert all(math.isnan(v) for v in feat.values())

    def test_uniform_near_zero_std(self):
        feat = self.compute(make_uniform_dvh(60.0, n_bins=200))
        assert feat["dose_std_gy"] < 0.5

    def test_no_runtime_warning_uniform(self):
        """CURSOR_FIXES §17: uniform DVH must not raise RuntimeWarning."""
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            try:
                feat = self.compute(make_uniform_dvh(60.0))
                assert math.isfinite(feat["dose_skewness"])
                assert math.isfinite(feat["dose_kurtosis"])
            except RuntimeWarning as e:
                pytest.fail(f"RuntimeWarning raised — scipy dependency not removed: {e}")

    def test_v95_high_for_uniform(self):
        feat = self.compute(make_uniform_dvh(60.0))
        assert feat["V95_rx_frac"] > 0.9


class TestDosiomics:

    def setup_method(self):
        try:
            from rbgyanx_advanced.dose3d.dosiomics import extract_dosiomics_features
            self.extract = extract_dosiomics_features
            self._ok     = True
        except ImportError:
            self._ok = False

    def _req(self):
        if not self._ok:
            pytest.skip("engine_advanced not available")

    def test_feature_count(self):
        self._req()
        feat = self.extract(np.random.default_rng(0).uniform(10, 60, 2000), "Parotid")
        assert len(feat) >= 15

    def test_no_nan_valid_input(self):
        self._req()
        feat = self.extract(np.random.default_rng(1).uniform(5, 50, 3000), "Lung")
        nans = [k for k, v in feat.items() if isinstance(v, float) and math.isnan(v)]
        assert len(nans) == 0

    def test_nan_on_empty(self):
        self._req()
        feat = self.extract(None, "Test")
        assert all(math.isnan(v) for v in feat.values())


# ---------------------------------------------------------------------------
# PART 10 — Clinical covariates
# ---------------------------------------------------------------------------

class TestClinicalCovariates:

    def test_runconfig_has_field(self):
        from rbgyanx_engine.run_config import RunConfig
        assert hasattr(RunConfig(), "clinical_features_csv")

    def test_merge_adds_columns(self):
        clin   = pd.DataFrame({"AnonPatientID": ["P1", "P2"],
                                "age_years": [65.0, 52.0]})
        feat   = pd.DataFrame({"AnonPatientID": ["P1", "P2"],
                                "TCP_Poisson": [0.75, 0.68]})
        merged = feat.merge(clin, on="AnonPatientID", how="left")
        assert "age_years" in merged.columns
        assert merged.loc[merged.AnonPatientID == "P1", "age_years"].iloc[0] == 65.0

    def test_missing_patient_retained(self):
        """Left merge keeps all dosimetric rows; NaN for missing covariate."""
        clin   = pd.DataFrame({"AnonPatientID": ["P1"], "age_years": [65.0]})
        feat   = pd.DataFrame({"AnonPatientID": ["P1", "P2"],
                                "TCP_Poisson": [0.75, 0.68]})
        merged = feat.merge(clin, on="AnonPatientID", how="left")
        assert len(merged) == 2
        assert math.isnan(merged.loc[merged.AnonPatientID == "P2", "age_years"].iloc[0])


# ---------------------------------------------------------------------------
# PART 11 — Model registry
# ---------------------------------------------------------------------------

class TestModelRegistry:

    def test_register_in_registry(self):
        from radiobiology.model_registry import register_tcp_model, _TCP_MODEL_REGISTRY

        class M:
            def compute_tcp_dvh(self, *a, **k):
                return {"tcp": 0.55, "model": "M"}

        register_tcp_model("REG_TEST", M())
        assert "REG_TEST" in _TCP_MODEL_REGISTRY

    def test_registered_model_in_ensemble(self):
        from radiobiology.model_registry import register_tcp_model
        from radiobiology.tcp_calculator import TCPCalculator
        from config.site_params import load_site_params

        class Fixed:
            def compute_tcp_dvh(self, *a, **k):
                return {"tcp": 0.444, "model": "Fixed444"}

        register_tcp_model("FIXED444_PUB", Fixed())
        r = TCPCalculator().compute_all(
            make_hn_ptv_dvh(),
            {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_per_fraction_gy": 2.0},
            load_site_params("HN"),
        )
        assert r.get("TCP_FIXED444_PUB") == pytest.approx(0.444)

    def test_minimal_protocol_compliant_model(self):
        """Any object with compute_tcp_dvh returning {'tcp': float} is valid."""
        from radiobiology.model_registry import register_tcp_model
        from radiobiology.tcp_calculator import TCPCalculator
        from config.site_params import load_site_params

        class Minimal:
            def compute_tcp_dvh(self, dvh_df, n_fx, sp, target_type="GTV"):
                # Fixed value: tests protocol compliance, not dvh_df parsing
                return {"tcp": 0.35, "model": "Min"}

        register_tcp_model("MINIMAL_PUB2", Minimal())
        r = TCPCalculator().compute_all(
            make_ramp_dvh(20, 70),
            {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_per_fraction_gy": 2.0},
            load_site_params("HN"),
        )
        assert "TCP_MINIMAL_PUB2" in r, f"keys: {list(r.keys())}"
        tcp_val = r.get("TCP_MINIMAL_PUB2", math.nan)
        assert not math.isnan(tcp_val), f"TCP_MINIMAL_PUB2 is NaN"
        assert 0.0 <= tcp_val <= 1.0


# ---------------------------------------------------------------------------
# PART 12 — Pelvic and liver sites
# ---------------------------------------------------------------------------

class TestPelvisLiverSites:

    def test_prostate_alpha_beta(self):
        from config.site_params import load_site_params
        assert abs(load_site_params("PROSTATE").alpha_beta_gy - 1.5) < 0.1

    def test_prostate_ntcp_organs(self):
        from config.site_ntcp_params import load_site_ntcp_params
        organs = set(load_site_ntcp_params("PROSTATE").organs.keys())
        assert "Rectum" in organs
        assert "Bladder" in organs

    def test_liver_tcp_loads(self):
        from config.site_params import load_site_params
        assert load_site_params("LIVER").alpha_beta_gy > 0.0

    def test_prostate_utcp_map(self):
        from radiobiology.utcp import UTCP_OAR_MAP
        assert "PROSTATE" in UTCP_OAR_MAP
        oars = {e["oar"] for e in UTCP_OAR_MAP["PROSTATE"]}
        assert "Rectum" in oars and "Bladder" in oars

    def test_lung_conv_utcp_map(self):
        from radiobiology.utcp import UTCP_OAR_MAP
        assert "LUNG_CONV" in UTCP_OAR_MAP

    def test_quantec_rectum_and_bladder(self):
        from validation.quantec_checker import QUANTEC_CONSTRAINTS
        assert "Rectum" in QUANTEC_CONSTRAINTS
        assert "Bladder" in QUANTEC_CONSTRAINTS


# ---------------------------------------------------------------------------
# PART 13 — Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_single_bin_dvh_no_crash(self):
        from radiobiology.tcp_calculator import TCPCalculator
        from config.site_params import load_site_params
        r = TCPCalculator().compute_all(
            pd.DataFrame({"dose_gy": [70.0], "volume_frac": [1.0]}),
            {"prescription_dose_gy": 70.0, "n_fractions": 35, "dose_per_fraction_gy": 2.0},
            load_site_params("HN"),
        )
        assert isinstance(r, dict) and "TCP_mean" in r

    def test_very_high_dose_tcp_high(self):
        from radiobiology.poisson_tcp import PoissonTCPCalculator
        from config.site_params import load_site_params
        r = PoissonTCPCalculator().compute_tcp_dvh(
            make_uniform_dvh(200.0, n_bins=10), 100, load_site_params("HN"))
        if not math.isnan(r["tcp"]):
            assert r["tcp"] > 0.85

    def test_ntcp_zero_dose_near_zero(self):
        from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
        n = calculate_ntcp_lkb_loglogit(0.0, 26.0, 3.0)
        assert n < 0.01 or math.isnan(n)

    def test_runconfig_enable_ml_default_false(self):
        from rbgyanx_engine.run_config import RunConfig
        assert RunConfig().enable_ml is False

    def test_site_registry_unknown_key_graceful(self):
        """CURSOR_FIXES §7: unknown site key → None with warning, no exception."""
        from rbgyanx.logic.engine_bridge import map_site_override
        assert map_site_override("UnknownSite_XYZ") is None

    def test_quantec_empty_dvh_no_crash(self):
        from validation.quantec_checker import check_quantec_constraints
        assert check_quantec_constraints(pd.DataFrame(), "SpinalCord") == []

    def test_utcp_zero_oars_no_crash(self):
        from radiobiology.utcp import compute_utcp
        r = compute_utcp({"AnonPatientID": "X", "TCP_Poisson": 0.7}, [], "HN")
        assert not math.isnan(r.TCP_used)


# ---------------------------------------------------------------------------
# PART 14 — Reproducibility
# ---------------------------------------------------------------------------

class TestReproducibility:

    def test_tcp_poisson_deterministic(self):
        from radiobiology.poisson_tcp import PoissonTCPCalculator
        from config.site_params import load_site_params
        calc = PoissonTCPCalculator()
        dvh  = make_hn_ptv_dvh()
        p    = load_site_params("HN")
        assert calc.compute_tcp_dvh(dvh, 35, p)["tcp"] == \
               calc.compute_tcp_dvh(dvh, 35, p)["tcp"]

    def test_ntcp_lkb_deterministic(self):
        from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
        v = calculate_ntcp_lkb_loglogit(22.0, 26.0, 3.0)
        assert v == calculate_ntcp_lkb_loglogit(22.0, 26.0, 3.0)

    def test_auc_deterministic(self):
        from validation.validation_metrics import compute_auc
        rng    = np.random.default_rng(7)
        y_true = rng.binomial(1, 0.3, 100).astype(float)
        y_pred = rng.uniform(0.05, 0.8, 100)
        assert compute_auc(y_true, y_pred) == compute_auc(y_true, y_pred)

    def test_bootstrap_seed_deterministic(self):
        from validation.validation_metrics import bootstrap_ci, compute_auc
        rng    = np.random.default_rng(42)
        y_true = rng.binomial(1, 0.25, 150).astype(float)
        y_pred = rng.uniform(0.05, 0.7, 150)
        lo1, hi1 = bootstrap_ci(y_true, y_pred, compute_auc, n_bootstrap=100, seed=42)
        lo2, hi2 = bootstrap_ci(y_true, y_pred, compute_auc, n_bootstrap=100, seed=42)
        assert lo1 == lo2 and hi1 == hi2

    def test_site_detection_deterministic(self):
        from dicom_io.site_detector import detect_site
        plan    = {"plan_label": "PROSTATE 78GY", "prescription_dose_gy": 78.0,
                   "n_fractions": 39, "dose_per_fraction_gy": 2.0}
        structs = [{"canonical": "PTV"}, {"canonical": "Rectum"}]
        assert detect_site(plan, structs)["site"] == detect_site(plan, structs)["site"]


# ---------------------------------------------------------------------------
# PART 15 — End-to-end engine integration
# ---------------------------------------------------------------------------

class TestEngineIntegration:

    def test_tcp_run_synthetic(self, tmp_path):
        from rbgyanx_engine.run_config import RunConfig
        from rbgyanx_engine.engine   import run_analysis
        (tmp_path / "hn_ptv.txt").write_text(
            "Dose(Gy)\tVolume(frac)\n"
            + "\n".join(f"{d:.1f}\t{max(0,1-d/75):.4f}" for d in range(0, 76, 2))
        )
        cfg = RunConfig(endpoint="tcp", input_kind="dvh_txt",
                        input_dir=tmp_path, output_dir=tmp_path / "out",
                        site="HN", dvh_glob="*.txt", dose_per_fraction=2.0,
                        no_uncertainty=True, cohort=False, enable_ml=False)
        result = run_analysis(cfg)
        assert result.exit_code == 0
        assert len(result.tcp_results) >= 1

    def test_provenance_json_created(self, tmp_path):
        from rbgyanx_engine.run_config import RunConfig
        from rbgyanx_engine.engine   import run_analysis
        (tmp_path / "ptv.txt").write_text(
            "Dose(Gy)\tVolume(frac)\n"
            + "\n".join(f"{d:.1f}\t{max(0,1-d/75):.4f}" for d in range(0, 76, 2))
        )
        cfg = RunConfig(endpoint="tcp", input_kind="dvh_txt",
                        input_dir=tmp_path, output_dir=tmp_path / "prov",
                        site="HN", no_uncertainty=True, cohort=False, enable_ml=False)
        run_analysis(cfg)
        assert (tmp_path / "prov" / "provenance.json").exists()
        assert (tmp_path / "prov" / "qa_report.json").exists()

    def test_provenance_fields(self, tmp_path):
        import json
        from rbgyanx_engine.run_config import RunConfig
        from rbgyanx_engine.engine   import run_analysis
        (tmp_path / "ptv2.txt").write_text(
            "Dose(Gy)\tVolume(frac)\n"
            + "\n".join(f"{d:.1f}\t{max(0,1-d/75):.4f}" for d in range(0, 76, 2))
        )
        cfg = RunConfig(endpoint="tcp", input_kind="dvh_txt",
                        input_dir=tmp_path, output_dir=tmp_path / "prov2",
                        site="HN", no_uncertainty=True, cohort=False, enable_ml=False)
        run_analysis(cfg)
        prov = json.loads((tmp_path / "prov2" / "provenance.json").read_text())
        for field in ("engine", "timestamp_utc", "endpoint", "input_kind", "exit_code"):
            assert field in prov

    def test_required_tcp_columns(self, tmp_path):
        from rbgyanx_engine.run_config import RunConfig
        from rbgyanx_engine.engine   import run_analysis
        (tmp_path / "col.txt").write_text(
            "Dose(Gy)\tVolume(frac)\n"
            + "\n".join(f"{d:.1f}\t{max(0,1-d/75):.4f}" for d in range(0, 76, 2))
        )
        cfg = RunConfig(endpoint="tcp", input_kind="dvh_txt",
                        input_dir=tmp_path, output_dir=tmp_path / "col_out",
                        site="HN", no_uncertainty=True, cohort=False, enable_ml=False)
        result = run_analysis(cfg)
        if result.tcp_results:
            row = result.tcp_results[0]
            for col in ("TCP_Poisson", "TCP_ZM", "TCP_gEUD", "TCP_Logistic",
                        "TCP_mean", "TCP_range", "EQD2_gy", "BED_gy"):
                assert col in row, f"Missing: {col}"
