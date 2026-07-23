# rbGyanX — high-level audit (Phase 0)

_Inventory only — **no fixes applied in this phase**. Generated 2026-07-18 on branch
`feat/extval-benchmark` at rbGyanX v1.0.0._

Scientific findings are cross-referenced to `validation_study/SCIENTIFIC_AUDIT.md` (private
workspace). **Cohort-specific result numbers stay in the private validation workspace**; this
public report describes the *software* defects and is reproducible on synthetic data.

---

## 1. Baseline health

| Check | Result |
| --- | --- |
| Full test suite (`pytest`, zero env vars) | **539 passed, 3 skipped, 0 failed** (exit 0) |
| ruff — CI-enforced scope | clean |
| black — CI-enforced scope | clean |
| mypy — `engine/radiobiology` | clean (16 source files) |
| ruff — whole repo incl. unmaintained legacy | 1,819 errors (not gated; see §3) |

The maintained engine is green. The defects below are **behavioural/scientific**, not test failures —
the existing tests do not pin the NTCP science, which is precisely the gap Phase 1 closes.

---

## 2. Correctness & scientific defects

Severity: **S-High** = invalidates results · **S-Med** = latent/misleading · **S-Low** = hygiene.

### A1 · Classical NTCP tier does not use the engine's NTCP models — **S-High** (→ S1)
The NTCP benchmark's "classical" predictor is, in at least one arm, a **data-fitted logistic on OAR
mean dose**, not the engine's LKB/RS. A fitted proxy cannot validate the tool's models, and it
inflates the classical tier's apparent performance relative to a genuinely fixed model.
*Also:* the TCP-specific `classical_t1` in `engine/validation/extval_benchmark.py`
(`PTV_EQD2`, `TCD50=63.5`, returns `1−TCP`) is correct for TCP but must never reach an NTCP arm.
**Verified:** driver code builds the classical column via an MLE refit, per its own comment.

### A2 · Relative-Seriality NTCP saturates to ≈1.0 — **S-High** (→ S2)
`radiobiology.ntcp.rs_poisson` returns ≈1.0 for essentially every realistic OAR DVH
(**verified**: across a real 54-patient parotid set the output spans 0.9999923–0.999999999999999 —
only *2 distinct values*). A constant predictor has AUC ≈ 0.5 **by construction**, so any RS result
reported to date is meaningless. Root cause is parametrisation/normalisation (and possibly DVH
binning), not the data.

### A3 · Parotid gEUD exponent wrong for a parallel organ — **S-Med** (→ S3)
`engine/config/site_params_ntcp_default.yaml` sets parotid `geud_a: 3.0`. Xerostomia is a
**mean-dose (a ≈ 1)** endpoint (QUANTEC); a = 3 over-weights hot spots for a parallel gland.

### A4 · DVH unit handling is heuristic — **S-Med** (→ S4)
`txt_dvh_reader._to_gy` converts by guessing (`value > 150 → ÷100`) and the curve path applies a
further unconditional ÷100. A plan legitimately exceeding 150 Gy (or an already-Gy file with large
values) silently mis-converts by 100×. Units are declared in the file header and must drive the
conversion deterministically.

### A5 · TCP and NTCP paths are entangled — **S-Med** (→ S5)
`extval_benchmark` mixes a TCP-specific dose driver/`1−TCP` inversion with generic tiering, making
it possible for TCP logic to leak into NTCP arms (this is how A1 arose).

### A6 · No positive-control tests for the models — **S-High (gap)** (→ S6)
Nothing pins NTCP=0.5 at gEUD=TD50, monotonicity in dose, QUANTEC/rectal LKB reproduction, or UTCP
factorisation. Without these, A2-class bugs pass CI silently. This is also the strongest evidence a
tool paper can present ("the engine reproduces validated models").

### A7 · Structure-definition heterogeneity in a derived cohort — **S-Med, data-side** (→ S3)
The institutional parotid input carries a single `Structure: Parotid` per patient whose **volume
varies ~7-fold across patients** (single-gland vs bilateral/combined cannot be distinguished from the
export). This dilutes any dose–response and cannot be reconstructed from the data alone — S3's
"reconcile, else STOP and report" branch applies. *(Details/numbers: private workspace.)*

---

## 3. Dead code & duplication

