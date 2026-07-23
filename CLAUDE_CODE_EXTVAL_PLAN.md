# rbGyanX — Claude Code reverse-engineering plan: full development + external validation of PINN vs classical radiobiology vs dosiomics

**Goal (your main aim):** a physics-informed neural network (PINN, LQ-constrained) for radiobiological outcome
(TCP and NTCP) **benchmarked head-to-head against classical radiobiological models and dosiomics**, on **real
external data**, under one leakage-safe protocol.

This document is the plan + a paste-ready Claude Code master prompt. Read "Data verdict" and "The cohort pivot"
first — they determine whether the aim is achievable, and they change which folder you point Claude Code at.

> **Phase 0 VERIFIED (2026-07-01) — see `docs/EXTVAL_DATA_READINESS.md`.**
> Benchmark cohort = **TCIA Head-Neck-PET-CT, n = 121** patients with dose + contours + outcome label (ID linkage
> perfect, 0 unlinked; 14 RTSTRUCT-only patients excluded). All dysphagia OARs + PTV present in **135/135**.
> Endpoints are small-event: loco-regional recurrence **20/121**, death **25/121**. **No toxicity endpoint here.**
> **Reference-dose caveat:** the archived RTPLANs are `UNAPPROVED` auto/reference plans (GDP-HMM repackaging), **not
> the delivered clinical dose** — so this is a **GO for model-vs-model benchmarking on real anatomy**, but a
> **NO-GO for delivered-dose outcome claims** until original clinical RTDOSE+RTSTRUCT are sourced. Frame TCP results
> as "association on reference-planned dose." Phase 0 gates in the prompt below are therefore already answered.

---

## 1. Data verdict — can the aim be served? (verified against your files)

I inspected `…\rbgaynx_desktop_paper\HNSCC`. The answer is **yes, with one mandatory pivot and honest endpoint scoping.**

| Requirement for the aim | AIRTP `HaN_valid_RTPLAN+RTDOSE` subset | Original TCIA collection zips |
|---|---|---|
| 3D dose grid (RTDOSE) | ✅ present (e.g. 91×182×119, Gy) | ✅ present |
| **Structure contours (RTSTRUCT)** — needed for **every** DVH, gEUD, organ dosiomics | ❌ **absent** (only `Pat_Obj_DICT.json` name lists + `PTV_DICT.json` metadata: `PDose`, `RingName` — no geometry) | ✅ **present** — `TCIA1_Head-Neck_Cetuximab.zip` (73 RS), `TCIA2_Head-Neck-PET-CT.zip` (135 RS), `TCIA5_HNSCC-3DCT-RT.zip` (27 RS) |
| CT (for QA / re-segmentation) | ❌ only `sample_patient` | ✅ present in the zips |
| Clinically delivered dose (vs auto-plan) | ❌ AIRTP plans are auto-generated, "not clinical-approved" | ✅ original clinical RTDOSE |
| **Outcome labels** | n/a | ✅ see below |

**Outcome labels available (verified columns):**
- `Head-Neck-PET-CT.xlsx` (Vallières; ~300 pts across 4 centre sheets): **Locoregional**, **Distant**, **Death** + event times → **TCP / loco-regional-control endpoint**. Clean, well-known outcome cohort.
- `HNSCC-MDA-Data_update_20240514.xlsx` (215 pts): **Loco-regional Control Censor**, Overall/Disease-Specific Survival, recurrence, **Received Feeding Tube (Y/N) + duration**, weight-loss/BMI, L3 sarcopenia → **TCP endpoint + a real NTCP toxicity proxy (feeding-tube dependence = severe dysphagia/mucositis).**
- `Head-Neck_Cetuximab.csv` is **only a TCIA download manifest** (Series UID, File Location) — *not* outcomes. Don't rely on it for labels.

