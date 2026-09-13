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

---

## Amendment 3 (2026-08-03, before the extension runs)

**Why supplement the pooled parotid result.** In the pooled parotid cohort every model
anti-discriminated (AUC≈0.42). This is a confound, not a property of the consensus: the pooled
cohort mixes single-gland and bilateral/combined parotid structure definitions, so a single
Dmean/gEUD-based dose-response cannot rank cases coherently across the mixture. A calibration
comparison built on mis-ranked predictions is not a fair test of *combination*. We therefore add:

- **B7 — HN loco-regional control** (TCP endpoint, n=121, 20 events): a different endpoint family and
  model set (tumour-control), same protocol (B2/B3/B4/B5), to test whether the median advantage is
  endpoint-specific.
- **B8 — clean parotid single-gland stratum** (volume ≤ 45 cm³, n=32, 20 events): the sub-cohort in
  which the dose-response is recovered (AUC≈0.58) and models are not mis-ranked. This is the
  scientifically clean calibration test; it, not the pooled cohort, is the fair comparison for
  calibration, and we state that explicitly.
- **B9** diagnoses the near-constant clean-case consensus; **B10** assesses generality; **B11** gives
  the analytic condition; **B12** applies the evidence to the software default.

**Decision rule for "the median advantage generalises".** Pre-specified: the median combiner is
called generalisably preferable to inverse-variance weighting iff, across the three cohorts
(HN, parotid-pooled, parotid-single-gland), (i) in the **B4 stress test** the median's worst-cell
Brier damage is smaller than IVW's in **all three** (direction), and (ii) in the **clean** (un-poisoned)
comparison the median is non-inferior to IVW on Brier (paired 95% CI upper bound ≤ +0.01) in **all
three**. If clean-case differences are indistinguishable from noise (expected at 20–34 events) we say
so and rest the claim on the stress-test direction + the B11 analytic argument, not on point estimates.
No outcome-driven re-tuning; the median and disagreement-penalty combiners are used exactly as
pre-registered in B5.

---

## Amendment 4 (2026-08-04, before the B13 runs)

**B13 — is the inverse-variance "winner" decided by arbitrary uncertainty metadata?** B9 found that
relative-seriality carries ~53 % of the 1/σ² weight un-poisoned because σ_RS≈0.062 < σ_probit≈0.137.
B13 establishes whether that dominance is a property of the *models* or of the *σ specification*.

**B13.1 — provenance of σ_i (reported, not computed).** Each model's MC σ is the SD over
truncated-normal draws of its parameters (`NTCPUncertaintyConfig`). Perturbed parameters, default CVs,
and cited sources (from `docs/archive/engine_rbGyanX_FIX_PROMPT.md`):
LKB-LL → TD50 (0.15, Deasy 1997), γ50 (0.20, Marks 2010) — **2 params**;
LKB-probit → TD50 (0.15), m (0.25), n (0.30, Deasy 1997) — **3 params**, and n enters as the gEUD
exponent 1/n (variance amplification);
RS → D50 (0.15), γ (0.20), s (0.25) (Källman 1992) — 3 params.
We state plainly which are arbitrary: the CVs are **round-number defaults** (0.15/0.20/0.25/0.30)
loosely attributed to those references, **not** values extracted from a specific table with a
documented derivation. No per-parameter literature covariance is encoded. The number of perturbed
parameters per model (2 vs 3) and the 1/n amplification are modelling choices, not data.

**B13.2 — sensitivity grid (single-gland stratum, n=32/20ev, seed 0, N_MC=2000).** For each model
m ∈ {LL, probit, RS} and scale k ∈ {0.5, 1, 2}, scale **only model m's CVs** by k (others at 1×) and
recompute σ_m by real MC; also a global control (all CVs ×k). For each cell record: mean 1/σ² weight
fraction per model, the **argmax (dominant model)**, and consensus Brier + calibration slope. Point
estimates are unchanged by CV scaling (nominal parameters), so only the weighting moves.