### D1 · Legacy `code1–7` monoliths — **11,760 lines**
| Module | Imported by | Status |
| --- | --- | --- |
| `code1_dvh_preprocess.py` | 1 | duplicates engine DVH preprocessing |
| `code2_dvh_plot_and_summary.py` | 1 | duplicates plotting/summary |
| `code3_ntcp_analysis_ml.py` | 1 | duplicates NTCP + ML |
| `code4_ntcp_output_QA_reporter.py` | **0** | **dead** |
| `code5_ntcp_factors_analysis.py` | **0** | **dead** |
| `code6_tcp_analysis.py` | **0** | **dead** |
| `code7_tcp_ntcp_integration.py` | **0** | **dead** |

Four modules (~half the legacy LOC) are imported by nothing. All seven duplicate engine
functionality and are excluded from lint/type gates — they account for most of the 1,819 whole-repo
ruff errors.

### D2 · Three DVH-text parsing implementations
1. `engine/dicom_io/txt_dvh_reader.py` — **canonical** (`parse_dvh_text_file`,
   `parse_multi_structure_dvh_text`, `iter_dvh_text_files`); the only one that is tested.
2. `utils/dvh_parser.py` — `UniversalDVHParser` + `preprocess_dvh_intelligent`, legacy, overlapping.
3. `code1_dvh_preprocess.py` — a third legacy path.
Divergent unit handling between these is the vector for A4.

### D3 · Multiple benchmarking entry points
`engine/validation/extval_benchmark.py` (TCP), `engine/validation/four_tier_harness.py` (NTCP),
`engine/validation/hnscc_external_val.py`, `external_validation/run_benchmark.py`,
`external_validation/run_phase4_analysis.py`. No single documented entry point; the TCP/NTCP split
is by convention rather than by interface (see A5).

---

## 4. Redundant workflows
- **Two GUIs' worth of surface in one file:** `rbgyanx_gui.py` (9,336 lines, 271 Tkinter references)
  mixes UI, orchestration, and data handling — no separation to migrate against (Phase 4 risk).
- **Reporting duplication:** `code4` QA reporter vs `engine/outputs/*` vs GUI-side reporting.
- **Generated-artifact hazard:** report/inventory generators previously wrote real-data artifacts into
  tracked paths (already remediated in `0b2aaf2`; now gitignored). Keep generators PHI-blind.

---

## 5. Priority for Phase 1+

| # | Fix | Phase | Rationale |
| --- | --- | --- | --- |
| 1 | A1 wire real NTCP models; TCP/NTCP separation (A5) | P1 S1/S5 | invalidates current NTCP results |
| 2 | A2 RS saturation | P1 S2 | predictor is constant → meaningless |
| 3 | A6 positive-control tests | P1 S6 | prevents recurrence; key paper evidence |
| 4 | A3 parotid a≈1; A7 reconcile/report | P1 S3 | model-endpoint mismatch |
| 5 | A4 explicit units | P1 S4 | latent 100× error |
| 6 | D1–D3 de-duplication | P2 | after science is pinned by tests |

**Do-no-harm constraint:** the HN TCP arm is correct — its numerics must stay byte-identical through
P1/P2. NTCP numbers *will* change; they are pinned by new positive-control tests, not by old values.

---

## 6. Phase 1 outcome (2026-07-18)

Suite after P1: **574 passed, 3 skipped, 0 failed** (was 539 — 35 tests added). CI-scoped
ruff/black/mypy clean. HN TCP numerics unchanged.

| ID | Fix | Commit | Status |
| --- | --- | --- | --- |
| A2 (S2) | RS complement-inside-product corrected; de-saturated | `8c0d541` | ✅ |
| A6 (S6) | 22 positive controls (TD50 fixed point, monotonicity, QUANTEC/rectal anchors, UTCP) | `8c0d541` | ✅ |
| A4 (S4) | Explicit header-declared dose units; magnitude rule demoted to warned fallback | `820daf9` | ✅ |
| A3 (S3) | Parotid `geud_a` 3.0 → 1.0; gEUD(a=1) ≡ mean dose pinned | `820daf9` | ✅ |
| A1 (S1) | `validation/ntcp_benchmark.py`: engine LKB/RS as classical tier; MLE refit of same family | `94fa139` | ✅ |
| A5 (S5) | TCP/NTCP paths separated; AST guard forbids the TCP predictor in NTCP | `94fa139` | ✅ |
| A7 (S3) | Parotid cohort reconciliation | — | ⛔ **STOP — reported** |

**A7 / S3 is deliberately unresolved (see §7 for the stratified follow-up).** The engine-side parotid fixes are complete, but the
dose→xerostomia association could not be recovered as positive from the derived cohort: it is
non-significant (p≈0.35), unaffected by structure-volume stratification, and only turns positive in
the ≥12-month follow-up subset (n=13). Closing it needs the prior pipeline's endpoint and structure
definitions, which are not derivable from the exported data. Per the S3 instruction this is reported,
not papered over — details in the private `validation_study/S3_PAROTID_RECONCILIATION.md`.
**P3 (re-validation) of the parotid arm is blocked on this decision.**