**Bottom line for your aim:**
- **TCP side — fully serviceable.** PTV DVH + PTV dosiomics → classical TCP (Poisson-LQ, ZM, gEUD-logistic, logistic) vs dosiomics-ML vs PINN, all predicting **loco-regional control**. Use Head-Neck-PET-CT as primary cohort.
- **NTCP side — serviceable with the right endpoint.** Parotid *xerostomia* is **not** in this data, but **feeding-tube/dysphagia** (MDA) is. OAR DVHs (pharyngeal constrictors, larynx, oral cavity, parotids, cord) → classical NTCP vs OAR-dosiomics vs PINN, predicting feeding-tube dependence.
- **PINN headline (the actual scientific question):** does an LQ-physics prior let the network **match/beat classical models and resist the overfitting that sank unconstrained ML in your prior small-cohort work**? Small real N is the point, not a weakness.

---

## 2. The cohort pivot (do this or nothing downstream works)

**Stop using `HaN/HaN_valid/HaN_valid_RTPLAN+RTDOSE/` as the validation source** — it has no contours, and its dose is
an auto-plan that did not produce the recorded outcomes. **Use the original TCIA collection zips instead:**

```
HNSCC/Radiotherapy_HaN_Lung_AIRTP/HaN/
  TCIA2_Head-Neck-PET-CT.zip   ← PRIMARY: CT + RTSTRUCT + RTDOSE + RTPLAN, outcomes = Locoregional/Distant/Death
  TCIA1_Head-Neck_Cetuximab.zip← SECONDARY: full DICOM; outcomes only if a real RTOG-0522 outcome table is sourced
  TCIA5_HNSCC-3DCT-RT.zip      ← CT + RTSTRUCT (no dose in zip) — geometry/QA only
```

Endpoint ↔ cohort mapping you will actually use:

| Endpoint (label) | Cohort with BOTH dose+contours AND label | Side | Status |
|---|---|---|---|
| Loco-regional control | Head-Neck-PET-CT (TCIA2 zip + xlsx) | TCP | ✅ ready |
| Overall / disease-specific survival | Head-Neck-PET-CT; HNSCC-MDA | TCP | ✅ ready |
| Feeding-tube dependence (dysphagia) | HNSCC-MDA outcomes **+ original HNSCC RTSTRUCT** (must be fetched; the MDA dose on disk lacks RS) | NTCP | ⚠ needs RS fetch |

If you cannot obtain HNSCC RTSTRUCT for the MDA patients, run NTCP as a **cross-model consistency benchmark**
(does PINN/dosiomics reproduce classical NTCP on real OAR DVHs?) and clearly label it as label-free.

---

## 3. Master prompt — paste into Claude Code (Agent mode, repo = `project_rbGyanx`)

> Run from the repo root. Point it at the data with `RBGYANX_EXTVAL_DATA="…/rbgaynx_desktop_paper/HNSCC"`.
> Work phase by phase; do not skip the Phase 0 gates — they decide what is scientifically honest to build.

