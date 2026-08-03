# Manuscript evidence — factual answers, governance IDs, capability matrix, adversarial review

Deliverable for the CMPB/Physica Medica/Medical Physics manuscript. PHI-free. Cohort analyses
(Parts B, C, D, F, I–N) run from `analysis/RUNBOOK.md` on the private data and are not reproduced
here; this file holds the answers that do **not** need the cohorts.

## 1.1 Test count — reconciled

| Number | What it actually counts |
|--------|-------------------------|
| **748** | full-suite passed items on `main` today — a clean checkout of the default branch reproduces this (0 failures). |
| **763** | full-suite after PR #2 (DVH-integrity) merges (+15 integrity tests). |
| 663 | `def test_` functions across `tests/` + `engine/tests/` (the circulating "661"); parametrisation expands these to the item counts above. |
| 129 | `tests/test_publication_suite.py` alone. |
| 423 / 130 | stale (an old README total; a very old function count). Corrected in the new README. |

**The one number:** quote **748** for v1.0.0 as released on `main`; **763** after the DVH PR
lands. Reproduce the verbatim line with `pytest -q` on a clean checkout (exit 0, 0 failures).

## 1.2 Version truth

- Tags in existence: `v1.0.0` and a junk lightweight tag `rbGyanX`. **No `v2.0.0` exists** — the
  referee's claim of a v2.0.0 dated before v1.0.0 is **false**. (`git tag -l` → `rbGyanX`,
  `v1.0.0`.)
- Version is single-sourced at **1.0.0**: `engine/rbgyanx_engine/_version.py`, `pyproject.toml`,
  `VERSION.txt`, `CITATION.cff`, and the installer `.iss` all agree.

## H. Governance evidence — quoted negative-control test IDs

The safety claim (BASIC cannot instantiate or return an ADVANCED output; unavailable features
return NaN, not 0) rests on these tests:

- `tests/test_governance.py::test_basic_mode_disables_advanced_capabilities`
- `tests/test_governance.py::test_enable_ml_ignored_in_basic_mode` — the ML flag is *ignored* in BASIC.
- `tests/test_ui_policy.py::test_basic_denies_every_research_surface`
- `tests/test_ui_policy.py::test_ai_panel_is_governed_and_denied_in_basic`
- `tests/test_ui_policy.py::test_gating_defers_to_the_engine_capability_model` — the UI cannot widen access beyond the engine.
- `tests/test_ui_policy.py::test_parameter_editor_stays_closed_in_both_modes`
- NaN-not-zero: `tests/test_nan_safety.py::test_degenerate_ntcp_returns_nan_not_zero`,
  `::test_empty_dvh_volume_zero_returns_nan` (with `test_valid_{lkb_probit,lkb_loglogit,rs}_not_nan`
  as the paired positive controls).

Run: `pytest tests/test_governance.py tests/test_nan_safety.py tests/test_ui_policy.py -q`.

## 4-A Correctness (Figure 2) — controls hold

`analysis/scripts/correctness_curves.py` exports (all from the engine, deterministic):
NTCP-vs-dose/gEUD for LKB probit, LKB log-logistic, relative seriality at s = 0.10/0.25/1.00;
QUANTEC parotid + rectal anchors; the P+ factorisation. Verified at run time: every model passes
**NTCP = 0.5 exactly at its TD50/D50**, `gEUD(a=1) == mean dose`, and `P+ ≤ TCP` always.

## 5.8 Capability matrix (verifiable software facts)

What rbGyanX implements that the classical lineage (BIOPLAN, BioSuite, TCP_NTCP_CALC, RBMODELv1)
and ROE (CMPB 2024) do not — stated as code facts, not performance:

| Capability | rbGyanX (module) | Classical lineage | ROE |
|---|---|---|---|
| Enforced BASIC/ADVANCED governance (capability gate, tested) | `rbgyanx/logic/mode_controller.py` + governance tests | no | no |
| Per-estimate Monte-Carlo uncertainty bands | `engine/uncertainty/` | no | limited |
| Multi-model **inverse-variance consensus** (uNTCP/uTCP) | `uncertainty/inverse_variance_consensus.py` | no | no |
| Out-of-domain flag (robust-MCD Mahalanobis CCS) | `engine/validation/cohort_consistency.py` | no | no |
| NaN-not-zero degenerate-input contract (tested) | NTCP primitives + `test_nan_safety.py` | no | — |
| Cohort-independent analytic positive controls (22) | `tests/test_ntcp_positive_controls.py` | no | — |
| DVH-integrity validator (rejects inverted curves) | `engine/dicom_io/dvh_integrity.py` | no | — |
| Explainable-ML gated to ADVANCED | `rbgyanx/` xAI + `test_ui_policy.py` | no | no |

(The literature comparison is the author's to finalise; the middle/right columns are claims to
verify against those tools, not asserted here.)

## 5.9 Adversarial review (hostile-referee pass on the current evidence)

- **"748 vs 763" will be spot-checked.** State the exact number for the tagged commit and paste
  the verbatim `pytest` line; do not let the README and paper disagree (the old README said 487).
- **The consensus is the headline but is unvalidated (Part B).** With 34 parotid events, no
  performance claim survives review; report calibration (pre-specified primary) with bootstrap CIs
  and the stress test, and be willing to publish an honest negative. Do **not** tune to win.
- **CCS 24% flagged with no consequence (Part C/M)** is a referee magnet — either show the flag
  carries information (residual effect size + CI) or state plainly that it does not.
- **P+ is computed but never shown to change a decision (Part D).** One worked vignette is the
  minimum; without it, reviewers will call P+ decorative.
- **Small-N everywhere.** Frame I–N as *methodological* validation (coverage, stability,
  decomposition, decision instability), never as discrimination performance. Decision instability
  at n=54 is the most defensible novel result.
- **`paper/` ships a manuscript Methods/Results section** — reconcile with the paper's "no
  manuscript files in the repo" statement (keep as a synthetic capsule, or move out).
- **The demo `PTV70` DVH was inverted** until PR #2; make sure the tagged release includes that
  fix so a referee cloning the repo does not see a rising DVH.
