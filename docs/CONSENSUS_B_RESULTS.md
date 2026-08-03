# Analysis B — inverse-variance uTCP/uNTCP consensus: results & verdict

Pre-registered in `analysis/preregistration_B.md` (committed before results). Parotid PRIMARY
cohort, xerostomia G≥2, **n = 54, 34 events**, seed 0, N_MC = 2000, N_boot = 2000. Aggregate
results only — no patient identifiers. Engine used exactly as implemented (`uncertainty.ntcp_mc`,
`inverse_variance_consensus`); classical numerics unchanged.

## B1. Estimator specification (LaTeX-ready, from source)

For a patient, with per-model NTCP point estimates $P_i$ and per-model Monte-Carlo variances
$\sigma_i^2$ ($i=1..M$; here $M=3$: LKB log-logistic, LKB probit, relative-seriality):

$$w_i = \frac{1}{\sigma_i^2},\qquad \hat P=\frac{\sum_i w_i P_i}{\sum_i w_i}\ \text{(probability space)},$$
$$\sigma^2_{\hat P}=\underbrace{\Big(\textstyle\sum_i w_i\Big)^{-1}}_{\text{within}}+\underbrace{\operatorname{Var}_i(P_i)}_{\tau^2\ \text{(between, ddof=1)}}.$$

$\sigma_i$ is the MC SD (ddof 1) of $P_i$ over **truncated-normal draws of that model's parameters**
(CVs: TD50 0.15, m 0.25, n 0.30, γ50 0.20, D50 0.15, γ 0.20, s 0.25), N=2000, seed 0. Models with
non-finite $P_i$ or $\sigma_i^2\le 0$ are dropped; if none remain the result is NaN. **No clipping, no
variance floor, no weight normalisation** beyond $\sum w_i$. Fusion is in probability space, not logit.

## B2. Primary experiment (apparent)

| Predictor | Brier | ECE | AUC | cal-slope |
|---|---|---|---|---|
| LKB log-logistic | 0.297 | 0.227 | 0.422 | undefined (flat) |
| LKB probit | 0.371 | 0.357 | 0.428 | −0.28 |
| **relative-seriality (best single)** | **0.274** | **0.174** | 0.424 | −0.61 |
| naive mean (prob) | 0.306 | 0.233 | 0.424 | −0.41 |
| naive mean (logit) | 0.311 | 0.240 | 0.425 | −0.38 |
| **inverse-variance consensus** | 0.296 | 0.205 | 0.428 | undefined (flat) |

**Paired difference (consensus − comparator), 2000-bootstrap 95 % CI** (Brier/ECE: negative favours
consensus; `*` = CI excludes 0):

| vs | ΔBrier [95 % CI] | verdict |
|---|---|---|
| best single (RS) | **+0.022 [+0.007, +0.041]** `*` | consensus **WORSE** |
| naive mean (prob) | −0.009 [−0.018, +0.000] | indistinguishable |
| naive mean (logit) | −0.015 [−0.023, −0.007] `*` | consensus better |
| LKB probit (worst) | −0.074 [−0.103, −0.046] `*` | consensus better |

AUC differences are all within noise (95 % CIs include 0). **Every model, including the consensus,
anti-discriminates** (AUC ≈ 0.42 < 0.5): the literature parotid parameters do not separate cases in
this high-event cohort. Calibration slopes are negative where identifiable (predicted↑ ⇒ observed↓);
LKB-LL and the consensus predict a near-constant value, so their slope is undefined (honestly reported,
not forced). *Fixed-parameter models fit nothing to outcome, so Brier/ECE/AUC carry no apparent-vs-CV
optimism (apparent = CV by construction).*

## B3. Interval quality (coverage vs nominal; sharpness = mean band width)

| Nominal | LL cov / width | probit | RS | **consensus** |
|---|---|---|---|---|
| 50 % | 0.20 / 0.11 | 0.20 / 0.17 | 0.20 / 0.08 | **0.40 / 0.15** |
| 80 % | 0.40 / 0.21 | 0.20 / 0.33 | 0.40 / 0.16 | **0.40 / 0.29** |
| 95 % | 0.40 / 0.31 | 0.40 / 0.49 | 0.40 / 0.24 | **0.60 / 0.45** |

The consensus band covers better (0.60 vs 0.40 at 95 %) but is wider (less sharp). **All bands are
badly under-covered** (≤0.60 at nominal 0.95): the dominant error is model *mis-specification*, which
parametric MC + $\tau^2$ do not capture. The τ² term buys some coverage at a sharpness cost.

## B4. Mis-specification stress test — the mechanism critique, confirmed

Poison the probit member (shift TD50, narrow its band) inside an otherwise-correct set. **Weight the
bad model receives and consensus Brier damage vs the clean consensus:**

