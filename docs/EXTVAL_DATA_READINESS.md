# External validation — Phase 0 data-readiness report

**Date:** 2026-07-01 · **Cohort probed:** TCIA `Head-Neck-PET-CT` (Vallières; centres HGJ, CHUS, HMR, CHUM)
**Source archive:** `…/rbgaynx_desktop_paper/HNSCC/Radiotherapy_HaN_Lung_AIRTP/HaN/TCIA2_Head-Neck-PET-CT.zip`
**Method:** extracted the 135 RTSTRUCT files, parsed ROI names, mapped to rbGyanX canonical structures, cross-linked
to `Head-Neck-PET-CT.xlsx` outcomes by patient ID, and read RTPLAN/RTDOSE headers for provenance.

## 1. Availability cross-tab

| Quantity | n |
|---|---|
| Patients with RTSTRUCT | 135 |
| Patients with RTDOSE (plan-sum) | 121 |
| **Dose + contours (RS ∩ RTDOSE)** | **121** |
| Dose + contours + outcome label | **121** (0 unlinked) |
| Patients with an outcome row (all centres) | 300 |
| RTSTRUCT-only, no dose (excluded) | 14 |

ID linkage is clean: DICOM PatientID (`HN-CHUM-001`) matches the xlsx `Patient #` exactly; **0** of the 135 RS
patients failed to link to an outcome row.

## 2. Endpoints and event counts (analysis-ready cohort, n = 121)

| Endpoint | Events | Non-events | EPV budget (≥10 ev/pred) |
|---|---|---|---|
| Loco-regional recurrence (TCP side) | 20 | 101 | ~2 predictors |
| Death / overall survival | 25 | 96 | ~2–3 predictors |
| Distant metastasis | (column present) | — | — |

These are **small-event** endpoints — exactly the regime where the four-tier harness and the PINN's LQ prior are
meant to be stress-tested. There is **no toxicity endpoint** in this cohort (xerostomia/feeding-tube not recorded
here); NTCP-toxicity needs the MD-Anderson `HNSCC-MDA` feeding-tube endpoint plus its own contours (separate fetch).

## 3. Structure coverage (per corrected ROI mapping, n = 135)

| Canonical structure | Patients | Notes |
|---|---|---|
| PTV (any dose level) | 135/135 | multi-level: PTV70, PTVHighOPT, PTVMid, PTVLow, PTV_Total, + Ring* |
| PharynxConstrictor | 135/135 | `PharynxConst` — dysphagia OAR |
| Larynx | 135/135 | dysphagia OAR |
| OralCavity | 135/135 | dysphagia OAR |
| Parotid (any) | 135/135 | contoured as bilateral `Parotids` + ipsi/contra; **not** explicit L/R |
| Submandibular | 134/135 | |
| SpinalCord | 135/135 | |
| Mandible | 135/135 | |
| Brainstem | 135/135 | |
| Cochlea | 135/135 | |

Coverage is total and uniform — the same standardized structure list appears in every patient (`PTVHighOPT`,
`RingPTVHigh`, `BrainStem_03`, `SpinalCord_05`…), i.e. an **auto/atlas contour set**, not heterogeneous clinician
contours. Two parsing rules for the pipeline: (a) prefer the **pure OAR** contour over `-PTV`-suffixed planning
subtraction volumes (`Parotids-PTV`, `OCavity-PTV` are not the true organ); (b) pick a single prescription PTV
(`PTV70`/`PTVHighOPT`) for the TCP target and one plan-sum RTDOSE per patient (≈3 dose objects exist per patient).

## 4. Dose provenance — the key caveat (verified from headers)

RTPLAN headers report **`ApprovalStatus = UNAPPROVED`**, `Manufacturer = Varian / ARIA RadOnc`, plan dates
2024-11, with cryptic auto-labels (`S2A4AcI1`); RTDOSE is `DoseSummationType = PLAN`, `PHYSICAL`, Gy. Combined with
the standardized auto-contours, **these are re-generated reference/auto plans (the GDP-HMM repackaging), not the
originally delivered clinical plans.** The recorded loco-regional/survival outcomes came from the patients' *actual*
treatment, which is **not** the dose in this archive.

**Implication:**
- ✅ Valid to use for: real-anatomy DVH/dosiomics extraction, and **model-vs-model benchmarking** (classical TCP/NTCP
  vs dosiomics vs PINN) including calibration, optimism (apparent vs grouped-CV AUC), consensus (uTCP/uNTCP), and CCS.
- ⚠️ **Not** a clean delivered-dose outcome validation. Frame any outcome result as "association on
  reference-planned dose," or obtain the **original delivered** RTDOSE+RTSTRUCT for these patients before making
  dose→outcome prediction claims.

## 5. GO / NO-GO

| Use | Verdict |
|---|---|
| Build real DVH + dosiomics front-end and run the four-class benchmark (classical vs covariate vs dosiomics vs PINN) on real HN anatomy | **GO** (n=121; all OARs+PTV present) |
| TCP / loco-regional-control modelling as a **methods benchmark** with honest small-N + reference-dose caveats | **GO, caveated** (20 events) |
| Delivered-dose outcome validation / clinical-association claims | **NO-GO until delivered clinical dose obtained** |
| NTCP **toxicity** (feeding-tube/dysphagia) | **NO-GO here** — endpoint not in this cohort; use HNSCC-MDA + fetch its contours |

## 6. Recommended next actions for the Claude Code run

1. Proceed with Phases 1–3 of `CLAUDE_CODE_EXTVAL_PLAN.md` using these **121 patients** as the benchmark cohort,
   with grouped (by centre + patient) CV and bootstrap CIs; report apparent vs CV AUC, Brier, ECE, calibration, DCA.
2. Treat the headline as a **methods/benchmarking** result (PINN LQ-prior vs classical vs dosiomics under small N on
   real anatomy), with the reference-dose caveat stated in Methods.
3. For a delivered-dose outcome claim, source the raw TCIA Head-Neck-PET-CT clinical RTDOSE+RTSTRUCT (or another
   cohort with delivered dose + outcome). For NTCP toxicity, pair HNSCC-MDA feeding-tube outcomes with HNSCC RTSTRUCT.
4. Do not commit any patient DICOM to the repo (TCIA/GDP-HMM licences); ship only derived non-identifying feature
   tables (if licence permits) plus the synthetic mirror for CI.

*Counts produced from the extracted RTSTRUCT set + zip listing; reproducible from the commands in the session log.*
