# rbGyanX manuscript-evidence RUNBOOK (manual PowerShell)

Deterministic, seed-0, provenance-stamped. **PHI never leaves the private folders and is never
committed** — `analysis/.gitignore` excludes `inputs/` and `outputs/`. Every step writes a
`provenance.json` (inputs, seed, versions, git commit, timestamp).

Repo: `C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx`
Private data (PHI, outside repo): `C:\Users\Sampa\OneDrive\Desktop\rbgaynx_desktop_paper`
(`HNSCC\`, `SPARK_data\`, `internal_validation_data_NTCP\`, `validation_study\`).

Status legend:  ✅ implemented + smoke-tested  ·  🧩 script scaffolded, runs on your private data  ·  📐 designed, script to be added

---

## Step 0 — environment (once) ✅

```powershell
cd C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".\engine" -e ".\engine_advanced" -e ".\engine_advanced_f" -e ".[dev,ml,torch,bayesian]"
python -c "import sys,numpy,pandas,sklearn; print(sys.version); print('numpy',numpy.__version__)" `
  | Tee-Object analysis\outputs\env.txt
$env:PYTHONHASHSEED=0
```
Expected: prints Python 3.10–3.12 and pinned versions; writes `analysis\outputs\env.txt`.

## Step 1 — correctness curves (Figure 2), engine-only, NO patient data ✅

```powershell
python analysis\scripts\correctness_curves.py
```
Expected console:
```
Part 4-A correctness curves -> ...\analysis\outputs\correctness
  fixed points all == 0.5 : True
  gEUD(a=1) == mean dose  : True
  P+ <= TCP always        : True
  rows: dose_response=905, anchors=4
```
Outputs (`analysis\outputs\correctness\`): `dose_response_curves.csv` (LKB probit, LKB
log-logistic, relative seriality at s=0.10/0.25/1.00), `fixed_points.csv`, `quantec_anchors.csv`,
`pplus_factorisation.csv`, `provenance.json`. Runtime < 10 s.

## Step 2 — cohort staging + flow + data dictionary (Part 2) 🧩

For each cohort, produce the input manifest (md5, role — **pseudonyms only, no PHI filenames**),
the PRISMA flow (screened → contours → dose → endpoint → analysed with count+reason per
exclusion), and the derived-feature data dictionary. Parotid inputs stay referenced in place.

```powershell
python analysis\scripts\stage_cohort.py --cohort hn      --root "..\rbgaynx_desktop_paper\HNSCC"
python analysis\scripts\stage_cohort.py --cohort spark   --root "..\rbgaynx_desktop_paper\SPARK_data"
python analysis\scripts\stage_cohort.py --cohort parotid --root "..\rbgaynx_desktop_paper\internal_validation_data_NTCP" --reference-in-place
```
Per-endpoint n/events to report: HN loco-regional + death; SPARK GU + rectal-GI;
parotid xerostomia G≥2 (n=54, 34 events).

## Step 3 — the consensus study (Part B) 📐
`consensus_study.py`: spec dump (weights ∝ 1/σ², fusion space, σ definition, NaN/zero-variance
handling, variance floor) → grouped-CV comparison of each single model / best single / naive mean
/ inverse-variance consensus, **calibration slope + ECE + Brier PRIMARY**, AUC secondary, apparent
+ CV with bootstrap 95% CIs → the deliberate-misspecification stress test (B3) → plain verdict.

## Step 4 — CCS out-of-domain informativeness (Parts C, M) 📐
`ccs_informativeness.py`: calibration/discrimination in flagged vs unflagged HN plans; residual
effect size + CI; AUC of CCS for predicting large residuals; robust-MCD vs classical Mahalanobis;
χ² cutoff sensitivity.

## Step 5 — P+ / therapeutic-window vignette (Part D) 📐
`pplus_vignette.py`: one worked plan comparison where P+ ranking differs from single-NTCP or
DVH-constraint ranking (synthetic or de-identified).

## Step 6 — parotid stratified QA diagnostic (Part F) 🧩
`parotid_stratified.py` (extends `validation_study/scripts/parotid_stratified.py`): volume strata,
follow-up strata, age-vs-dose DeLong, cutoff sensitivity. Likely the headline.

## Step 7 — uncertainty quantification (Part I) 📐
`uncertainty_study.py`: MC-band coverage at 50/80/95%; parameter (MC) vs sampling (bootstrap)
variance decomposition per cohort; **decision instability** — fraction of patients whose 95% band
crosses a clinical threshold (xerostomia NTCP=20% and a second), per model and for the consensus.

## Step 8 — dosiomics / PINN / xAI methodology (Parts J, K, L) 📐
Feature ICC under DVH perturbation + redundancy + selection-stability (Jaccard) across folds (J);
λ-sweep + λ=0 ablation, per-fold variance/calibration, monotone-response plot (K); in-fold SHAP
with rank-agreement stability + radiobiological plausibility, ADVANCED-gated (L).

## Step 9 — governance evidence (Part H) ✅ (tests already exist)
```powershell
pytest tests\test_governance.py tests\test_nan_safety.py tests\test_ui_policy.py -q
```
Negative controls proving BASIC cannot instantiate/return ADVANCED output, and unavailable
features return NaN (not 0): see `docs/MANUSCRIPT_EVIDENCE.md` §H for the quoted test IDs.

## Step 99 — regenerate everything 📐
`run_all.py` chains Steps 1–8 and writes a single `analysis\outputs\INDEX.json`.
```

## Provenance
Every `provenance.json` records: inputs (paths + md5, pseudonymised), `seed=0`, package versions,
`git rev-parse HEAD`, UTC timestamp. Re-running a step overwrites its own output dir only
(idempotent).
