# Audit → scientific fixes → de-duplication → re-validation (P0–P3)

Phases 0–3 of `CLAUDE_CODE_FIX_AUDIT_GUI.md`. **Phases 4 (Qt GUI) and 5 (AI-API) are
deliberately out of scope** and deferred to a separate project.

**Suite: 583 passed / 3 skipped / 0 failed.** CI-scoped ruff + black + mypy clean.
**HN TCP numerics byte-identical** (re-run and diffed: max |Δ| = 0.000e+00 across all three
benchmark tables).

## P0 — audit (`7998bdd`)
`docs/AUDIT_REPORT.md`: 7 defects (A1–A7) verified independently, plus a dead-code and
duplication inventory.

## P1 — scientific fixes
| Fix | Commit |
| --- | --- |
| **S2** relative-seriality saturation — the complement was applied *inside* the product, so low-dose bins collapsed it and NTCP was pinned at 1.0 for every patient. It agreed with truth only at `s=1` with a single uniform bin, which was exactly the one case the old test covered. | `8c0d541` |
| **S6** 22 positive controls: NTCP = 0.5 at TD50 for probit, log-logistic **and RS for any seriality `s`**; monotonicity; QUANTEC parotid + rectal LKB anchors; exact UTCP factorisation. | `8c0d541` |
| **S4** dose units taken from the file's own headers; the `>150` magnitude rule demoted to a *warned* fallback (it silently divided legitimate >150 Gy plans by 100). | `820daf9` |
| **S3** parotid `geud_a` 3.0 → 1.0 (parallel/mean-dose endpoint); gEUD(a=1) ≡ mean dose pinned. | `820daf9` |
| **S1/S5** new `engine/validation/ntcp_benchmark.py` — the NTCP classical tier **is** the engine's LKB/RS model (the fitted mean-dose proxy is gone); T2 is an MLE refit of the *same family*; direct polarity. TCP/NTCP paths separated, enforced by an AST guard. | `94fa139` |

**S3 is deliberately left open** (`ccee265`): the parotid dose→xerostomia association could not be
recovered as positive from the derived cohort, and closing it needs the prior pipeline's endpoint
and structure definitions. Reported, not papered over.

## P2 — de-duplication (`d524077`)
- **13,868 LOC** quarantined to `legacy/` via `git mv` (history preserved), excluded from
  packaging/ruff/coverage. Whole-repo ruff **1,819 → 1,534**.
- **DVH readers 3 → 2** with a documented canonical (`engine/dicom_io/txt_dvh_reader.py`).
  `utils/dvh_parser.py` is deprecated *in place* because the Tkinter GUI still imports it;
  full unification lands with the deferred Qt migration.
- **Single entry point** `run_arm_benchmark(kind="tcp"|"ntcp")`, whose NTCP branch **raises**
  unless an engine model + fixed parameters are named — the A1 proxy defect is now structurally
  unreachable through the public API.
- **Correction to my own P0 finding:** P0 called `code4/5/6/7` dead based on an import-only scan.
  `code3/6/7` are invoked by three test modules via **subprocess**; the P2 suite run caught this
  (5 failures). Only `code4/5` were truly dead. Tests repointed; correction recorded in the audit.

## P3 — re-validation (`88b2f69`)
Arms re-run against the corrected engine in the **private** workspace (no study data or PHI in
this repo). Two further engine defects surfaced and were fixed:
- **Missing OAR contour** produced a NaN classical NTCP and crashed `roc_auc_score`. Such
  patients are now **excluded and counted**, never imputed to 0.0 (which would fabricate a
  "no complication" patient and violate the NaN-not-zero contract).
- **The T2 MLE refit ran away on a flat likelihood** — on real data it returned
  **TD50 ≈ 2.4 × 10¹⁶ Gy** with calibration slope ≈ **−2.7 × 10¹⁴**. It is now bounded to the
  data-supported dose range and reported as *"refit not identifiable from these data"* instead of
  being presented as a result.

## Review notes
- The NTCP numbers **change by design**; they are pinned by the new positive-control tests, not
  by previously observed values. The HN TCP arm is unchanged.
- No study data, cohort tables, results or PHI are added to this repo.