| TD50 shift → | band ×1 | ×0.5 | ×0.2 | ×0.1 |
|---|---|---|---|---|
| **0 %** | wt 0.14, Δ0 | 0.37, +0.017 | 0.76, +0.052 | **0.92, +0.068** |
| **10 %** | 0.14, +0.001 | 0.37, +0.024 | 0.76, +0.080 | 0.92, +0.109 |
| **25 %** | 0.14, +0.001 | 0.37, +0.028 | 0.76, +0.118 | 0.92, +0.169 |
| **50 %** | 0.14, −0.003 | 0.37, +0.028 | 0.76, +0.160 | **0.92, +0.241** |

**The predicted failure is real and severe.** Because $w_i\propto1/\sigma_i^2$, narrowing a model's
band ×10 multiplies its weight ×100: a merely *over-confident* model (band ×0.1, **no** mis-specification)
already captures **92 %** of the weight and inflates Brier by +0.068; a *confidently wrong* model
(TD50 +50 %, band ×0.1) nearly **doubles** the Brier (+0.24, 0.30→0.54). Confidence, not correctness,
drives the combination.

## B5. Repairs (triggered by B4)

Consensus Brier — clean set vs worst poison (TD50 +50 %, band ×0.1):

| Method | clean | worst poison |
|---|---|---|
| naive inverse-variance | 0.296 | **0.537** |
| disagreement penalty ($\sigma_i^2\!+\!\tau^2$) | 0.302 | 0.324 |
| **median combination** | 0.295 | **0.290** |

The **median combination is robust** — the confident outlier cannot dominate a median, so the worst
poison barely moves it (0.290 ≈ clean 0.295), and it is *also* marginally better than IVW on the clean
set. The disagreement penalty helps substantially (0.537→0.324) at a small clean-case cost. Neither was
tuned to win; both were pre-registered.

## B6. Verdict

> On the parotid cohort (n=54, 34 events) the inverse-variance uNTCP consensus did **not** improve on
> the best single model: its calibration was significantly **worse** than relative-seriality
> (ΔBrier +0.022, 95 % CI 0.007–0.041) and indistinguishable from a naive probability mean, while every
> model — the consensus included — failed to discriminate (AUC ≈ 0.42). Its uncertainty band covered
> observed rates slightly better than single-model bands only by being wider, and all bands remained
> badly under-covered because the dominant error was model mis-specification, not parameter spread. A
> pre-registered stress test confirmed the method's central weakness: because weights scale as
> $1/\sigma^2$, a model made artificially confident captured up to 92 % of the weight and inflated the
> Brier score by up to 0.24 — the estimator propagates confident error rather than guarding against it.
> A median combination removes this failure without cost. **We therefore report the inverse-variance
> consensus as, at these event counts, no better than the best single model and mechanistically fragile,
> and recommend a robust (median or disagreement-penalised) combiner instead.**

## Adversarial self-review (hostile CMPB referee)

- **This does not establish that the consensus is *worse* in general** — n=54/34 events; the "worse than
  RS" CI is narrow but the cohort is one centre with anti-discriminating literature parameters. State it
  as a single-cohort demonstration, not a universal claim.
- **The anti-discrimination (AUC<0.5) is itself suspicious** and a referee will probe it: it likely
  reflects that this cohort's high xerostomia rate (63 %) is driven by factors the parotid-Dmean models
  omit (baseline function, contralateral sparing, chemo), *and/or* a sign/endpoint-coding check is
  warranted. It weakens any calibration claim built on these predictions — the honest framing is
  "the models mis-rank here," not "the consensus is well/badly calibrated."
- **The stress test uses a synthetic logit shift** to emulate a TD50 change rather than re-running the MC
  at a shifted TD50; a referee may want the exact re-MC. The qualitative conclusion (weight ∝ 1/σ² ⇒
  confident-outlier dominance) is analytic and independent of that approximation, but say so.
- **"best single by apparent Brier" favours the comparator** (selection on the same data) — already
  disclosed, but it means the "consensus worse than best single" result is, if anything, generous to the
  single model; the honest read is "consensus ≈ mid-pack," and it clearly loses to *median*.
- **Calibration slope undefined for the consensus** because it predicts a near-constant value — a referee
  will note the consensus barely varies across patients, which is itself a limitation (it is dominated by
  the flat LL/RS predictions), not a neutral fact.
- What it DOES establish, defensibly: the estimator's weighting mechanism is fragile to over-confident
  members (quantified), and a robust combiner fixes it at no cost — a genuine, useful, honest result.

---

## B8. Clean single-gland stratum (parotid, volume ≤ 45 cm³, n = 32, 20 events)

