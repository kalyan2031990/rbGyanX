"""
Build the machine-learning / statistics-ready PATIENT-LEVEL feature table (brief §9).

Reads ONLY pseudonymised rbGyanX cohort outputs (advanced run, basic used as fallback) and pivots them
to one row per patient. Attaches outcome labels where a documented, verifiable linkage exists.

Cohort lock (brief §2, as corrected by the owner):
    Parotid  n=54  INTERNAL
    SPARK    n=43  EXTERNAL
    TCIA_HN  n=186 EXTERNAL
    TCIA_Lung — EXCLUDED ENTIRELY (never read, never counted).

Identifier = cohort + pseudonymous patient ID. No real names/MRNs are read or written.
Parotid is reported side-unspecified: the manuscript-facing organ label is `Parotid_unspecified`,
with the engine's internal canonicalisation retained in an audit column.

Usage:
  python build_patient_features.py --final-validation <...>/rbGyanX_Final_Validation --out <dir>
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import pandas as pd

# --- locked cohorts; TCIA_Lung deliberately absent so it cannot enter any denominator -------------
COHORTS = {
    "Parotid": {"dir": "Parotid_Internal_n54", "role": "internal", "n": 54,
                "sub": "InternalValidation/Parotid", "site": "HN"},
    "SPARK": {"dir": "SPARK_External_n43", "role": "external", "n": 43,
              "sub": "ExternalValidation/SPARK", "site": "PROSTATE"},
    "TCIA_HN": {"dir": "TCIA_HN_External_n186", "role": "external", "n": 186,
                "sub": "ExternalValidation/TCIA_HN", "site": "HN"},
}
EXCLUDED_COHORTS = ("TCIA_Lung",)  # hard exclusion, brief §3

# Parotid manuscript-facing organ label (never claim laterality — brief §10)
PAROTID_NEUTRAL = "Parotid_unspecified"


def _read(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _f(v):
    """float or NaN — never silently 0 (engine NaN contract)."""
    try:
        x = float(v)
        return x if math.isfinite(x) else math.nan
    except Exception:
        return math.nan


def _cohort_root(final_dir: Path, cohort: str) -> tuple[Path, str]:
    """Prefer the ADVANCED run; fall back to basic. Returns (CohortLevel dir, which run)."""
    meta = COHORTS[cohort]
    adv = final_dir / meta["dir"] / "advanced" / meta["sub"] / "CohortLevel"
    bas = final_dir / meta["dir"] / "basic" / "CohortLevel"
    if (adv / "ntcp_results.csv").is_file():
        return adv, "advanced"
    return bas, "basic"


def build_cohort(final_dir: Path, cohort: str) -> pd.DataFrame:
    meta = COHORTS[cohort]
    cl, which = _cohort_root(final_dir, cohort)
    ntcp, tcp = _read(cl / "ntcp_results.csv"), _read(cl / "tcp_results.csv")
    phys, plan = _read(cl / "physical_metrics.csv"), _read(cl / "plan_quality.csv")
    site = _read(cl / "site_detection.csv")
    dvh = _read(cl / "dvh_summary.csv")
    mlf = _read(cl / "ML_features.csv")

    patients = sorted({r["pseudonym"] for r in ntcp + tcp + phys} - {""})
    site_by = {r["pseudonym"]: r for r in site}
    rows: list[dict] = []

    for p in patients:
        rec: dict = {
            "uid": f"{cohort}::{p}",
            "cohort": cohort,
            "pseudonym": p,
            "validation_role": meta["role"],
            "run_mode": which,
            "site": (site_by.get(p, {}) or {}).get("site") or meta["site"],
            "site_confidence": (site_by.get(p, {}) or {}).get("confidence", ""),
        }

        # ---- physical DVH metrics, per structure (wide) --------------------------------------
        for r in phys:
            if r["pseudonym"] != p:
                continue
            s = r["structure"]
            if cohort == "Parotid":
                s = PAROTID_NEUTRAL
            for src, dst in (("volume_cc", "volume_cc"), ("Dmean_gy", "Dmean_gy"),
                             ("Dmax_gy", "Dmax_gy"), ("D2_gy", "D2_gy"), ("D98_gy", "D98_gy")):
                rec[f"{s}__{dst}"] = _f(r.get(src))

        # ---- DVH summary (mode / volume) ------------------------------------------------------
        for r in dvh:
            if r["pseudonym"] == p and r.get("dvh_mode"):
                rec["dvh_mode"] = r["dvh_mode"]
                break

        # ---- plan quality ---------------------------------------------------------------------
        for r in plan:
            if r["pseudonym"] != p:
                continue
            rec[f"{r['target']}__HI"] = _f(r.get("HI"))
            rec[f"{r['target']}__CI"] = _f(r.get("CI"))
            rec[f"{r['target']}__GI_pct"] = _f(r.get("GI_pct"))

        # ---- TCP (per target × model) ---------------------------------------------------------
        for r in tcp:
            if r["pseudonym"] != p:
                continue
            rec[f"TCP__{r['structure']}__{r['model']}"] = _f(r.get("tcp"))

        # ---- NTCP (+ Monte-Carlo uncertainty) per organ × model -------------------------------
        defn_flags: set[str] = set()
        canon_seen: set[str] = set()
        for r in ntcp:
            if r["pseudonym"] != p:
                continue
            organ_raw = r["structure"]
            canon_seen.add(organ_raw)
            organ = PAROTID_NEUTRAL if cohort == "Parotid" else organ_raw
            m = r["model"]
            rec[f"NTCP__{organ}__{m}"] = _f(r.get("ntcp"))
            for u in ("mean", "sd", "p5", "p95"):
                v = r.get(f"uNTCP_{u}")
                if v not in (None, ""):
                    rec[f"uNTCP__{organ}__{m}__{u}"] = _f(v)
            if r.get("reason_codes"):
                defn_flags.add(r["reason_codes"])
            rec["ntcp_params_key"] = r.get("site_params_key", "")

        # ---- dosiomics (ADVANCED, long-form in ML_features.csv) --------------------------------
        for r in mlf:
            if r["pseudonym"] == p and str(r.get("feature", "")).startswith("dosio_"):
                name = r["feature"]
                if cohort == "Parotid":
                    name = name.replace("Parotid_R", PAROTID_NEUTRAL).replace("Parotid_L", PAROTID_NEUTRAL)
                rec[name] = _f(r.get("value"))

        rec["ntcp_definition_flags"] = ";".join(sorted(f for f in defn_flags if f))
        # AUDIT ONLY — records the engine's internal canonicalisation, never used as anatomy
        rec["audit_engine_canonical_organs"] = ";".join(sorted(canon_seen))
        rows.append(rec)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("pseudonym").reset_index(drop=True)
    return df


# ------------------------------------------------------------------ outcome linkage

def attach_outcomes(df: pd.DataFrame, cohort: str, validation_study: Path, map_dir: Path) -> pd.DataFrame:
    """Attach outcome labels ONLY where a documented linkage exists. Never invent labels."""
    df = df.copy()
    df["outcome_available"] = 0
    if df.empty:
        return df
    mp = map_dir / f"{cohort}_pseudonym_map.csv"
    if not mp.is_file():
        return df
    raw_by_pse = {r["pseudonym"]: r["raw_patient_key"] for r in _read(mp)}

    if cohort == "Parotid":
        pm = _read(validation_study / "derived" / "parotid_pseudonym_map.csv")
        full = _read(validation_study / "derived" / "parotid_cohort_full.csv")
        code_by_study = {r["pseudonym"]: str(r["dvh_file"]).replace("_Parotid.txt", "") for r in pm}
        out_by_code = {}
        for r in full:
            code = code_by_study.get(r["pseudonym"])
            if code:
                out_by_code[code] = r
        vals, avail, extra = [], [], defaultdict(list)
        for p in df["pseudonym"]:
            o = out_by_code.get(raw_by_pse.get(p, ""), {})
            y = o.get("xerostomia_grade2plus", "")
            vals.append(_f(y))
            avail.append(1 if y not in ("", None) else 0)
            for k in ("age", "sex_M", "tobacco_exposure", "followup_months", "Parotid_volume_cc"):
                extra[k].append(_f(o.get(k)) if k in o else math.nan)
        df["outcome_xerostomia_g2plus"] = vals
        df["outcome_available"] = avail
        for k, v in extra.items():
            df[f"clin_{k}"] = v

    elif cohort == "TCIA_HN":
        hn = {r["patient_id"]: r for r in _read(validation_study / "derived" / "hn_cohort_features.csv")}
        lr, dth, avail, centre = [], [], [], []
        for p in df["pseudonym"]:
            o = hn.get(raw_by_pse.get(p, ""), {})
            lr.append(_f(o.get("locoregional")) if o else math.nan)
            dth.append(_f(o.get("death")) if o else math.nan)
            centre.append(o.get("centre", ""))
            avail.append(1 if o else 0)
        df["outcome_locoregional"] = lr
        df["outcome_death"] = dth
        df["clin_centre"] = centre
        df["outcome_available"] = avail

    # SPARK: per-patient outcome labels are NOT linkable to the DVH exports (no ID crosswalk between
    # the adverse-event/EPIC-26 tables and the plan-sum files). Left unlabelled by design — brief §15
    # forbids inventing supervised metrics.
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--final-validation", required=True, type=Path)
    ap.add_argument("--validation-study", required=True, type=Path)
    ap.add_argument("--map-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    all_df, summary = [], []
    for cohort in COHORTS:
        df = build_cohort(args.final_validation, cohort)
        df = attach_outcomes(df, cohort, args.validation_study, args.map_dir)
        expected = COHORTS[cohort]["n"]
        got = len(df)
        summary.append({"cohort": cohort, "validation_role": COHORTS[cohort]["role"],
                        "expected_n": expected, "actual_n": got, "match": got == expected,
                        "run_mode": df["run_mode"].iloc[0] if got else "",
                        "outcome_labelled_n": int(df["outcome_available"].sum()) if got else 0,
                        "n_features": df.shape[1]})
        out = args.out / f"patient_features_{cohort}.csv"
        df.to_csv(out, index=False)
        print(f"{cohort:9s} n={got:4d} (expected {expected}) features={df.shape[1]:4d} "
              f"labelled={int(df['outcome_available'].sum()) if got else 0}  -> {out.name}")
        all_df.append(df)

    master = pd.concat(all_df, ignore_index=True, sort=False)
    master.to_csv(args.out / "patient_features_ALL.csv", index=False)
    pd.DataFrame(summary).to_csv(args.out / "feature_table_summary.csv", index=False)

    assert not any(c in set(master["cohort"]) for c in EXCLUDED_COHORTS), "TCIA_Lung leaked!"
    assert master["uid"].is_unique, "duplicate patient uid!"
    print(f"\nMASTER: {len(master)} patients x {master.shape[1]} columns -> patient_features_ALL.csv")
    print(f"  cohort counts: {master['cohort'].value_counts().to_dict()}")
    print(f"  TCIA_Lung present: {'TCIA_Lung' in set(master['cohort'])} (must be False)")
    print(f"  duplicate uids: {int(master['uid'].duplicated().sum())} (must be 0)")
    (args.out / "build_manifest.json").write_text(json.dumps(
        {"cohorts": summary, "total_patients": len(master), "excluded": list(EXCLUDED_COHORTS),
         "parotid_organ_label": PAROTID_NEUTRAL}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
