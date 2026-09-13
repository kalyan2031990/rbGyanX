# External validation — results (Phases 3–4)

**Cohort:** TCIA Head-Neck-PET-CT, **n = 121** (4 centres), loco-regional recurrence
**20/121**, death **25/121**. **Reference-dose caveat:** the archived RTPLANs are
`UNAPPROVED` auto/reference plans (GDP-HMM), **not the delivered clinical dose** — every
result below is an **association on reference-planned dose**, a *methods benchmark*, not a
delivered-dose outcome claim, and **no clinical discrimination is claimed**.

**Protocol:** identical centre-grouped `StratifiedGroupKFold` (n_splits = 4) folds for all
model classes; apparent AND cross-validated (CV) metrics for every class; bootstrap Brier
CIs. Seed = 0.

**Reproduce:**
```powershell
python external_validation/build_cohort_features.py --zip ".../TCIA2_Head-Neck-PET-CT.zip" `
  --clinical ".../Head-Neck-PET-CT.xlsx" --out external_validation/data/cohort_features.csv
python external_validation/run_benchmark.py     --features external_validation/data/cohort_features.csv --out-dir external_validation/data/benchmark --seed 0
python external_validation/run_phase4_analysis.py --features external_validation/data/cohort_features.csv --out-dir external_validation/data/benchmark --seed 0
```

## 1. Benchmark — loco-regional control (dosiomics features, n = 121, 20 events)

| Class | Model | Apparent AUC | CV AUC | Optimism | Brier [95% CI] | H-L p | ECE | Calib. slope | Net benefit |
|---|---|---|---|---|---|---|---|---|---|
| C1.T1 | classical fixed-TCP | 0.600 | 0.600 | 0.000 | 0.211 [0.18, 0.25] | 0.00 | 0.237 | 0.21 | −0.001 |
| C1.T2 | classical MLE (EQD2) | 0.600 | 0.501 | 0.099 | 0.143 [0.10, 0.19] | 0.22 | 0.015 | 0.00 | 0.030 |
| C2.T3 | clinical logistic (age+HPV, EPV 10) | 0.715 | **0.638** | 0.077 | 0.158 [0.12, 0.21] | 0.00 | 0.122 | 0.39 | 0.047 |
| C3.T4 | dosiomics RF | 0.998 | 0.629 | 0.369 | 0.137 [0.10, 0.18] | 0.26 | 0.057 | 1.19 | 0.031 |
| C4 | PINN plain (λ=0) | 1.000 | 0.589 | 0.411 | 0.265 | 0.00 | 0.280 | 0.05 | −0.013 |
| C4 | PINN LQ (λ=0.5/1/2) | 1.000 | 0.580–0.583 | 0.42 | 0.286 | 0.00 | 0.31 | 0.04 | −0.024 |

## 2. Benchmark — loco-regional control (DVH-only features)

| Class | Model | Apparent | CV | Optimism |
|---|---|---|---|---|
| C3.T4 | dosiomics RF | 0.991 | 0.612 | 0.378 |
| C4 | PINN plain (λ=0) | 1.000 | 0.553 | 0.447 |
| C4 | PINN LQ (λ=1) | 1.000 | **0.595** | **0.405** |

## 3. Benchmark — death (secondary, 25 events)

| Class | Model | Apparent | CV | Optimism | Brier |
|---|---|---|---|---|---|
| C1.T1 | classical fixed-TCP | 0.450 | 0.450 | 0.000 | 0.251 |
| C2.T3 | clinical logistic | 0.585 | 0.290 | 0.295 | 0.206 |
| C3.T4 | dosiomics RF | 0.957 | 0.661 | 0.296 | 0.156 |
| C4 | PINN plain (λ=0) | 1.000 | 0.608 | 0.392 | 0.270 |
| C4 | PINN LQ (λ=1) | 1.000 | 0.608 | 0.392 | **0.221** |

## 4. Scientific answer (the headline question)

> *At matched folds, does the PINN (C4) ≥ classical (C1) and ≥ dosiomics (C3) on CV-AUC and
> calibration, and does the LQ prior reduce the apparent→CV optimism gap vs λ_phys = 0?*

**No, not on this reference-dose cohort — and that is the honest result.**

1. **Clinical covariates win CV discrimination.** C2 (age + HPV) gives the best
   loco-regional CV-AUC (**0.638**), ≈ dosiomics RF (0.629) and above the refit classical
   dose-response (0.501) and the PINN (0.58–0.60). On near-uniform reference-planned tumour
   dose, dose features add little over prognostic clinical variables.
2. **Every ML/PINN model massively overfits.** Apparent AUC ≈ 1.0 collapses to CV ≈ 0.6
   (optimism 0.30–0.45) — the small-N regime this study is designed to expose.
3. **The LQ physics prior helps modestly and conditionally, not universally.** It **reduced**
   the optimism gap and improved CV-AUC for the DVH-only loco-regional set (0.553 → 0.595,
   optimism 0.447 → 0.405) and **improved Brier/calibration for death** (0.270 → 0.221), but
   **slightly worsened** the loco-regional dosiomics set. It did not make the PINN beat the
   classical or dosiomics models on discrimination.

**Conclusion:** on real HN anatomy with reference-planned dose and 20 events, an LQ-prior PINN
is a fair but not superior competitor; the physics prior's benefit is a small,
calibration-side, regime-dependent effect. This is consistent with the prior small-cohort
finding that unconstrained ML overfits — the prior tempers, but does not rescue, the
small-sample regime. Optimism plots: `external_validation/data/benchmark/optimism_*.png`.

<!-- PHASE4_ABLATIONS -->
## 5. Ablations (N-subsampling learning curve, cohort consistency)

### 5.1 N-subsampling learning curve (loco-regional, dosiomics; mean CV-AUC, 3 repeats)

| N | events | RF | PINN plain (λ=0) | PINN LQ (λ=1) |
|---|---|---|---|---|
| 40 | ~9 | 0.652 | 0.630 | 0.629 |
| 60 | ~12 | 0.533 | 0.496 | 0.509 |
| 80 | ~14 | 0.624 | 0.596 | 0.590 |
| 100 | ~15 | 0.606 | 0.562 | 0.545 |
| 121 | 20 | 0.654 | 0.531 | 0.517 |

The dosiomics RF is ≥ the PINN at every cohort size, and the LQ prior gives **no
consistent gain** over the plain NN in stratified-CV subsampling (a slight edge only at
N=60). Curves are flat/noisy in N — the expected signature of a **weak dose→outcome signal
on reference-planned dose** with few events. Plot: `subsampling_curve.png`.
(In the centre-grouped benchmark, §2, the LQ prior did help the DVH-only set and death
calibration — the physics prior's benefit is real but small and regime-dependent.)

### 5.2 MCD cohort-consistency (out-of-domain flagging)

Robust Mahalanobis CCS on 6 dose features (PTV EQD2/gEUD/HI, Parotids/Constrictor Dmean,
Cord Dmax): **29/121 (24%)** plans flagged outside the χ²₀.₉₇₅ domain (crit 14.45),
median CCS 0.67 — the cohort carries a substantial heterogeneous-dose tail that a
deployment guard would flag for review. Report: `ccs_report.json`.

### 5.3 uTCP/uNTCP consensus

The inverse-variance uTCP/uNTCP consensus (`engine/uncertainty/`) combines multiple
uncertainty-bearing model estimates; on this reference-dose cohort it is reported as a
cross-model consistency demonstration (not a delivered-dose claim) alongside the CCS flag.
<!-- /PHASE4_ABLATIONS -->

## 6. Honesty checklist

- Small N / few events → wide bootstrap CIs; apparent **and** CV reported for every class.
- No clinical-discrimination claim; results are association on reference-planned dose.
- No fabricated labels/contours; endpoint counts reproduce `docs/EXTVAL_DATA_READINESS.md`.
- No patient DICOM committed; only the derived, de-identified feature table (gitignored).
