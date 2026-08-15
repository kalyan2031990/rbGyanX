# rbGyanX — Phase 1 Audit (read-only)

Independent engineering audit for manual cohort runs. **No code was changed in this phase.** Findings
are split into **Science** (flagged, not fixed — per constraint C1) and **Tidiness/Engineering**.
"Critical path" = required for a four-cohort run (discover → map → DVH → metrics → TCP/NTCP → write).

Baseline: `main @ b366cbc`; 22/22 positive controls; 769 passed / 3 skipped (`PYTHONUTF8=1`).

---

## 1.2 Module inventory (critical path for a cohort run?)

| Module | Role (one line) | Critical path | Import |
|---|---|:--:|:--:|
| `engine/dicom_io/dicom_reader.py` | Read RT DICOM (CT/STRUCT/DOSE/PLAN) | **Yes** | OK |
| `engine/dicom_io/patient_registry.py` | Group instances into patients/studies | **Yes** | OK |
| `engine/dicom_io/dvh_extractor.py` | Extract/compute DVH from dose+struct | **Yes** | OK |
| `engine/dicom_io/dvh_integrity.py` | Validate cumulative DVH (monotone/finite) | **Yes** | OK |
| `engine/dicom_io/txt_dvh_reader.py` | Parse TPS text DVH exports (parotid/SPARK) | **Yes** | OK |
| `engine/dicom_io/structure_mapper.py` | ROI raw-name → canonical (TG-263-ish) | **Yes** | OK |
| `engine/dicom_io/site_detector.py` | Infer treatment site from structures | **Yes** | OK |
| `engine/dicom_io/cohort_features.py` | Per-patient feature table builder | **Yes** | OK |
| `engine/dicom_io/dvh_shape_features.py` | DVH shape descriptors (dosiomics-lite) | Advanced | OK |
| `engine/dicom_io/input_validation.py` | Input QA gates | **Yes** | OK |
| `engine/dicom_io/tcia_hnscc_adapter.py` | TCIA HNSCC collection adapter | **Yes** (TCIA) | OK |
| `engine/radiobiology/geud_tcp.py` | gEUD + gEUD-TCP | **Yes** | OK |
| `engine/radiobiology/bdvh.py` | EQD2/BED DVH transforms | **Yes** | OK |
| `engine/radiobiology/lq_model.py` | LQ EQD2/BED primitives | **Yes** | OK |
| `engine/radiobiology/poisson_tcp.py` · `zaider_minerbo.py` · `logistic_tcp.py` | TCP models | **Yes** | OK |
| `engine/radiobiology/tcp_calculator.py` | TCP orchestration over models | **Yes** | OK |
| `engine/radiobiology/ntcp/{lkb_loglogit,lkb_probit,rs_poisson}.py` | NTCP models | **Yes** | OK |
| `engine/radiobiology/ntcp_calculator.py` | NTCP orchestration | **Yes** | OK |
| `engine/radiobiology/utcp.py` | Uncomplicated-TCP composite (P+) | **Yes** | OK |
| `engine/uncertainty/parameter_mc.py` · `ntcp_mc.py` | MC uTCP/uNTCP | Advanced | OK |
| `engine/uncertainty/inverse_variance_consensus.py` · `utcp_consensus.py` | Consensus combiner | Advanced | OK |
| `engine/uncertainty/{dosimetric_uncertainty,setup_error,hypoxia}.py` | Extra uncertainty terms | Advanced | OK |
| `engine/ml_models/{xgboost,lgbm,random_forest}_tcp.py`, `model_manager.py` | ML predictors | Advanced (ADVANCED) | OK |
| `engine/xai/{shap_tcp,lime_tcp,pdp_ice}.py` | Explainability | Advanced (ADVANCED) | OK |
| `engine/validation/outcome_pinn.py` | PINN outcome model (in-engine) | Advanced (ADVANCED) | OK |
| `engine_advanced/rbgyanx_advanced/pinn/**` | PINN training/models (torch) | Advanced (ADVANCED) | OK (CPU) |
| `engine_advanced/rbgyanx_advanced/dose3d/dosiomics.py` | First-order dose features (real RTDOSE only) | Advanced (ADVANCED) | OK |
| `analysis/dosiomics/real_dosiomics.py` | Reported 3-D texture dosiomics (GLCM/GLRLM/GLSZM) | Analysis | OK |
| `engine_advanced_f/rbgyanx_advanced_f/bayesian/ntcp_bayesian.py` | Bayesian NTCP | Advanced (ADVANCED) | OK |
| `engine_advanced_f/rbgyanx_advanced_f/pinn/train_pinn.py` | PINN trainer (alt) | Advanced (ADVANCED) | OK |
| `engine/outputs/ntcp_reporter.py` | Report/export writer | **Yes** | OK |
| `engine/rbgyanx_engine/{pipeline,engine,physical_dose,run_config}.py` | Engine CLI + pipeline | **Yes** | OK |

**All optional/ADVANCED stacks import cleanly** (PINN ×3 locations, Bayesian, XAI, dosiomics, ML) — no
broken imports, nothing needs gating for import-failure (C3 satisfied at import level). PINN GPU path is
inert because torch is CPU-only (Phase 4.5 will gate execution, not delete).

---

## 1.1 Structural findings (tidiness / engineering — not science)