**B13.3 — decisive question, pre-committed answer rule.** If the identity of the dominant model
**flips** within this plausible range (a 0.5×–2× CV change, i.e. within one reference's stated
uncertainty), we conclude: *under inverse-variance weighting the ensemble output is determined by the
analyst's uncertainty metadata rather than by the models' agreement with data.* If dominance is stable
across the whole grid, we report stable dominance (a weaker but honest result).

**B13.4 — median contrast.** Repeat B13.2 for the median combiner. Prediction (to be confirmed or
refuted): the median point estimate is invariant to CV scaling (it ignores σ), so its consensus Brier
is **constant** across the entire grid. If instead the median moves, that refutes the robustness claim
and we say so. No outcome-driven tuning; CVs are scaled by fixed factors specified here in advance.

**Literature-alternative CV set:** none is encoded in the engine and we will not fabricate one; the
"alternative set" is realised as the ±2× reference-scale sweep above, which brackets the plausible
range. Marked N/A with this justification rather than invented.

---

## Amendment 5 (2026-08-04, before the B7 TCP-family runs)

**B7 — does the 1/σ² pathology generalise to a DIFFERENT model family?** B11 asserts the failure is
structural (dependence + bias + variance≠error), not endpoint-specific. That is a prediction; the TCP
family (different models, parameters, σ structure) is the test.

**B7.0 — REGISTERED PREDICTION (committed before wiring anything).** B11 predicts, on the TCP family:
- **(i) spontaneous concentration:** one TCP model will carry a disproportionate share of the 1/σ²
  weight with no adversary — pre-specified threshold: some model's mean weight fraction ≥ **0.50**
  (vs the equal-share 0.25 for M=4 models).
- **(ii) robust combiner wins:** the median is non-inferior to inverse-variance on the clean case
  (paired Brier 95 % CI upper bound ≤ +0.01) **and** strictly more robust under poisoning (worst-cell
  Brier damage smaller than IVW's).

**What would REFUTE the prediction (pre-committed):** if the TCP members' MC σ are homogeneous so that
**no** model's mean weight fraction exceeds ~0.40 **and** poisoning one member (shift + band-narrowing)
does **not** let it capture a dominant share of the weight, then the pathology does *not* generalise to
this family. In that case we report it plainly and give the structural reason (e.g. the four TCP models
share dose-response steepness / saturate together at prescription dose, so their σ are comparable) —
that is a more interesting result than a confirmation and will be reported as such. An indeterminate
verdict (CIs include the thresholds at these 20 events) is also permitted and will be stated.

**B7.1 — harness.** Wire the engine TCP family (Poisson-LQ, Zaider–Minerbo, gEUD-logistic, logistic;
`uncertainty.parameter_mc.run_parameter_mc`, HN `TCPSiteParams`) into the same consensus/comparator
code as NTCP. Models are used exactly as implemented — no numerics changed. Per-patient PTV DVH is
**reconstructed** as a truncated-normal(mean=PTV_Dmean_gy, sd=PTV_dose_std_gy) discretised into 40
physical-dose bins (volume_frac normalised to 1); this is a pre-registered approximation, justified
because PTVs are near-homogeneous (small dose std) so the reconstruction is tightly constrained by the
reported moments. n_fractions is the per-patient plan value. This DVH-reconstruction is a stated
limitation and does not affect the *relative* σ structure that the prediction is about.

**B7.2 — protocol.** HN loco-regional (n=121, 20 loco-regional failures). Endpoint = loco-regional
**control**; calibration/discrimination target y = 1 − locoregional (1 = controlled). Comparators:
each single TCP model; best single (apparent Brier); naive probability mean; naive logit mean;
inverse-variance; median; disagreement-penalty. Apparent + grouped-CV (grouped by treating centre),
paired bootstrap 95 % CIs (2000 resamples, seed 0, stratified by outcome). Interval quality (B3) and
the B4 stress + B5 repairs run as for parotid, poisoning one TCP member.

**B7.3** reports the spontaneous 1/σ² weight distribution across the four TCP models (the B9 analogue).
**B7.4** delivers the verdict against the registered prediction: confirmed / refuted / indeterminate,
with the structural explanation if refuted. Seed 0; pseudonymised, gitignored outputs; no re-tuning.
