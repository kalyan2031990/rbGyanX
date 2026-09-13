"""
Classical-numerics fingerprint for do-no-harm regression (Phase 0.2).

Runs the engine's validated classical calculations (physical DVH metrics, gEUD, EQD2, NTCP LKB
log-logistic / probit / relative-seriality) on the shipped SYNTHETIC example DVHs and serialises every
number to JSON at full precision. Later phases re-run this and diff against the Phase-0 reference; any
non-zero diff is a stop-and-report (constraint C1).

Deterministic and self-contained — no seeds, no ML, synthetic input only. Not a clinical result.

Usage:
  python scripts/verification/baseline_fingerprint.py            # write baseline_numerics.json
  python scripts/verification/baseline_fingerprint.py --check    # recompute and diff vs the reference
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "engine"))

from dicom_io.txt_dvh_reader import parse_dvh_text_file  # noqa: E402
from radiobiology import compute_geud, dvh_object_to_dataframe  # noqa: E402
from radiobiology.bdvh import compute_eqd2_dvh  # noqa: E402
from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit  # noqa: E402
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit  # noqa: E402
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson  # noqa: E402

DVH_DIR = ROOT / "examples" / "data" / "dvh_txt"
REF = ROOT / "baseline_numerics.json"

# Fixed literature parameters — a regression fingerprint of the FUNCTIONS, not a clinical assignment.
GEUD_A = (1.0, 3.0, 10.0, -10.0)
EQD2_AB = (3.0, 10.0)
NTCP_LL = {"TD50": 28.4, "gamma50": 0.6}       # parotid log-logistic
NTCP_PROBIT = {"TD50_gy": 39.9, "m": 0.40}     # parotid probit (mean-dose form)
NTCP_RS = {"D50": 28.4, "gamma": 1.0, "s": 0.25}  # relative-seriality


def _phys(df):
    """Definitional physical metrics from a differential DVH (dose_gy, volume_frac summing to 1)."""
    d = np.asarray(df["dose_gy"], float)
    v = np.asarray(df["volume_frac"], float)
    order = np.argsort(d)
    d, v = d[order], v[order]
    dmean = float((d * v).sum() / v.sum())
    dmax = float(d[v > 0].max())
    # cumulative volume receiving >= dose (DVH); D_x = min dose covering x% of volume
    cum = np.cumsum(v[::-1])[::-1] / v.sum()  # fraction with dose >= d[i]

    def dose_at(frac):
        idx = np.where(cum >= frac)[0]
        return float(d[idx[-1]]) if len(idx) else float("nan")

    return {"Dmean_gy": dmean, "Dmax_gy": dmax, "D2_gy": dose_at(0.02), "D98_gy": dose_at(0.98)}


def fingerprint() -> dict:
    out: dict = {}
    for f in sorted(DVH_DIR.glob("*.txt")):
        parsed = parse_dvh_text_file(f)
        df = dvh_object_to_dataframe(parsed.dvh_object)
        meta = getattr(parsed, "plan_metadata", {}) or {}
        nfx = int(meta.get("n_fractions") or 35)
        rec: dict = {"n_fractions": nfx, **_phys(df)}
        for a in GEUD_A:
            rec[f"gEUD_a{a:g}"] = float(compute_geud(df, a))
        for ab in EQD2_AB:
            eqd2_df = compute_eqd2_dvh(df, nfx, ab)
            ed = np.asarray(eqd2_df["dose_gy"], float)
            vv = np.asarray(eqd2_df["volume_frac"], float)
            rec[f"EQD2mean_ab{ab:g}"] = float((ed * vv).sum() / vv.sum())
        geud1 = float(compute_geud(df, 1.0))
        rec["NTCP_LL"] = float(calculate_ntcp_lkb_loglogit(geud1, NTCP_LL["TD50"], NTCP_LL["gamma50"]))
        rec["NTCP_probit"] = float(calculate_ntcp_lkb_probit(geud1, NTCP_PROBIT["TD50_gy"], NTCP_PROBIT["m"]))
        rec["NTCP_RS"] = float(calculate_ntcp_rs_poisson(df, NTCP_RS["D50"], NTCP_RS["gamma"], NTCP_RS["s"]))
        out[f.name] = rec
    return out


def _diff(ref: dict, cur: dict) -> list[str]:
    diffs = []
    for key in sorted(set(ref) | set(cur)):
        if key not in ref:
            diffs.append(f"NEW structure {key}")
            continue
        if key not in cur:
            diffs.append(f"MISSING structure {key}")
            continue
        for m in sorted(set(ref[key]) | set(cur[key])):
            a, b = ref[key].get(m), cur[key].get(m)
            if a is None or b is None:
                diffs.append(f"{key}.{m}: {a} -> {b}")
            elif isinstance(a, float) and math.isnan(a) and isinstance(b, float) and math.isnan(b):
                continue
            elif a != b:  # exact floating-point equality (C1)
                diffs.append(f"{key}.{m}: {a!r} -> {b!r}  (Δ={b - a:.3e})")
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="recompute and diff vs baseline_numerics.json")
    args = ap.parse_args()
    cur = fingerprint()
    if args.check:
        if not REF.exists():
            print("NO REFERENCE — run without --check first.")
            return 2
        ref = json.loads(REF.read_text(encoding="utf-8"))
        diffs = _diff(ref, cur)
        if diffs:
            print(f"STOP-AND-REPORT: {len(diffs)} numeric diff(s) vs baseline:")
            for d in diffs:
                print("  " + d)
            return 1
        print(f"OK — {sum(len(v) for v in cur.values())} numbers across {len(cur)} structures match baseline exactly.")
        return 0
    REF.write_text(json.dumps(cur, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {REF} — {sum(len(v) for v in cur.values())} numbers across {len(cur)} structures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
