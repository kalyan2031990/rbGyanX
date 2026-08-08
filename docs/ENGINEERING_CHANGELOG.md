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

## Phase 5 — Run system

| Change | Why | Files | Risk | Baseline affected? |
|---|---|---|---|---|
| **New** cohort runner | 5.1–5.7 — one resumable, idempotent, deterministic, pseudonymised command per cohort; mandated tree; 16 always-written CSVs; run manifest; per-patient logs; cohort summary. Wraps `run_analysis` per patient (numerics unchanged). | **new** `engine/rbgyanx_engine/cohort_runner.py` | Medium — new orchestration, but reuses the validated per-patient engine; no numeric kernel touched | **No** |
| **New** PowerShell launcher | one-command entry that needs no editable install | **new** `scripts/run_cohort.py` | none | **No** |
| Gitignore cohort outputs + pseudonym maps | C2 — the `Outputs/` tree and `*_pseudonym_map.csv` are PHI-adjacent and must never be committed | `.gitignore` | none | **No** |
| **New** cohort-runner acceptance tests (5) | Phase 5 acceptance: determinism, idempotency, 16 CSVs, degraded DICOM, PHI-free tree | **new** `tests/synthetic/test_cohort_runner.py` | none | **No** |
| **New** runbook | D5 — copy-pasteable PowerShell per cohort | **new** `docs/RUNBOOK.md` | none | **No** |

**C2 handling (the flagged `PatientRegistry` PHI-in-export issue):** the cohort runner never uses the
PHI-bearing registry columns. It pseudonymises every patient (`<COHORT>-NNNN`), holds the raw-ID↔pseudonym
map **outside** the output tree (`--pseudonym-map-dir`, gitignored), runs the engine into a **temp** dir
with its **console output suppressed**, PHI-strips every harvested row (drops PatientID/DOB/StudyDate/
Institution/AnonPatientID/…), and writes only pseudonymised rows. A test scans the whole tree and asserts
no raw token leaks.

## Phase 6 — Staged real-data testing (fixes found by real cohorts)

All changes are **opt-in** (default behaviour byte-identical) unless stated. `baseline_numerics.json`
re-verified after each.

| Change | Why (found on real data) | Files | Risk | Baseline affected? |
|---|---|---|---|---|
| Expose `preserve_canonical` on the TPS-text reader + plumb through `RunConfig`/pipeline | **Blocker.** Single-structure TPS exports were always coerced to a target type, so an OAR export (54 parotid files) became a "PTV": it received meaningless TCP and **NTCP could never be computed** (organ lookup for a canonical named "PTV" always fails). Matches the authors' own documented gap. | `engine/dicom_io/txt_dvh_reader.py`, `engine/rbgyanx_engine/{run_config,pipeline,engine}.py` | Low — default `False` keeps legacy path exactly | **No** |
| Multi-structure TPS parsing (`_read_txt_structures`) | **Blocker.** SPARK plan-level exports hold ~6 ROIs per file; the single-structure reader returned **only the last one**, silently discarding PTV/CTV/Bladder/Rectum. The correct multi-structure reader existed but was never called. | `engine/rbgyanx_engine/pipeline.py` | Low — only under `preserve_canonical` | **No** |
| OAR-never-receives-TCP guard | Mirror of the TARGET-never-receives-NTCP rule; a parotid gland was being given tumour-control probability | `engine/rbgyanx_engine/pipeline.py` | Low — only under `preserve_canonical` | **No** |
| Record ROI `raw_name` on NTCP/TCP rows | Lets the definition guard see the ROI's original name | `engine/rbgyanx_engine/pipeline.py` | none (extra column) | **No** |
| Laterality is evidence only when in the ROI's own name | A side-less `Parotid` silently canonicalises to `Parotid_R`; treating that inferred side as "verified single gland" hid the hazard. Now yields `NTCP_DEFINITION_UNVERIFIED`. | `engine/radiobiology/ntcp_applicability.py` | Low — advisory flag only | **No** |
| Folder-qualified patient keys | **Data-corrupting bug.** SPARK restarts numbering per centre, so `Center 1/Pat01` and `Center 4/Pat01` (different people) were merged into one patient. | `engine/rbgyanx_engine/cohort_runner.py` | none | **No** |
| Suppress the engine's **logging tree** during patient runs | The pipeline logs the source-header patient id on MC/uNTCP failure; logging handlers bypass `redirect_stdout/stderr` (C2 leak path) | `engine/rbgyanx_engine/cohort_runner.py` | none | **No** |
| Log exception **type** only, never the message | Exception messages can quote source paths/content (C2) | `engine/rbgyanx_engine/cohort_runner.py` | none | **No** |
| Automatic post-run PHI scan | C2 "grep your own outputs before declaring done": harvests real identifier values from source headers (memory only) and asserts none appear in any output; writes `QA/phi_scan.json` | `engine/rbgyanx_engine/cohort_runner.py` | none | **No** |
| `NO_STRUCT` is a documented reduced mode, not a failure | TCIA Lung has plan+dose but no contours; DVH is impossible, so it is a skip with a reason code | `engine/rbgyanx_engine/cohort_runner.py` | none | **No** |
| `--file-pattern`, `--preserve-structure-canonical` CLI flags | Select a study arm (SPARK with/without KIM) and enable OAR-aware TPS parsing | `engine/rbgyanx_engine/cohort_runner.py` | none | **No** |
| **New** run-report generator | Per-cohort `RUN_REPORT.md` from pseudonymised outputs only | **new** `scripts/make_run_report.py` | none | **No** |