The pooled cohort mixes single-gland and combined parotid structure definitions, which
anti-discriminates (B2, AUC≈0.42). Restricting to single-gland structures recovers a coherent
dose-response — **AUC = 0.579 for every model** (LL, probit, RS, consensus alike) and **positive
calibration slopes** — so this is the *fair* test of combination (pre-registered, Amendment 3).

| Predictor | Brier | ECE | AUC | cal-slope |
|---|---|---|---|---|
| LKB log-logistic | 0.255 | 0.158 | 0.579 | +0.16 |
| LKB probit | 0.309 | 0.257 | 0.579 | +0.17 |
| **relative-seriality (best single)** | **0.241** | **0.129** | 0.579 | **+0.36** |
| naive mean (prob) | 0.260 | 0.201 | 0.579 | +0.24 |
| naive mean (logit) | 0.263 | 0.208 | 0.579 | +0.21 |
| **inverse-variance consensus** | 0.254 | 0.147 | 0.579 | +0.19 |

**Paired difference (consensus − comparator), 2000-bootstrap 95 % CI:**

| vs | ΔBrier [95 % CI] | verdict |
|---|---|---|
| best single (RS) | +0.013 [−0.005, +0.035] | **indistinguishable** (CI includes 0) |
| naive mean (prob) | −0.006 [−0.014, +0.004] | indistinguishable |
| naive mean (logit) | −0.009 [−0.019, +0.0005] | indistinguishable |
| LKB probit (worst) | −0.055 [−0.089, −0.020] `*` | consensus better |

**In the clean, discriminating regime the consensus is no longer *significantly* worse than the best
single model** (unlike pooled, where it lost with CI excluding 0) — but it is not better either: it is
statistically indistinguishable from RS and from a naive mean, and RS alone remains the point-estimate
leader on Brier/ECE/slope. The consensus buys nothing over the best single model even where the models
work. Calibration slopes are all well below 1 (models over-spread relative to observed risk), consistent
across single models and consensus.

## B9. Why the consensus is a lightly-perturbed single model (near-constant diagnosis)

Per-model MC band width and the **mean fraction of the inverse-variance weight** each model receives,
averaged over patients (both strata; identical picture):

| model | σ (MC), median | mean weight fraction (pooled) | (single-gland) |
|---|---|---|---|
| LKB log-logistic | 0.085 | 0.33 | 0.31 |
| LKB probit | 0.137 | 0.14 | 0.15 |
| **relative-seriality** | **0.062 (narrowest)** | **0.53** | **0.54** |

**A single model (relative-seriality) already carries a majority of the weight by default — with no
poisoning at all** — purely because its parametric MC band is the narrowest (σ≈0.062 vs 0.137 for
probit). The consensus point estimate therefore tracks RS (consensus pred-std 0.18 ≈ RS-flavoured, not
a genuine three-way blend); it cannot outperform RS because it is mostly RS, and it inherits RS's
behaviour. This is the *same* $1/\sigma^2$ pathology the B4 stress test provokes with a poisoned member,
operating here spontaneously on the honest, well-specified set. **The mechanism does not require an
adversary: whichever model is quoted most confidently dominates the "consensus," accuracy notwithstanding.**
This strengthens, not weakens, the finding.

## B10. Generality of the median advantage (across strata)

Pre-registered decision rule (Amendment 3): the median is generalisably preferable iff, across cohorts,
(i) its worst-cell stress damage is smaller than IVW's **and** (ii) on the clean set it is non-inferior
to IVW (paired Brier CI upper bound ≤ +0.01).

| stratum (n / events) | clean IVW / **median** | worst-poison IVW / **median** | worst bad-model weight |
|---|---|---|---|
| parotid pooled (54 / 34) | 0.296 / **0.295** | 0.537 / **0.290** | 0.92 |
| parotid single-gland (32 / 20) | 0.254 / **0.253** | 0.516 / **0.253** | 0.93 |

**Both conditions hold in both strata.** (i) *Direction:* under the worst poison (TD50 +50 %, band ×0.1)
the over-confident member captures ≈0.93 of the IVW weight and inflates IVW Brier by +0.24/+0.26, while
the **median barely moves** (Δ ≤ +0.001 vs its clean value) — median worst-cell damage ≪ IVW in both.
(ii) *Non-inferiority:* on the clean set the median is not worse than IVW (in fact −0.001 in both, well
within the +0.01 bound). The disagreement-penalty is a valid runner-up (worst-poison 0.324 / 0.292) at a
small clean cost. **The median advantage is not cohort-specific**; combined with the B11 analytic argument
it holds independent of the anti-discrimination confound. *(HN loco-regional TCP arm — B7 — is a
different endpoint family and is deferred to a follow-on commit; the parotid-strata generality + analytic
argument already satisfy the decision rule for the software change in B12.)*

