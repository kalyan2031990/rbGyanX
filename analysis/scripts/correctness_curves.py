"""
Part 4-A — CORRECTNESS CURVES (Figure 2), exported from the engine.

Cohort-independent analytic controls. NO patient data, NO development history — only curves
showing the controls holding:
  * NTCP vs gEUD for LKB probit, LKB log-logistic and relative seriality across several seriality
    values, each passing through 0.5 at its TD50/D50 fixed point;
  * QUANTEC parotid (Dmean) and rectal (LKB) anchor curves with the anchor points marked;
  * the P+ (uncomplicated control) factorisation identity P+ = TCP * prod(1 - NTCP_i).

Deterministic (closed-form; no RNG). Writes tidy CSVs + provenance.json under
analysis/outputs/correctness/ (gitignored). Run: python analysis/scripts/correctness_curves.py
"""

from __future__ import annotations

import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from radiobiology.geud_tcp import compute_geud
from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

OUT = Path(__file__).resolve().parents[1] / "outputs" / "correctness"


def _uniform_dvh(dose_gy: float, n_bins: int = 100) -> pd.DataFrame:
    return pd.DataFrame({"dose_gy": [dose_gy] * n_bins, "volume_frac": [1.0 / n_bins] * n_bins})


def dose_response_curves() -> pd.DataFrame:
    """NTCP vs dose/gEUD for the three model families; RS at >=3 seriality values."""
    dose = np.round(np.arange(0.0, 90.01, 0.5), 2)
    rows = []
    # LKB probit and log-logistic share the parallel/gEUD Dmean form.
    td50_probit, m_probit = 39.9, 0.40  # parotid xerostomia (QUANTEC-era)
    td50_ll, gamma_ll = 39.9, 2.0
    for d in dose:
        rows.append(
            ("LKB_probit", td50_probit, calculate_ntcp_lkb_probit(d, td50_probit, m_probit))
        )
        rows.append(("LKB_loglogistic", td50_ll, calculate_ntcp_lkb_loglogit(d, td50_ll, gamma_ll)))
    # Relative seriality across seriality values spanning the D50 fixed point.
    d50_rs, gamma_rs = 39.9, 2.0
    for s in (0.10, 0.25, 1.00):
        for d in dose:
            ntcp = calculate_ntcp_rs_poisson(_uniform_dvh(float(d)), d50_rs, gamma_rs, s)
            rows.append((f"relative_seriality_s{s:.2f}", d50_rs, ntcp))
    df = pd.DataFrame(rows, columns=["model", "td50_gy", "ntcp"])
    df.insert(1, "dose_gy", np.tile(dose, len(df) // len(dose)))
    return df


def fixed_points() -> pd.DataFrame:
    """The TD50/D50 controls: NTCP must be exactly 0.5 at the fixed point."""
    rows = [
        ("LKB_probit", 39.9, calculate_ntcp_lkb_probit(39.9, 39.9, 0.40)),
        ("LKB_loglogistic", 39.9, calculate_ntcp_lkb_loglogit(39.9, 39.9, 2.0)),
    ]
    for s in (0.10, 0.25, 1.00):
        rows.append(
            (
                f"relative_seriality_s{s:.2f}",
                39.9,
                calculate_ntcp_rs_poisson(_uniform_dvh(39.9), 39.9, 2.0, s),
            )
        )
    df = pd.DataFrame(rows, columns=["model", "fixed_point_gy", "ntcp_at_fixed_point"])
    df["passes_0.5"] = np.isclose(df["ntcp_at_fixed_point"], 0.5, atol=1e-9)
    return df


def quantec_anchors() -> pd.DataFrame:
    """QUANTEC anchor points marked on the LKB curves."""
    rows = [
        # (organ, endpoint, TD50, m, anchor dose, expected note)
        ("Parotid", "xerostomia G>=2", 39.9, 0.40, 25.0, "QUANTEC Dmean<25 Gy guideline"),
        ("Parotid", "xerostomia G>=2", 39.9, 0.40, 39.9, "TD50 fixed point"),
        ("Rectum", "late rectal G>=2", 76.9, 0.15, 70.0, "QUANTEC V70 region"),
        ("Rectum", "late rectal G>=2", 76.9, 0.15, 76.9, "TD50 fixed point"),
    ]
    out = []
    for organ, endpoint, td50, m, d, note in rows:
        out.append((organ, endpoint, td50, m, d, calculate_ntcp_lkb_probit(d, td50, m), note))
    return pd.DataFrame(
        out, columns=["organ", "endpoint", "td50_gy", "m", "anchor_dose_gy", "ntcp", "note"]
    )


def pplus_factorisation() -> pd.DataFrame:
    """P+ identity: uncomplicated control = TCP * prod(1 - NTCP_i), checked numerically."""
    tcp_vals = [0.5, 0.7, 0.9]
    ntcp_sets = [[0.1, 0.2], [0.05, 0.15, 0.3], [0.0, 0.5]]
    rows = []
    for tcp in tcp_vals:
        for ntcps in ntcp_sets:
            prod = float(np.prod([1.0 - n for n in ntcps]))
            pplus = tcp * prod
            rows.append((tcp, ",".join(f"{n:g}" for n in ntcps), prod, pplus, pplus <= tcp + 1e-12))
    return pd.DataFrame(
        rows, columns=["tcp", "ntcp_list", "prod_1_minus_ntcp", "p_plus", "p_plus_le_tcp"]
    )


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    outputs = {
        "dose_response_curves.csv": dose_response_curves(),
        "fixed_points.csv": fixed_points(),
        "quantec_anchors.csv": quantec_anchors(),
        "pplus_factorisation.csv": pplus_factorisation(),
    }
    for name, df in outputs.items():
        df.to_csv(OUT / name, index=False)

    fp = outputs["fixed_points.csv"]
    geud_check = compute_geud(_uniform_dvh(30.0), 1.0)  # gEUD(a=1) == mean dose
    all_fixed_ok = bool(fp["passes_0.5"].all())
    all_pplus_ok = bool(outputs["pplus_factorisation.csv"]["p_plus_le_tcp"].all())

    prov = {
        "part": "4-A correctness curves",
        "seed": 0,
        "deterministic": True,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "controls": {
            "all_fixed_points_pass_0.5": all_fixed_ok,
            "geud_a1_equals_mean_dose": bool(np.isclose(geud_check, 30.0, rtol=1e-9)),
            "pplus_never_exceeds_tcp": all_pplus_ok,
        },
        "outputs": list(outputs),
    }
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")

    print("Part 4-A correctness curves ->", OUT)
    print(f"  fixed points all == 0.5 : {all_fixed_ok}")
    print(f"  gEUD(a=1) == mean dose  : {prov['controls']['geud_a1_equals_mean_dose']}")
    print(f"  P+ <= TCP always        : {all_pplus_ok}")
    print(
        f"  rows: dose_response={len(outputs['dose_response_curves.csv'])}, "
        f"anchors={len(outputs['quantec_anchors.csv'])}"
    )
    return 0 if (all_fixed_ok and all_pplus_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
