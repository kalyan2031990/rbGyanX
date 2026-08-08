# rbGyanX — Engineering Changelog (independent stabilisation)

Every change made during the independent verification, with rationale, files, risk, and whether it
could move a baseline number. **Nothing here alters a radiobiological calculation.** Local branch
`verify/stabilisation`; no GitHub push.

Legend — **Baseline numerics affected?** answered against `baseline_numerics.json` (224 values,
byte-exact) re-checked after every phase.

---

## Phase 0 — Baseline (tooling only)

| Change | Why | Files | Risk | Baseline affected? |
|---|---|---|---|---|
| Add classical-numerics fingerprint + reference | C1 regression guard for all later phases | `scripts/verification/baseline_fingerprint.py`, `baseline_numerics.json` | none (new, read-only over synthetic data) | **No** (defines the reference) |

## Phase 1 — Audit (docs only)

| Change | Why | Files | Risk | Baseline affected? |
|---|---|---|---|---|
| Read-only audit report | Deliverable D2 | `docs/AUDIT.md` | none | **No** |

## Phase 2 — Ingest robustness

| Change | Why | Files | Risk | Baseline affected? |
|---|---|---|---|---|
| **New** deterministic cohort discovery + modality selection with reason codes | Current ingest picks "first-found via `rglob`" (non-deterministic — C5) and **raises** on any missing modality (2.1–2.4). New module groups by PatientID+FrameOfReferenceUID, selects deterministically (APPROVED→latest→SOP tiebreak), degrades with machine-readable reason codes, never raises on one patient. | **new** `engine/dicom_io/cohort_discovery.py` | Low — additive; `DicomPlanReader` left unchanged (backward compat) | **No** (no numerics) |
| **New** dose units/scaling guards | 2.5 — catch cGy-vs-Gy, missing `DoseGridScaling`, non-Gy `DoseUnits`, DVH/grid mean-dose disagreement, as reason codes | **new** `engine/dicom_io/dose_units_check.py` | Low — additive; delegates dose math to dicompylercore | **No** |
| Force UTF-8 console in the engine CLI | Windows `cp1252` crashes on the CLI's Unicode output (σ ✓ — °); affects PowerShell users and any parent capturing stdout (T7). `main()` now reconfigures stdout/stderr to UTF-8 (`errors="replace"`). | `engine/rbgyanx_engine/__main__.py` | Low — I/O only, guarded | **No** |
| Add `encoding="utf-8"` to subprocess test calls | Parent-side of the same cp1252 issue; makes `pytest` (no env var) deterministically green (C5) | `tests/test_integration.py`, `tests/test_ntcp_analysis.py`, `tests/test_tcp_analysis.py`, `engine/tests/test_outputs.py` | Low — test I/O only | **No** |
| **New** synthetic corrupted-input battery (17 tests) | Phase 2 acceptance: no uncaught exception + reason code on every degradation path; determinism proven | **new** `tests/synthetic/test_ingest_robustness.py` | none (tests) | **No** |

**Not changed (deliberately):** `DicomPlanReader.load_patient_dicom/load_cohort` (kept for backward
compatibility; the new discovery module is the robust front-end the Phase-5 runner will use). The
`PatientRegistry` PHI-in-export issue (PrimaryPatientID/DOB/StudyDate/Institution reach
`build_dataframe`) is **flagged** (C2) and will be handled in the Phase-5 output layer, not here.

## Phase 3 — Semantic layer

| Change | Why | Files | Risk | Baseline affected? |
|---|---|---|---|---|
| **New** structure mapping report | 3.1 — report mapped/ambiguous/unmapped per cohort + list unmapped raw names so authors extend the dictionary; every ROI accounted for (never silently discarded) | **new** `engine/dicom_io/structure_mapping_report.py` | Low — additive, wraps `canon_target` | **No** |
| **New** NTCP applicability + definition guard | 3.3 / audit S2 — make explicit that TARGET/SUPPORT never receive NTCP, and flag single-gland-vs-merged-bilateral parameter-definition mismatches (record assumed definition) | **new** `engine/radiobiology/ntcp_applicability.py` | Low — advisory verdict only; no numeric kernel touched | **No** |
| Curated alias expansion | 3.1 — PRV/laterality/abbreviation/synonym variants; **deliberately excludes** bilateral→single-sided mappings so the definition guard can flag merged contours | `engine/config/structure_aliases.py` (append-merge) | Low — only adds recognitions; "Parotids" stays UNKNOWN by design | **No** (synthetic fingerprint uses explicit names) |
| **New** semantic-layer tests (23) | Phase 3 acceptance | **new** `tests/synthetic/test_semantic_layer.py` | none | **No** |

**Verified unchanged (already correct):** `site_detector.detect_site` returns UNKNOWN/LOW with an
`evidence` list on ambiguity and detects all 7 sites (HN/lung/brain/breast/prostate/pelvis/liver); the
pipeline already applies NTCP only via `get_oar_structures` (targets structurally excluded).

## Phase 4 — Computation layer (verify; change only what's provably broken)

| Change | Why | Files | Risk | Baseline affected? |
|---|---|---|---|---|
| Record NTCP parameter provenance in the run manifest | 4.3 — `provenance.json` did not say which NTCP parameter set(s) were applied; now lists the distinct `site_params_key`s used | `engine/rbgyanx_engine/engine.py` (`_write_provenance`) | Low — writes an extra JSON field; no numeric path | **No** |
| **New** computation-layer verification locks | Lock 4.3 provenance + re-affirm 4.1 reject-not-repair and 4.2 NaN-not-zero | **new** `tests/synthetic/test_computation_provenance.py` (4 tests) | none | **No** |

**Verified unchanged (already correct — no code change):**
- **4.1 DVH integrity**: `dvh_integrity.validate_cumulative_dvh` rejects (raises) inverted/rising/negative/
  non-finite/empty DVHs — never repairs — and sorts valid ones. Wired into the TPS text reader; DICOM DVHs
  are monotone by dicompylercore construction. Zero-volume/empty → NaN or a controlled raise, never a crash
  (`tests/test_dvh_integrity.py`, `tests/test_edge_cases_hardening.py`).
- **4.2 Physical metrics / NaN**: `compute_dose_metrics` guards NaN on integral dose, CI, GI, Dmean/Dmax;
  gEUD/EQD2/NTCP return NaN (not 0) on degenerate input (`test_edge_cases_hardening.py`). The only `or 0.0`
  sites are missing-prescription **plan-metadata** defaults, not computed-metric coercion.
- **4.3 provenance**: NTCP output rows already carry `site_params_key`; `params_source` on `SiteNTCPParams`.
- **4.4 dosiomics / ML / XAI**: import + run green (`test_dosiomics.py`, `test_xai.py`).
- **4.5 PINN**: registry/stub load + training e2e green (`test_pinn_registry.py`, `test_train_pinn.py`).
  Training is **already gated** — default mode is `basic` (no advanced path); advanced only registers a
  PINN stub / loads a checkpoint; heavy training runs only when `pinn_train=True`. Torch is CPU-only, so
  GPU training is inert by construction. **PINN not deleted, not altered.**
- **4.6 Bayesian**: import + execution green (`test_bayesian_ntcp.py`), graceful fallback. Not deleted.