**T1 — Multiple cohort-run entry points that overlap (Phase 5 consolidation target).**
`python -m rbgyanx_engine` (single DVH dir) · `external_validation/run_hnscc_validation.py`,
`run_benchmark.py`, `run_phase4_analysis.py` · `scripts/run_ntcp_benchmark_workspace.py`,
`scripts/build_parotid_cohort_workspace.py`, `scripts/run_validation_report.py`. No single
"one command per cohort" entry with the resumable/idempotent contract Phase 5 requires. *Impact:* the
authors currently have no uniform way to run all four cohorts. *Plan:* add one wrapper in Phase 5;
do **not** delete the existing runners.

**T2 — Two `pipeline.py` + a `run_controller`.** `engine/rbgyanx_engine/pipeline.py` (headless engine
pipeline) vs `rbgyanx/logic/pipeline.py` + `rbgyanx/services/run_controller.py` (GUI/service
orchestration). Not a bug, but two orchestration layers; the cohort runner should target the engine one.

**T3 — Duplicate TCP implementation.** `engine/radiobiology/{poisson_tcp,logistic_tcp,geud_tcp}.py`
(validated, critical path, NaN contract) **and** `rbgyanx/core/tcp/{poisson,logistic,eud,lkb}.py`
(second implementation). The `core/tcp` copy is imported **only by itself** — not on the cohort path —
so it is effectively parallel/legacy. See **S1** for the science angle. NTCP is *not* duplicated:
`rbgyanx/core/ntcp/*` are thin re-exports of `radiobiology.ntcp.*` (single-sourced ✓).

**T4 — `legacy/` quarantine (9 files: `code1`–`code7`, two QA suites).** Provenance scripts; superseded
by the engine. Keep (C3), but they are dead relative to the current pipeline — documented so the authors
don't mistake them for the live path.

**T5 — Working-tree debris (pre-existing; not introduced here).** Untracked `temp_check_values.py`,
`temp_find_columns.py`, `temp_grade_summary.py`, `temp_inspect_csv.py`, `temp_output/`,
`dicom_search.txt`, `hnscc_contents.txt`, `hnscc_inventory.txt`, several untracked `scripts/…`
(`audit_spark_dataset.py`, `build_parotid_cohort_workspace.py`, `cohort_builder/`, `dvh_builder/`,
`run_ntcp_benchmark_workspace.py`), and modified `docs/rbgyanx_user_manual.html`. *Recommendation:*
gitignore `temp_*`/`temp_output/` and either commit or remove the untracked scripts — **left for author
decision; not touched.**

**T6 — Broken imports / cyclic deps:** none found. `rbgyanx_engine.pipeline`, `rbgyanx_engine.engine`,
and every optional stack import without error. No import cycles surfaced on load.

**T7 — Windows console encoding (from Phase 0).** Four subprocess tests decode CLI output as cp1252;
the engine CLI emits Unicode. Robustness bug for PowerShell users. *Plan:* fix at source in Phase 2/5.

---

## 1.3 SCIENCE flags (reported only — not fixed in this task)

**S1 — Divergent degenerate-value contract between the two TCP implementations.**
`engine/radiobiology` TCP/NTCP return **NaN** on degenerate input (documented NaN contract, and the
positive controls depend on it). `rbgyanx/core/tcp/{eud,lkb,logistic,poisson}.py` return **0.0** on the
same degenerate branches (≈14 `return 0.0` sites). The existing release `VERIFICATION_REPORT.md` even
notes this ("still return 0.0 in `rbgyanx/core`"). *Why it matters:* a TCP of exactly 0.0 vs NaN changes
downstream P+ and any averaging (NaN must never silently become 0 — constraint C4.2). *Current exposure:*
LOW — `core/tcp` is off the cohort critical path (self-imports only). *Action:* flagged for the authors;
**not changed** here because it touches a validated calculation. If `core/tcp` is truly unused it can be
retired later; if the GUI uses it dynamically, its contract should be reconciled to NaN.

**S2 — NTCP-on-target and parameter-definition matching (to VERIFY in Phase 3, not yet a defect).**
The semantic guard that (a) a TARGET never receives an NTCP and (b) an NTCP model is only applied to a
structure whose definition matches its published parameters (e.g. single-gland vs merged bilateral
parotid) must be confirmed to exist on the cohort path. Recorded here as a Phase-3 verification item; no
claim of a defect yet.

**Scope honesty:** this audit did **not** perform a line-by-line numerical re-derivation of each
radiobiological model. The guardrails against silent numeric change are the 22 positive controls and
`baseline_numerics.json` (224 values, byte-exact), re-checked after every later phase. Any model-level
correctness concern beyond S1/S2 is therefore *not asserted* — absence of a flag here is not a proof of
correctness, only that nothing obviously wrong was seen at the interface level.

---

## Phase-forward implications

- **Phase 2:** ingest robustness + the cp1252 fix (T7) — highest leverage for "do cohorts run at all".
- **Phase 3:** expand `structure_mapper` (239 lines today), harden `site_detector` (375 lines), and
  establish the S2 target/definition guards with explicit UNKNOWN paths.
- **Phase 4:** verify DVH integrity + physical metrics + TCP/NTCP against `baseline_numerics.json`;
  reconcile S1 only if provably safe, else leave and document.
- **Phase 5:** one resumable/idempotent command per cohort (T1/T2) with the mandated output tree.