---

## 7. Phase 2 outcome — de-duplication (2026-07-18)

### D1 · Legacy monoliths retired to `legacy/` (quarantined, not deleted)
**13,868 LOC moved out of the supported tool** via `git mv` (history preserved). See
[`legacy/README.md`](../legacy/README.md) for the per-file supersession table.

| Moved | Referenced by | Now |
| --- | --- | --- |
| `code4/5_*.py` | nothing (genuinely dead) | `legacy/` |
| `code3/6/7_*.py` | **`tests/` via subprocess** (not imports) | `legacy/` |
| `code1/2_*.py` | only `qa_comprehensive_test_suite.py` | `legacy/` |
| `qa_comprehensive_test_suite.py`, `rbgyanx_qa_test_suite.py` | nothing (standalone `__main__`) | `legacy/` |

> **Correction to §3/D1.** That inventory reported `code4/5/6/7` as "imported by 0 = dead". That
> was measured on `import` statements only. `code3`, `code6` and `code7` are in fact invoked by
> `tests/test_integration.py`, `tests/test_ntcp_analysis.py` and `tests/test_tcp_analysis.py`
> **via `subprocess`**, which an import scan does not see. The P2 suite run caught this (5
> failures). Only `code4` and `code5` were truly dead. Those three test modules were repointed to
> `legacy/…` so the retired pipeline stays verified where it now lives, and the suite is green
> again. Lesson recorded: dead-code claims need a call/subprocess scan, not just imports.

Nothing in the supported tree *imports* `legacy/`; the only references are those three
legacy-pipeline test modules, which exercise it deliberately. Excluded from packaging
(`tool.setuptools.packages.find`), ruff (`extend-exclude`) and coverage (`omit`).
**Whole-repo ruff errors: 1,819 → 1,534.**

Enforced by `tests/test_no_legacy_imports.py`: no module under `engine/ rbgyanx/ clinical/
utils/ qa/ models/ external_validation/ examples/ scripts/ tests/` may import a quarantined
module, and the files must not reappear at the repo root.

### D2 · DVH readers: 3 → 2, with a documented single canonical
- **Canonical:** `engine/dicom_io/txt_dvh_reader.py` — the only reader used by the engine, CLI
  and benchmarks, the only one under test, and the only one with deterministic header-declared
  units (P1 · S4).
- `code1_dvh_preprocess.py` (third reader) — **retired** to `legacy/`.
- `utils/dvh_parser.py` (`UniversalDVHParser`) — **deprecated in place**, with a docstring
  notice pointing to the canonical reader. It cannot be removed yet: `rbgyanx_gui.py` imports it
  and the Tkinter→Qt migration is deferred to a separate project. **Full unification to a single
  reader completes with that migration**, when the GUI reads through the engine.

### D3 · Single documented benchmarking entry point
New `engine/validation/benchmark.py` → `run_arm_benchmark(df, kind="tcp"|"ntcp", endpoint=…)`.
A facade, deliberately **not** a merge: it dispatches to `extval_benchmark` (TCP) or
`ntcp_benchmark` (NTCP), preserving the P1 · S5 separation. The NTCP branch **raises** unless an
engine model and its fixed parameters are named, so a fitted proxy cannot be passed off as a
classical tier (the A1 defect is now structurally unreachable through the public entry point).

### Not changed
`rbgyanx_gui.py` (9,336 lines) still mixes UI, orchestration and data handling, and reporting is
still duplicated between the GUI and `engine/outputs/*`. Both are entangled with the deferred Qt
migration and were left alone rather than half-refactored.

---

## 8. Phase 3 outcome — re-validation (2026-07-18)

Track-B arms were re-run against the corrected engine in the **private** workspace; no study
data or PHI enters this repo. Two further engine defects surfaced during the re-run and were
fixed here:

### P3-a · Patients with no OAR contour crashed the NTCP path — **fixed**
`run_ntcp_benchmark` computed a NaN classical NTCP for a patient lacking the OAR structure and
then failed inside `roc_auc_score`. Such patients are now **excluded explicitly and counted**
(`extras["n_excluded_missing_dose"]`) rather than imputed to 0.0 — imputing would fabricate a
"no complication" patient, bias the classical tier and violate the NaN-not-zero contract. A
single remaining class after exclusion raises a clear error.