```
You are working in the rbGyanX repository in reverse-engineering mode. The engine already implements classical
TCP/NTCP, UTCP, uTCP/uNTCP consensus, MCD cohort-consistency (CCS), the therapeutic index/window, a four-tier
benchmarking harness, dosiomics, a Bayesian module, and an LQ-constrained PINN stub. Your job is to (A) finish and
harden these into a coherent, tested pipeline and (B) run a REAL external validation that benchmarks a
physics-informed neural network against classical radiobiological models and against dosiomics for TCP and NTCP
outcomes, on TCIA head-and-neck data. Preserve all validated classical numerics as regression contracts: if a
classical number changes, a test must justify it.

GROUND RULES
- Physics-first, do-no-harm: never alter BED/EQD2/LKB/gEUD/Poisson/ZM/UTCP numerics except where a test pins a
  corrected, literature-anchored value.
- Every change ships with a test. Prefer analytic anchors over snapshots.
- BASIC stays clinic-safe (cannot enable ML; returns NaN, never 0.0, for unavailable/empty inputs).
- Leakage-safe evaluation is mandatory: patient-grouped CV, no patient in both train and test, report apparent
  AND cross-validated metrics for every model class.
- Honesty over optimism: small real N is expected; report calibration and decision-curve analysis, and never claim
  clinical discrimination. The deliverable is a fair benchmark, not a winning model.

PHASE 0 — DATA READINESS GATES (block downstream work until each is answered in writing to docs/EXTVAL_DATA_READINESS.md)
  0.1 Unzip TCIA2_Head-Neck-PET-CT.zip (primary). Confirm per patient: CT series, ≥1 RTSTRUCT, ≥1 RTDOSE, RTPLAN.
  0.2 Parse RTSTRUCT ROI names; build an alias map onto rbGyanX canonical OARs/targets using the existing TG-263
      mapper (clinical/ + engine site detector). Report coverage: how many patients have PTV, pharyngeal
      constrictors, larynx, oral cavity, parotids, spinal cord, mandible.
  0.3 Link DICOM↔outcomes by patient ID. Report n with BOTH usable DICOM AND a non-missing label, per endpoint
      (loco-regional control; survival; — if HNSCC RS obtained — feeding-tube).
  0.4 Verify dose provenance: confirm RTDOSE is the delivered clinical dose, units Gy, grid aligned to CT frame of
      reference. Flag plan-sum vs per-beam.
  0.5 GO/NO-GO per endpoint. If feeding-tube NTCP has no contours, mark NTCP as label-free cross-model consistency
      and proceed; do not fabricate toxicity labels.

PHASE 1 — REPO RECONCILE & GREEN BASELINE
  - Commit/clean the local working-tree drift (currently dozens of modified, uncommitted files) so "what runs" ==
    "what's on GitHub". One source of truth for version (reconcile VERSION.txt 2025-12-25 vs CITATION/CHANGELOG
    1.0.0 vs release tag); set CITATION.cff doi to 10.5281/zenodo.20623120.
  - From a clean checkout: `pip install -e ".[dev]"` then `pytest` passes with zero env vars. ruff+black+mypy clean
    on engine/radiobiology and the new modules. Record counts in docs/EXTVAL_BASELINE.md.

PHASE 2 — REAL DVH + FEATURE EXTRACTION (the missing real-data front door)
  - Build engine/dicom_io extraction that, given (RTSTRUCT, RTDOSE[, RTPLAN]), yields per-structure cumulative
    DVHs via dicompyler-core, with EQD2/bDVH conversion using organ α/β when dose/fraction ≠ 2 Gy.
  - Derive, per patient: PTV metrics (gEUD, D95, D2, HI/CI if PTV+dose, BED/EQD2 from RTPLAN fractionation) and OAR
    metrics (gEUD, Dmean, Dmax, V-doses) for the dysphagia organ set.
  - Dosiomics: extend the existing DVH-shape/IBSI dosiomics to operate on the real DVHs AND (where CT+RTSTRUCT
    allow) on the 3D dose-in-ROI array. Output a tidy cohort_features.csv (one row/patient) with provenance.
  - Tests: round-trip on tests/synthetic DICOM factory; assert DVH metrics match closed-form on a synthetic ROI;
    assert NaN-not-zero on empty/zero-volume ROI.

PHASE 3 — MODEL CLASSES UNDER ONE HARNESS (the benchmark)
  Wire engine/validation/four_tier_harness.py to consume the Phase-2 features and these four classes, for each
  chosen endpoint (TCP: loco-regional control; NTCP: feeding-tube OR cross-model consistency):
    C1 Classical radiobiology: literature-fixed (T1) + MLE-refit with bootstrap CIs (T2). TCP = Poisson-LQ / ZM /
       gEUD-logistic; NTCP = LKB probit / log-logistic / relative-seriality.
    C2 Clinical-covariate logistic regression, EPV-gated (≥10 events/predictor), with age/stage/HPV/smoking (T3).
    C3 Dosiomics ML: XGBoost/RF on DVH + dosiomics features, leakage-safe StratifiedGroupKFold, SHAP/PDP (T4).
    C4 PINN (your headline): LQ-constrained NN minimising L = L_BCE + λ_phys·L_LQ + λ_bc·L_BC, predicting the SAME
       endpoint from the SAME features as C3, under the SAME CV folds. Make λ_phys a swept hyperparameter so you can
       show the physics-prior effect (λ_phys=0 reduces to a plain NN ablation).
  Report per model & class: AUC (apparent + grouped-CV), bootstrap Brier, Hosmer-Lemeshow, ECE, calibration slope,
  and decision-curve net benefit. Emit one tidy benchmark table + the Fig-4-style apparent-vs-CV optimism plot.

PHASE 4 — PINN-vs-CLASSICAL-vs-DOSIOMICS ANALYSIS (answer the scientific question)
  - Headline comparison: at matched CV folds, does C4 (PINN) ≥ C1 (classical) and ≥ C3 (dosiomics) on CV-AUC and
    calibration, and does the LQ prior REDUCE the apparent→CV optimism gap relative to λ_phys=0?
  - Ablations: λ_phys sweep; features = DVH-only vs +dosiomics; N-subsampling curve (performance vs cohort size) to
    demonstrate the small-sample regime where physics regularisation should help most.
  - uTCP/uNTCP consensus + CCS on the real cohort: report consensus curves, flag out-of-domain plans (real
    Mahalanobis), and the therapeutic index/window where a PTV+OAR pairing exists.
  - Write docs/EXTVAL_RESULTS.md with every number, seed, and the exact command to reproduce.

PHASE 5 — REPRODUCIBILITY & MANUSCRIPT WIRING
  - Add an extval reproduction capsule (scripts + a de-identified, redistributable feature table if licences allow;
    otherwise a synthetic mirror) and a CI job that runs the pipeline on the synthetic mirror.
  - Update the paper: add an "External validation" Methods+Results section; move the relevant claims from
    "synthetic only" to "synthetic + external"; keep the no-clinical-discrimination caveat; add a TRIPOD-style
    reporting checklist and a data-use/PHI statement for TCIA.
  - Final gate: pytest green; ruff/black/mypy clean; docs/EXTVAL_RESULTS.md complete; benchmark table + optimism
    plot regenerated by one command; data-readiness GO/NO-GO recorded.

For each phase, report: files changed, tests added, pass/fail counts, and any data-readiness blocker. Stop and ask
if a Phase-0 gate fails rather than fabricating labels or contours.
```

