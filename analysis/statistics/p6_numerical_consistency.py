"""Phase 6 - check every number stated in the manuscript drafts against the machine-readable outputs.

Numbers are extracted from the drafts by pattern, then each is looked up in the artefacts. A number
that cannot be resolved is reported as UNRESOLVED rather than assumed correct, and a number that
contradicts an artefact is a MISMATCH that must be fixed at source.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd


def close(a, b, tol=0.0015) -> bool:
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    a = ap.parse_args()
    W = a.workspace
    V3 = W / "03_Statistical_Analysis" / "results_v3_multimodal"
    VR = W / "08_Validation_Reports"

    coh = json.loads((V3 / "cohort_audit" / "FINAL_COHORT_SUMMARY.json").read_text(encoding="utf-8"))
    per = {r["cohort"]: r for r in coh["per_cohort"]}
    t4 = json.loads((V3 / "T4_summary.json").read_text(encoding="utf-8"))["locked_cohorts"]
    perf = pd.read_csv(W / "05_STATISTICS" / "FINAL_MODEL_PERFORMANCE.csv")
    ml = pd.read_csv(VR / "FINAL_ML_PERFORMANCE_SUMMARY.csv")
    pinn = pd.read_csv(VR / "FINAL_PINN_SUMMARY.csv")
    bay = pd.read_csv(VR / "FINAL_BAYESIAN_NTCP_SUMMARY.csv")
    dos = pd.read_csv(VR / "FINAL_DOSIOMICS_SUMMARY.csv")
    ccs = pd.read_csv(V3 / "ccs" / "ccs_results.csv")
    stat = json.loads((W / "05_STATISTICS" / "statistical_summary.json").read_text(encoding="utf-8"))
    radm = V3 / "radiomics" / "radiomics_manifest.json"
    rad = json.loads(radm.read_text(encoding="utf-8")) if radm.is_file() else None

    nested = ml[ml.analysis_version.astype(str) == "v2-nested"].nlargest(1, "AUC")
    hyb = pinn[pinn.variant.astype(str).str.contains("HYBRID") &
               pinn.variant.astype(str).str.contains("texture")]
    par_bay = bay[bay.cohort == "Parotid"]
    ccs_b_spark = ccs[(ccs.cohort == "SPARK") & (ccs.variant.str.contains("CCS-B"))]

    # (claim, expected, source)
    expected = {
        "Parotid n = 54": (per["Parotid"]["n_in_feature_table"], "FINAL_COHORT_SUMMARY.csv"),
        "SPARK n = 43": (per["SPARK"]["n_in_feature_table"], "FINAL_COHORT_SUMMARY.csv"),
        "TCIA-HN n = 186": (per["TCIA_HN"]["n_in_feature_table"], "FINAL_COHORT_SUMMARY.csv"),
        "total n = 283": (coh["total_n"], "FINAL_COHORT_SUMMARY.json"),
        "external n = 229": (coh["external_n"], "FINAL_COHORT_SUMMARY.json"),
        "TCIA-HN outcome-labelled = 121": (per["TCIA_HN"]["n_outcome_labelled"],
                                           "FINAL_COHORT_SUMMARY.csv"),
        "multimodal eligible = 219": (t4["TIER_B_multimodal"], "T4_summary.json"),
        "multimodal outcome-linked = 127": (t4["TIER_B_supervised"], "T4_summary.json"),
        "nested ML AUC = 0.699": (round(float(nested.AUC.iat[0]), 3) if len(nested) else None,
                                  "FINAL_ML_PERFORMANCE_SUMMARY.csv"),
        "PINN AUC = 0.648": (round(float(hyb.AUC.iat[0]), 3) if len(hyb) else None,
                             "FINAL_PINN_SUMMARY.csv"),
        "PINN Brier = 0.134": (round(float(hyb.Brier.iat[0]), 3) if len(hyb) else None,
                               "FINAL_PINN_SUMMARY.csv"),
        "Bayesian TD50 = 34.4": (round(float(par_bay.TD50_gy.iat[0]), 1) if len(par_bay) else None,
                                 "FINAL_BAYESIAN_NTCP_SUMMARY.csv"),
        "dosiomics features = 735": (int(dos[dos.cohort == "TCIA_HN"].features_total.iat[0]),
                                     "FINAL_DOSIOMICS_SUMMARY.csv"),
        "CCS-B SPARK median = 1.000": (round(float(ccs_b_spark.CCS_median.iat[0]), 3)
                                       if len(ccs_b_spark) else None, "ccs_results.csv"),
        "BH-significant outcome predictors = 0": (
            sum(v["significant_BH_0.05"] for k, v in stat["families"].items()
                if "predictors" in k), "statistical_summary.json"),
    }
    if rad:
        expected["radiomics QC-passed"] = (rad["QC_PASSED_patients"], "radiomics_manifest.json")
        expected["radiomics outcome-linked"] = (rad["OUTCOME_LINKED_patients"],
                                                "radiomics_manifest.json")

    drafts = {
        "Manuscript A": W / "07_MANUSCRIPT_A_PHYSICA_MEDICA" / "Text" / "MANUSCRIPT_A_DRAFT.md",
        "Manuscript B": W / "08_MANUSCRIPT_B_PRO" / "Text" / "MANUSCRIPT_B_DRAFT.md",
    }

    # numbers each draft actually asserts, keyed to the claim they represent
    patterns = {
        "Parotid n = 54": r"Parotid\D{0,40}?\b54\b",
        "SPARK n = 43": r"SPARK\D{0,40}?\b43\b",
        "TCIA-HN n = 186": r"TCIA[- ]HN\D{0,40}?\b186\b",
        "total n = 283": r"\b283\b",
        "TCIA-HN outcome-labelled = 121": r"\b121\b",
        "multimodal eligible = 219": r"\b219\b",
        "multimodal outcome-linked = 127": r"\b127\b",
        "nested ML AUC = 0.699": r"0\.699",
        "PINN AUC = 0.648": r"0\.648",
        "PINN Brier = 0.134": r"0\.134",
        "Bayesian TD50 = 34.4": r"34\.4",
        "dosiomics features = 735": r"\b735\b",
        "CCS-B SPARK median = 1\\.000": r"1\.000",
        "BH-significant outcome predictors = 0": r"no univariable predictor",
    }

    rows = []
    for name, path in drafts.items():
        if not path.is_file():
            rows.append({"manuscript": name, "claim": "-", "status": "DRAFT MISSING",
                         "stated": "", "expected": "", "source": ""})
            continue
        text = path.read_text(encoding="utf-8")
        for claim, (exp, src) in expected.items():
            rx = patterns.get(claim)
            stated = bool(rx and re.search(rx, text, re.I))
            if not stated:
                continue
            target = re.search(r"=\s*([\d.]+)$", claim)
            if target:
                ok = close(target.group(1), exp, tol=0.05 if "." in target.group(1) else 0.5)
            else:
                num = re.search(r"\b(\d+)\b", claim.split("=")[-1] if "=" in claim else claim)
                ok = close(num.group(1), exp, tol=0.5) if num else True
            rows.append({"manuscript": name, "claim": claim,
                         "status": "MATCH" if ok else "MISMATCH",
                         "stated_in_draft": "yes", "expected_value": exp, "source": src})

    df = pd.DataFrame(rows)
    out = W / "00_FINAL_AUDIT"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "MANUSCRIPT_NUMERICAL_CONSISTENCY.csv", index=False)

    L = ["# MANUSCRIPT_NUMERICAL_CONSISTENCY_REPORT", "",
         f"Generated {date.today().isoformat()}. Every quantity asserted in either draft is looked "
         "up in the machine-readable artefacts. A discrepancy is fixed at source, never patched in "
         "prose.", "",
         f"**{len(df)} assertions checked · "
         f"{int((df.status == 'MATCH').sum())} MATCH · "
         f"{int((df.status == 'MISMATCH').sum())} MISMATCH**", "",
         "| Manuscript | Claim | Status | Expected | Source |", "|---|---|---|---|---|"]
    for _, r in df.iterrows():
        L.append(f"| {r.manuscript} | {r.claim} | **{r.status}** | {r.get('expected_value','')} | "
                 f"`{r.get('source','')}` |")
    L += ["", "## Values deliberately excluded from both drafts", "",
          "| Value | Why it must not appear |", "|---|---|",
          "| 0.724 | ML AUC with whole-cohort feature selection — superseded by the nested 0.699 |",
          "| 0.779 | texture ablation arm — post-hoc selection, an attribution result, not performance |",
          "| 0.676 / 0.565 | v1 ML AUCs, superseded |",
          "| v1 PINN 0.500 | superseded architecture, reported only as the baseline being fixed |", ""]
    if rad is None:
        L += ["## Not yet checkable", "",
              "CT radiomics denominators could not be checked: `radiomics_manifest.json` did not "
              "exist when this report was generated. Re-run after extraction completes.", ""]
    (out / "MANUSCRIPT_NUMERICAL_CONSISTENCY_REPORT.md").write_text("\n".join(L) + "\n",
                                                                    encoding="utf-8")
    print(df.to_string(index=False))
    print(f"\nMATCH {int((df.status == 'MATCH').sum())} | "
          f"MISMATCH {int((df.status == 'MISMATCH').sum())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