### P3-b · The T2 MLE refit could run away on a flat likelihood — **fixed**
With no dose–response the likelihood is flat and the unbounded optimiser drifted to physically
meaningless parameters (observed on real data: **TD50 ≈ 2.4 × 10¹⁶ Gy**, calibration slope
≈ −2.7 × 10¹⁴). The refit is now:
* **bounded** to the data-supported dose range (TD50 within ~[0.5·min, 2·max] dose, capped at
  200 Gy) and to plausible steepness (`m` ∈ [0.02, 1.5]; `γ50` ∈ [0.1, 10]);
* solved with L-BFGS-B under those bounds;
* reported with a `plausible` flag — when the fit is pinned to a bound or TD50 falls outside the
  observed dose span it is surfaced in the results table as
  **"refit not identifiable from these data (flat likelihood)"** instead of being presented as a
  result.

Both are covered by new tests (exclusion count, single-class error, bounded refit, plausibility
flag on a genuine dose–response).

### Do-no-harm verification
The HN TCP arm was re-run and diffed against the pre-correction tables:
**max |Δ| = 0.000e+00 across all three benchmark tables — byte-identical.** The corrections are
confined to the NTCP path, as intended.

### Reproduction
The anonymised capsule was rebuilt around the corrected path: the retired proxy driver is gone
and `capsule/run_all.py` now drives both arms through the single documented entry point
`validation.benchmark.run_arm_benchmark`. Verified end-to-end from the derived tables.

---

## 9. Phase 1.6 outcome — defensive hardening (2026-07-18)

A systematic pass over parameter fitting and degenerate inputs, reusing the input-validation and
positive-control infrastructure from A4/S6. **HN TCP re-run and diffed: max |Δ| = 0.000e+00 —
byte-identical.**

### 9.1 Every parameter fit is bounded and reports identifiability

| Site | Failure mode | Hardening |
| --- | --- | --- |
| `ntcp_benchmark.fit_ntcp_mle` | unbounded optimiser on a flat likelihood → **TD50 ≈ 2.4 × 10¹⁶ Gy** (observed on real data) | bounded to the data-supported dose range + plausible steepness; `plausible` flag surfaced as *"refit not identifiable from these data (flat likelihood)"* |
| `ntcp_calibration.fit_lkb_parameters` | bounded, but returned the **initial guess** on failure and reported bound-pinned fits as if they were fits | new `identifiable` + `note` fields; at-bound and non-convergence detected, logged, and returned as unusable |
| `validation_metrics.calibration_slope` | unbounded Nelder-Mead; separation drives the slope to ±∞ | pre-guards (n<3, non-finite, single-class outcome, constant predictor) + admissibility check rejecting \|slope\| > 10 |
| `four_tier_harness._calibration_slope` | `LinearRegression` on near-constant predictions → **≈ −2.7 × 10¹⁴** | NaN on zero-variance predictor, single-class outcome or non-finite input; rejects \|slope\| > 100 |

> **Method note (do-no-harm).** The first attempt at `calibration_slope` swapped Nelder-Mead for
> L-BFGS-B and shifted HN TCP by 2.6 × 10⁻⁵. The requirement is *bounding*, not a different
> algorithm, so the original optimiser was restored and the bounds implemented as pre/post
> checks. Well-behaved cohorts therefore stay bit-identical to previous releases while
> pathological fits are refused.

### 9.2 Degenerate-input guards (exclude-and-count, never impute)
Covered: empty DVH · single-bin DVH · zero-volume ROI · missing ROI / missing OAR dose ·
all-zero dose · single-class endpoint (all events **and** no events) · fewer than 2 CV groups ·
all patients missing dose · constant predictor · perfect separation.

- `_effective_splits()` bounds grouped CV by both distinct groups **and** the minority class.
- `_safe_auc` / `_safe_brier` score only the finite subset and return NaN when nothing is
  scoreable, instead of raising.
- `compute_geud` returns NaN (never 0.0) for zero total volume.
- **Bug found by the new tests:** a single-centre cohort produced `GroupKFold(n_splits=1)`, which
  raises. Grouped CV is now skipped with a warning and CV metrics reported as NaN — an honest
  "no out-of-fold estimate available" rather than a crash or in-sample predictions relabelled
  as CV.

### 9.3 Tests
`tests/test_edge_cases_hardening.py` — **17 tests** with a flat-likelihood fixture, one class per
degenerate category above, plus identifiability checks for both fitting routines. Run together
with the 22 positive controls, which continue to pass unchanged.