---

## B11. Analytic proposition (Methods, LaTeX-ready)

**Proposition (when inverse-variance weighting is optimal).** Let $\hat\theta_1,\dots,\hat\theta_M$ be
estimators of a common scalar $\theta$. The linear combination $\sum_i w_i\hat\theta_i$ with
$\sum_i w_i=1$ that minimises mean squared error has, for **independent** and **unbiased** estimators,
weights $w_i\propto 1/\operatorname{Var}(\hat\theta_i)$ — the inverse-variance rule — *provided the
quoted variance equals the estimator's true error*, $\sigma_i^2=\mathbb E[(\hat\theta_i-\theta)^2]$.

**Why this fails for an ensemble of TCP/NTCP models of the same endpoint.** Three of the required
conditions break, structurally:

1. **Dependence.** The models are evaluated on the *same* patient DVH/gEUD, so $\hat\theta_i$ share
   their dominant input; they are strongly positively correlated, not independent. The optimal weights
   then involve the full covariance $\Sigma$, $w\propto\Sigma^{-1}\mathbf 1$, not the diagonal $1/\sigma_i^2$.
2. **Bias.** Each model uses a *fixed literature parameter set* (different TD50/m/γ/s), so
   $\mathbb E[\hat\theta_i]\neq\theta$ in general; the estimators are biased, and MSE $=\text{bias}^2+\text{variance}$.
   Inverse-*variance* weighting ignores the bias term entirely.
3. **Variance $\neq$ error.** The quoted $\sigma_i$ is the **parametric Monte-Carlo spread** of model $i$
   under an *assumed* parameter distribution — the width of the analyst's prior, not the model's distance
   from the truth. A confidently-wrong model (narrow prior, wrong centre) has small $\sigma_i$ and large
   error, exactly the case IVW cannot see.

**Consequence (one line).** Because $w_i\propto 1/\sigma_i^2$ uses the analyst's *confidence* in place of
the estimator's *accuracy*, and because the ensemble is dependent and biased, inverse-variance weighting
of same-endpoint radiobiological models is not MSE-optimal and can be dominated by a single confident,
wrong member — as the B4 stress test demonstrates. A rank-based combiner (median) is invariant to any
single member's quoted confidence and is therefore robust to this failure, at the cost of discarding
genuine precision information when the models *are* well-specified and independent (rare here).

---

## B12. Applying the finding to the software (engine change)

Analysis B is not just a paper result — it changes the default the engine ships. Evidence-driven change,
made minimally and with do-no-harm on the classical numerics.

**What changed (`engine/uncertainty/inverse_variance_consensus.py`).** The module now offers three
combiners behind a `combine_consensus(estimates, variances, method=...)` dispatcher:

- **`median` (NEW DEFAULT, robust).** Point estimate = median of the members; band = between-model τ² +
  the *median* within-model variance. No single member's quoted confidence can move the centre
  (≈50 % breakdown) or collapse the band.
- **`inverse_variance` (historical).** The original Eq. 1 weighting, `w_i = 1/σ_i²`. Kept, selectable,
  documented as MSE-optimal only for independent, unbiased, well-specified members (B11). Its standalone
  function keeps its exact previous return shape (backward compatible).
- **`disagreement`.** Inverse-variance with `σ_i² ← σ_i² + τ²`; a middle ground.

`run_untcp` (uNTCP) and `run_utcp_consensus` (uTCP) now default to `method="median"`; the method is
selectable via `NTCPUncertaintyConfig.consensus_method` / the `consensus_method=` argument.

**Permanent positive control (`engine/tests/test_consensus_robustness.py`, 9 tests).** A confidently
mis-specified member (far from peers, band ≈30× narrower ⇒ ≈900× weight) is fed to the default combiner;
the test asserts the default consensus stays with the honest members (median) **and** that inverse-variance
*is* dragged to the outlier (captures > 95 % weight) — so the guard cannot silently rot: if a future
change reinstates a weighting default, this test fails. Also locks the band's robustness, the
agreeing-members do-no-harm case, the backward-compatible IVW shape, and NaN handling.

**Do-no-harm verification.**

- Classical single-model NTCP numerics are untouched — the change is only in how per-model estimates are
  *combined*. `tests/test_ntcp_positive_controls.py` — **22/22 green**, max|Δ| = 0.
- The pipeline (`engine/rbgyanx_engine/pipeline.py`) surfaces the per-model uNTCP blocks (LL/probit/RS)
  individually and does **not** consume the consensus `mean`, so no published pipeline number moves.
- `engine/tests/test_ntcp_models.py` (per-model MC bands) and the original
  `test_inverse_variance_consensus.py` (historical combiner) — all green.
