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
