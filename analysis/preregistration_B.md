# Pre-registration — Analysis B: inverse-variance uTCP/uNTCP consensus

**Committed before any result exists.** Do not edit after results; append dated amendments only.
Seed 0 everywhere; pseudonymised, gitignored outputs under `analysis/outputs/consensus_B/`.

## B1. The estimator, exactly as implemented (`engine/uncertainty/inverse_variance_consensus.py`)

For patient with per-model NTCP point estimates $P_i$ and per-model Monte-Carlo variances
$\sigma_i^2$ (models $i = 1\dots M$):

- Weights (fusion in **probability space**, not logit): $w_i = 1/\sigma_i^2$.
- Consensus estimate: $\displaystyle \hat P = \frac{\sum_i w_i P_i}{\sum_i w_i}$.
- Within-model variance: $\sigma^2_{\text{within}} = 1/\sum_i w_i$.
- Between-model spread: $\tau^2 = \operatorname{Var}_i(P_i)$ (sample variance, ddof=1; 0 if $M=1$).
- Combined variance: $\sigma^2_{\hat P} = \sigma^2_{\text{within}} + \tau^2$; band SD $=\sqrt{\sigma^2_{\hat P}}$.
- **Degenerate handling:** a model contributes only if $P_i,\sigma_i^2$ are finite and $\sigma_i^2>0$;
  if none qualify the result is NaN. **No clipping, no variance floor, no weight normalisation** beyond $\sum w_i$.

$\sigma_i$ is the MC standard deviation (ddof=1) of $P_i$ over **truncated-normal draws of that model's
parameters** (per-parameter CVs; `ntcp_mc.py` defaults e.g. TD50_cv=0.15, m_cv, n_cv, γ_cv, D50_cv,
s_cv), **N=2000 draws, seed 0** for this analysis (the engine default is 1000/seed 42; we fix
2000/seed 0 for stability + determinism and record it).

## B2. Design

**Models under combination** (parotid/HN NTCP): LKB log-logistic, LKB probit, relative-seriality,
each at literature parameters (parotid xerostomia; QUANTEC/HyTEC-era). Per patient: point $P_i$ at the
patient's gEUD + $\sigma_i$ by MC.

**Comparators** (identical patients, identical $P_i$ inputs):
(a) each single model; (b) best single model — chosen by lowest **apparent Brier** (favours the
comparator; stated); (c) naive unweighted mean of $P_i$; (d) naive mean in logit space
($\operatorname{logit}^{-1}(\text{mean}_i\operatorname{logit}P_i)$); (e) inverse-variance consensus (method under test).

**Cohorts:** (1) **parotid, xerostomia G≥2, n=54, 34 events — PRIMARY**; (2) HN loco-regional,
n=121, 20 events — SECONDARY; (3) SPARK GU, n=42, 13 events — DESCRIPTIVE only.

**Endpoints:** PRIMARY = calibration: slope, intercept, ECE (10-bin), Brier. SECONDARY = AUC.
INTERVAL (B3) = empirical coverage at nominal 50/80/95 % and mean band width (sharpness).

**Optimism note (pre-specified):** the NTCP models and the consensus are **fixed-parameter** — they
fit nothing to outcome, so Brier/ECE/AUC have **no apparent-vs-CV optimism** (apparent = CV by
construction; we report this explicitly, not as a null result). The **calibration slope/intercept**
are obtained by logistic recalibration ($\text{event}\sim\operatorname{logit}\hat P$), which *is* fit
and therefore reported both apparent and grouped-CV.

**Folds:** parotid — stratified 5-fold on the event, seed 0, + leave-one-out sensitivity; HN — grouped
by treating centre if present else stratified 5-fold seed 0. **Bootstrap:** 2000 resamples (stratified
by event), seed 0, for every metric CI and for **paired** differences (consensus − comparator).

## Decision rule (fixed in advance)

Per cohort, the consensus is called:
- **BETTER** than a comparator iff the paired difference favours the consensus on the PRIMARY
  (lower Brier AND/OR ECE, and calibration slope nearer 1) with a bootstrap **95 % CI excluding 0**,
  against **both** (i) the best single model and (ii) the better of the two naive means;
- **WORSE** iff a comparator beats it with 95 % CI excluding 0;
- **EQUIVALENT / INDISTINGUISHABLE** iff the 95 % CI includes 0 — the expected outcome at 20–34 events,
  and it will be reported as such (no ranking on point estimates).
Interval quality (B3) is judged separately: better = coverage nearer nominal at equal-or-better sharpness.

## B4 stress test (pre-specified)

Poison one member of a correctly-specified set: shift its TD50 by ±10/25/50 % **and** narrow its
parametric band (σ ×1, ×1/2, ×1/5, ×1/10). For each grid cell record the poisoned model's consensus
weight and the change in consensus calibration (Brier, slope) vs the un-poisoned consensus. Output a
2-D (mis-specification × confidence) → damage map.

## B5 repairs (only if B4 shows a failure; labelled secondary)

(i) variance floor; (ii) disagreement penalty $\sigma_i^2 \leftarrow \sigma_i^2 + \tau^2$; (iii) trimmed/
median combination; (iv) leave-one-model-out influence. Report whether any fixes the failure **without**
degrading the well-specified case. Repairs are never presented as the original method.

## Guarantees

Seed 0; provenance.json per output; no patient identifier in any output (pseudonyms only); outputs
gitignored; classical numerics unchanged (22 positive controls stay green); the consensus is used
exactly as implemented — no modification to win.

---

## Amendment 1 (2026-08-03, before results)

On inspecting the engine config, the parotid organ (`HN/Parotid_L`) parameterises **only** LKB
log-logistic (TD50=28.4, γ50=0.6) and relative-seriality (D50=28.4, γ=1.0, s=0.25) at geud_a=1.0;
**LKB probit is not configured for parotid**. To keep the pre-registered **3-model** design (and a
richer stress test), the analysis adds a documented QUANTEC-era parotid **probit** parameterisation
(TD50=39.9 Gy, m=0.40, n=1.0 → mean-dose form) *for the analysis only* — the engine config is not
modified (do-no-harm). If a reader prefers the strict engine set, the 2-model (LL+RS) consensus is
reported alongside as a sensitivity. No outcome data has been examined at the time of this amendment.

## Amendment 2 (2026-08-03, before results)

Scope for this run: the **parotid PRIMARY** cohort is executed in full (B2–B4). The HN loco-regional
arm is a **TCP** (tumour-control) consensus over a different model set and the SPARK arm is
descriptive; both are deferred to a follow-on commit so the primary result is delivered clean. This
does not change the pre-registered endpoints or decision rule.
