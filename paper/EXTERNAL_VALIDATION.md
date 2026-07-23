# External validation — manuscript section (Methods + Results)

Paper-ready section for the Medical Physics manuscript. Numbers are reproduced by the
pipeline in `external_validation/` from the TCIA Head-Neck-PET-CT cohort; full tables,
seeds and the reproduce command are in `docs/EXTVAL_RESULTS.md`. No patient PHI or DICOM is
included here or in the repository.

## Methods

**Cohort.** We used the public TCIA **Head-Neck-PET-CT** collection (Vallières et al.),
four Québec centres (HGJ, CHUS, HMR, CHUM). Of 135 patients with RT structure sets, **121**
had a plan-sum RTDOSE and an outcome label (0 unlinked); 14 structure-only patients were
excluded. Endpoints were loco-regional recurrence (**20/121**, primary) and death
(**25/121**, secondary). There is no toxicity endpoint in this cohort.

**Dose provenance (key limitation).** The archived RTPLANs are `UNAPPROVED` auto/reference
plans (GDP-HMM repackaging), **not the delivered clinical dose**. All dose–outcome results
are therefore framed as **association on reference-planned dose** — a model-vs-model methods
benchmark on real anatomy, not a delivered-dose outcome validation.

**Feature extraction.** Per patient we computed cumulative DVHs (dicompyler-core) for the
prescription PTV and the dysphagia organ set (pharyngeal constrictors, larynx, oral cavity,
parotids, submandibular, spinal cord), then derived PTV gEUD/D95/D2/HI/CI, BED/EQD2 from
plan fractionation, per-OAR Dmean/Dmax/gEUD/EQD2/V-dose, and DVH-shape dosiomics. Empty or
zero-volume ROIs yield NaN (never 0.0).

**Model classes (one protocol).** Four classes were evaluated on identical centre-grouped
`StratifiedGroupKFold` folds: **C1** classical radiobiology (literature-fixed logistic-TCP;
MLE-refit dose–response), **C2** clinical-covariate logistic regression (age, HPV), gated at
≥10 events/predictor, **C3** dosiomics random forest, **C4** an LQ-constrained
physics-informed neural network minimising L = L_BCE + λ_phys·L_LQ + λ_bc·L_BC (λ_phys swept;
λ_phys = 0 is the plain-NN ablation). We report apparent and cross-validated AUC, Brier
score with bootstrap 95% CI, Hosmer-Lemeshow, expected calibration error, calibration slope,
and decision-curve net benefit, plus an N-subsampling learning curve and MCD cohort-consistency.

## Results

On loco-regional control (20 events), **clinical covariates gave the best cross-validated
AUC (0.638)**, comparable to the dosiomics random forest (0.629) and above the refit
classical dose–response (0.501) and the PINN (0.58–0.60). Every ML/PINN model overfit
severely — apparent AUC ≈ 1.0 collapsing to CV ≈ 0.6 (optimism 0.30–0.45). The LQ physics
prior produced a small, regime-dependent benefit: it improved CV-AUC and reduced the
optimism gap on the DVH-only feature set (0.553 → 0.595) and improved death-endpoint Brier
and calibration (0.270 → 0.221), but did not confer a discrimination advantage over the
classical or dosiomics models. The N-subsampling curve was flat/noisy in N, and MCD
cohort-consistency flagged 24% of plans as outside the dose-feature domain.

**Interpretation.** On real head-and-neck anatomy with reference-planned dose and few
events, an LQ-prior PINN is a fair but not superior competitor to classical and dosiomics
models; the physics prior tempers, but does not rescue, small-sample overfitting. **No claim
of clinical discrimination is made.**

## TRIPOD reporting checklist (abbreviated)

| Item | Where |
|---|---|
| Source of data / study design | External validation, retrospective public cohort — Methods |
| Participants / eligibility | 121 dose+contour+label patients; 14 excluded — Methods |
| Outcome definition | Loco-regional recurrence; death — Methods |
| Predictors | PTV/OAR DVH metrics, dosiomics, clinical covariates — Methods |
| Sample size / events | n=121; 20 LR / 25 death events — Methods |
| Missing data | NaN-preserving; medians for covariates; HPV 63/121 |
| Model specification | C1–C4 — Methods; code in `engine/validation/` |
| Model performance | AUC (apparent+CV), Brier±CI, H-L, ECE, calibration slope, DCA — Results |
| Model evaluation / validation | Centre-grouped StratifiedGroupKFold; bootstrap CIs |
| Limitations | Reference-planned (not delivered) dose; small N/events — Methods |
| Reproducibility | `docs/EXTVAL_RESULTS.md`; CI runs the synthetic mirror |

## TCIA data-use / PHI statement

The TCIA Head-Neck-PET-CT collection is publicly available under its TCIA data-use terms;
the GDP-HMM AIRTP repackaging is CC-BY-NC-SA. Patient DICOM is **not** redistributed in this
repository. Only derived, de-identified feature tables are produced (kept out of version
control), plus a fully synthetic mirror for continuous integration. TCIA identifiers are
already de-identified; no protected health information is stored or shared.