---

## 4. Phased plan — acceptance criteria (human-readable companion to the prompt)

**Phase 0 — Data readiness (gate).** `docs/EXTVAL_DATA_READINESS.md` exists with: per-endpoint n having dose+contours+label; OAR-coverage table from RTSTRUCT alias mapping; dose-provenance confirmation; explicit GO/NO-GO. *No modelling before this passes.*

**Phase 1 — Green baseline.** Clean checkout installs and `pytest` passes with no env vars; local drift committed; single version source; Zenodo DOI in CITATION.cff.

**Phase 2 — Real DVHs.** Given RTSTRUCT+RTDOSE, the engine emits per-structure DVHs and a tidy `cohort_features.csv` with PTV + dysphagia-OAR metrics + dosiomics; round-trip and NaN-contract tests pass.

**Phase 3 — Benchmark.** Four model classes run on identical patient-grouped CV folds for each endpoint; one benchmark table reports AUC(apparent+CV), Brier, H-L, ECE, calibration slope, DCA; the apparent-vs-CV optimism plot regenerates.

**Phase 4 — Scientific answer.** A documented head-to-head of PINN vs classical vs dosiomics, a λ_phys sweep showing the physics-prior effect, an N-subsampling curve, and consensus/CCS on the real cohort.

**Phase 5 — Reproduce + manuscript.** CI runs the pipeline on a synthetic mirror; the paper gains an honest External-Validation section with TRIPOD reporting and a TCIA data-use statement.

---

## 5. Honest caveats to keep the work publishable

- **Small N / few events.** Grouped CV + bootstrap CIs are mandatory; expect wide intervals. Frame as a fair benchmark and a stress-test of the physics prior, not a deployable model (consistent with your prior small-cohort findings).
- **Endpoint substitution.** Feeding-tube dependence is a *dysphagia* NTCP surrogate, not xerostomia; state this explicitly and cite the constrictor/larynx dose–dysphagia literature.
- **Auto-plan vs delivered dose.** Only the original TCIA RTDOSE corresponds to the recorded outcomes; never model outcomes from the AIRTP auto-plan dose.
- **Licence/PHI.** TCIA collections are de-identified but carry data-use terms (the GDP-HMM AIRTP README is gated, CC-BY-NC-SA). Do not redistribute patient DICOM in the repo; ship only derived, non-identifying feature tables if their licence allows, plus a synthetic mirror for CI.
- **No silent ML substitution.** Keep the governance contract: PINN/dosiomics outputs are reported beside, never instead of, classical estimates.
```
