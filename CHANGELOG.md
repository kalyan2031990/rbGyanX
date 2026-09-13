# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-09-13 — minor: three documented behaviours changed

A **minor** release, not a patch. Three behaviours that the documentation described are now
different, and code written against the old ones will break. No scientific result changed, no
analysis was rerun, and the release identifier stays FINAL_V3.2.

This release is independent of any publication. It is a software release: the defects below were
found by auditing the tool on its own terms, and the fixes stand on their own. A paper may cite
rbGyanX; rbGyanX does not exist to serve one. `CITATION.cff` accordingly sets no
`preferred-citation`, so a citation of this tool credits the tool.

### Changed / Breaking

- **Suspected PHI bound for a remote AI provider is now BLOCKED, not warned about.**
  `LLMClient.complete` scanned every outgoing message, attached the findings to the response as a
  warning, and then transmitted anyway — the code was annotated `# warn, do not block`. Meanwhile
  `README.md` and `DISCLAIMER.md` told the reader that remote providers "never receive patient
  data". The documentation described the behaviour the guard should have had, so the guard changed
  rather than the sentence.

  A finding on a payload bound for a remote provider now raises
  `rbgyanx.ai.llm_client.PhiBlocked` **before the transport is constructed**. There is no
  override: no parameter, no environment variable, no config field, and no "send anyway" button in
  the Qt panel. Local (loopback) providers are unaffected and still only warn, because nothing
  leaves the machine. Refusals are recorded in the audit log with `outcome="refused"` and no
  payload digest.

  *Migration:* a caller that relied on a warn-and-send remote path must now catch `PhiBlocked`,
  remove the identifiers, or select a local provider. `LLMResponse.had_phi_warning` still reports
  findings for local sends.

  The guard also now scans **every role, system messages included**. Run-derived context is
  attached to the conversation as a system message, and the old scan filtered that role out —
  exempting precisely the part of the payload derived from patient data. `rbgyanx/ai/context.py`
  claimed "the PHI guard still runs on the final text"; for that path it did not.

- **A site whose TCP parameters are missing or technique-specific now raises instead of silently
  substituting a near match.** `load_site_params("LUNG_SBRT")` returned the conventional `LUNG`
  parameter object, so a caller asking for SBRT parameters received conventional-fractionation
  ones with nothing saying so. It now resolves to its own entry, and
  `dicom_io.site_detector.params_site_key` no longer folds the key into `LUNG` either.

  `PELVIS` is declared as having no TCP parameter set and raises the new
  `SiteParamsUnavailable` (a `ValueError` subclass) explaining that a pelvic volume is
  multi-target and needs a named target site. It previously failed with
  `Site 'PELVIS' not found in SITE_PARAMS` — an internal detail rather than an answer, and
  reachable from real data, since the detector maps `PELVIS`, `CERVIX` and `ENDOMETRIUM` onto it.

  *Migration:* callers that passed `LUNG_SBRT` and expected `LUNG` values now get an object whose
  `site` field says `LUNG_SBRT`. Those values are still the conventional numbers — no
  SBRT-specific lung parameter set has been adopted and none was invented — but the object now
  declares that in `notes`. Callers that passed `PELVIS` must handle `SiteParamsUnavailable`.

- **The expression calculator no longer evaluates user input with `eval()`.**
  `ask_rbgyanx/calculator.py` called `eval(expression, {"__builtins__": {}}, {"math": math})`
  behind a blocklist of six substrings, and its accompanying character check was inert — every
  branch of that loop ended in `continue`, so it rejected nothing. Replaced with an `ast` walk
  over an explicit allow-list of node types, operators, functions and constants, plus caps on
  exponent magnitude, factorial input and expression length. Anything not on the list is refused
  by name.

  *Migration:* expressions outside the allow-list now fail with
  `UnsafeExpressionError` (a `ValueError` subclass) reported through the existing
  `{'success': False, 'error': ...}` contract. Attribute access, comprehensions, lambdas and
  non-numeric literals were never intended to work and now say so.

### Fixed

- **The documented pipeline entry point raised on its first call.**
  `rbgyanx.logic.pipeline.run_analysis_pipeline` raised `UnboundLocalError` in its default BASIC
  configuration: the BASIC block logged each conservative default through `structured_logger`, but
  the provenance tracker and structured logger were both initialised *after* that block. BASIC is
  the default, so the very first call failed. Initialisation now precedes use.

  A second defect sat on the same path. The loop copying applicability warnings onto the output
  dereferenced `applicability_result` unconditionally — that object is only built when
  `inputs.treatment_info` is supplied — and had been indented into the preceding
  `if provenance_tracker:` block, so disabling provenance silently discarded user-facing
  applicability warnings. Now guarded and de-indented.

  Note that this function still cannot execute its subprocess steps, because `code1`–`code7` live
  in quarantined `legacy/`. It returns `status='partial'` rather than raising. Use
  `rbgyanx.services.run_controller.RunController`, which is the supported entry point and what
  both GUIs call. See `docs/KNOWN_LIMITATIONS.md`.

- **`PROSTATE_SBRT` parameters were unreachable.** They existed in
  `engine/config/site_params_default.yaml` and differ materially from conventional prostate
  (TCD50 36.25 Gy vs 72.0), but the key was absent from `_SITE_KEY_MAP` and so was rejected as an
  unknown site. It now loads.

- **Two error handlers crashed instead of reporting.** In `rbgyanx_gui.py`, handlers for the
  assistant and the self-test closed over `e` from `except Exception as e:` and were invoked later
  through Tk's `after()`/`lambda`. Python deletes the exception name when the block ends, so both
  raised `NameError` at the moment they were meant to report a failure — losing the original error
  and replacing it with a confusing one. The message is now bound at raise time.

- **`CITATION.cff` and `README.md` cited a version DOI.** Both now cite the concept DOI
  `10.5281/zenodo.21757163`, which always resolves to the newest release, instead of
  `10.5281/zenodo.21757164`, which pinned readers to v1.2.1.

- **The published wheel could not be imported.** `rbgyanx/__init__.py` imports `rbgyanx_engine` at
  module scope, but `rbgyanx-engine` was not declared as a dependency — so
  `pip install rbgyanx-1.2.1-py3-none-any.whl` succeeded and `import rbgyanx` then raised
  `ModuleNotFoundError`. The dependency is now declared, which turns that into an install-time
  resolution error with a clear message, and the engine wheel ships alongside.

- **`utils/shap_utils.py`: the advertised workflow was broken and leaked figures.** `to_matrix`
  only handled the pre-0.45 list-of-two-arrays form, so under shap 0.45+ a binary tree model
  returned a 3-D array unreduced and `generate_shap_caption` raised `TypeError` — breaking the
  documented `safe_shap_values -> to_matrix -> generate_shap_caption` chain for XGBoost and
  RandomForest. Separately, both plotting helpers leaked exactly one matplotlib figure per call.

- **Bare `except:` in 22 places** swallowed `KeyboardInterrupt` and `SystemExit`; now
  `except Exception:`. **Ten re-raises** inside except blocks lost their cause; now chained.
  **Seven `zip()` call sites** that must pair equal-length sequences — including
  `zip(feature_names, feature_importances)`, where truncation would mislabel importances — now
  pass `strict=True` and raise rather than truncating silently.

- **A missing optional dependency no longer fails the whole test suite.**
  `tests/test_gui_integration.py` imported `tkinter` unguarded at module scope, and
  `rbgyanx.qtapp.is_available()` checked only that the PySide6 *package* was findable rather than
  that Qt could load. Either combination turned a should-be-skipped module into a *collection*
  error. Both now guard on the real import.

### Security

- **`HttpTransport` passed a user-configurable `base_url` straight to `urllib.request.urlopen`,**
  which also honours `file:`, `ftp:` and `data:`. A preset pointed at `file:///etc/passwd` would
  have turned the AI panel into a local-file reader. The scheme is now checked against an
  http/https allow-list before any request is built.

- **`setuptools>=83`** is now the build floor, closing PYSEC-2026-3447.

- `pydicom` remains pinned `>=2.4,<3.0` and so carries **PYSEC-2026-2266**, a path traversal in
  the `FileSet`/DICOMDIR API. The pin cannot be lifted: `dicompyler-core` 0.5.6 — the latest
  release — imports `pydicom.pixel_data_handlers`, removed in pydicom 3.0, and installing 3.0.2
  makes `import dicompylercore.dicomparser` fail outright. This codebase never touches the
  vulnerable API, so exposure is nil rather than merely unlikely. Accepted as a documented
  `pip-audit` exception; `SECURITY.md` states the justification and what would invalidate it.

### Infrastructure

- **Bandit and pip-audit are blocking gates.** Both previously ended in `|| true`, so the build
  went green whether or not they passed — and both were in fact failing when that mask was
  removed. Every finding is now fixed or recorded in `SECURITY.md` with a reason. `B602`
  (`shell=True`) is deliberately not skipped.

- **Ruff lints the whole maintained tree.** It previously ran over nine named paths, so a green
  check said nothing about the other ~140 files — which is where the two undefined-name bugs
  above were hiding. 1,561 findings went to zero; remaining exclusions are policy with stated
  reasons in `pyproject.toml`, not backlog.

- **The release workflow builds real artefacts.** It previously built nothing: the installer step
  printed "skipping in CI unless secrets configured" and the only uploaded artifact was
  `CHANGELOG.md`. It now builds wheels and sdists for both distributions, freezes and compiles the
  Windows installer, and **asserts that every artefact filename carries the tag's version**.
  `packaging/build_installer.ps1` had `$AppVersion` hardcoded to `"1.0.0"`, which is why a release
  could ship an asset named after the wrong version; it now reads the version from the single
  source of truth. A clean-install smoke test installs both wheels into a fresh venv and runs the
  README quickstart.

- **`analysis/` is excluded from linting and formatting.** Its scripts are pinned by SHA-256 in
  `FINAL_ANALYSIS_CODE_MANIFEST.json`, so reformatting them breaks the mapping between a reported
  number and the bytes that produced it. It is a frozen provenance artefact, not maintained code.

### Added

- `tests/test_ai_phi_failclosed.py` — asserts against a transport that records every call that a
  flagged payload never reaches it. The exception alone would pass even if the request had already
  gone out.
- `engine/tests/test_site_params_routing.py` — pins the invariant that every mapped site either
  loads as itself or raises, which is what makes all three routing defects unreintroducible.
- `tests/test_ask_rbgyanx_calculator.py` — correctness for the advertised functions, and 18
  refusal payloads.
- `tests/test_shap_workflow.py` — previously a zero-byte file. Populated rather than deleted,
  because `utils/shap_utils.py` ships in the wheel and had no tests; writing them found the two
  bugs above.
- `tests/test_pipeline_entry_point.py` — calls `run_analysis_pipeline` with default arguments.
- `scripts/check_release_version.py` — gates a release on tag/code version agreement.

### Documentation

- `README.md` rewritten for a first-time reader, with an explicit **What this is not for**
  section. Its example output is now the captured output of a real run rather than illustrative
  figures.
- `docs/KNOWN_LIMITATIONS.md` gains five entries and corrects one that had become false. Among
  them: **eight of the 23 scripts recorded in `FINAL_ANALYSIS_CODE_MANIFEST.json` no longer match
  their recorded SHA-256.** The drift predates this release — the files are byte-identical to
  their state at the v1.2.1 tag — and is recorded rather than repaired, because the honest
  repairs are authorial decisions, not cleanup.
- `docs/AI_ASSISTANT_DESIGN.md` no longer describes the PHI guard as "warns, never blocks".

---

## [1.2.1] - 2026-08-22 — patch: the write tool did not run on any supported Python

A patch over 1.2.0. **Anyone on 1.2.0 who enables the assistant's tools should update.** No
scientific result changed, no analysis was rerun, and the release identifier stays FINAL_V3.2.

### Fixed

- **`edit_code` raised `TypeError` on first use (affects 1.2.0 only).** The write tool called
  `Path.read_text(newline=...)` and `Path.write_text(newline=...)`. That keyword was added in
  **Python 3.13**, and this project supports **3.10, 3.11 and 3.12** — so the tool failed on
  every supported interpreter, with:

  ```
  TypeError: Path.read_text() got an unexpected keyword argument 'newline'
  ```

  It surfaced the moment a user enabled assistant tools and accepted an edit. It went unnoticed
  locally because the development machine ran Python 3.14, where the keyword exists; the CI
  matrix caught it. Now uses the builtin `open(..., newline=...)`, which has always accepted it,
  verified under 3.10 to preserve bytes with no newline translation.

- **A Windows-style path evaluated on Linux could be classified as inside the install tree.** On
  POSIX a backslash is an ordinary character, so `C:\Data\...` resolves to a *relative* name
  under the working directory, which can fall inside the tree — where a data path would be
  reported as though it were rbGyanX's own source. No identifier was leaked, because the
  deny-list redacted it as a Windows path immediately afterwards, but the frame reconstruction
  was wrong. Foreign-convention paths are now treated as external, scoped to non-Windows
  platforms so that a drive letter on Windows still describes our own tree correctly.

### Changed

- **`requires-python` narrowed from `>=3.10` to `>=3.10,<3.13`.** The open-ended bound promised
  support for 3.13 and 3.14, which CI does not test and which the README badge never claimed.
  The `edit_code` defect above is exactly what that gap hides: code that works on a newer
  interpreter and fails on every version actually supported. The declared range now matches the
  CI matrix and the badge.

  **Consequence:** installing on Python 3.13+ is now refused rather than silently untested. If
  you need a newer interpreter, add it to the CI matrix first.

### Tests

1289 → 1326 collected. `tests/test_ai_portability.py` is new: it scans the AI modules for
pathlib keywords newer than the supported floor, pins that floor against `pyproject.toml`, and
asserts foreign-convention paths are external on every platform — so this class of defect fails
on a developer's machine rather than waiting for CI.

### Note on 1.2.0

The `v1.2.0` tag is left in place and unmodified. It is superseded, not withdrawn.

## [1.2.0] - 2026-08-22 — governed AI assistant

Adds an optional, governed AI assistant and fixes a data-locality defect present in earlier
versions. **No scientific result changed**: no analysis was rerun, no reported number altered,
and the release identifier stays FINAL_V3.2 because the analysis programme is the same generation
1.1.0 froze. The assistant explains outputs the deterministic engine has already produced — it
never computes, adjusts or influences a TCP, NTCP or UTCP value, and no code path leads from it
into the numeric core.

### Security

- **`AiConfig.is_remote` ignored `base_url` (affects 1.0.0 and 1.1.0).** A provider preset
  flagged local — the "Local (Ollama / llama.cpp)" preset — could be pointed at any URL, and
  `is_remote` still reported it as local because it read only the preset's declarative flag. The
  send-confirmation dialog reads that property, so the dialog told the user their data was
  staying on the machine while it left over the network. It is the one place a person looks for
  that reassurance, so it is the one place it must not be wrong.

  `is_remote` now requires both the local flag **and** a resolved loopback URL
  (`localhost`, `127.0.0.0/8`, `::1`); anything else is treated as remote. A LAN endpoint counts
  as remote, which is correct — the data does leave the machine.

  **Who is affected:** anyone on 1.0.0 or 1.1.0 who changed the Local preset's base URL. The
  default configuration was never affected, because it points at localhost. There is no evidence
  of exposure in the shipped defaults; the defect was in what the interface *claimed*, and in
  what would have happened had the URL been changed.

### Added

- **Capability matrix** (`rbgyanx/ai/capability.py`): a 9x5 table enforced in code, granting
  capability on two axes — data locality (local vs remote provider) and install type (source,
  frozen binary, CI). Remote providers never receive patient data, under any capability, in any
  install type. All 45 cells are asserted individually.
- **Institutional kill switch**: `RBGYANX_AI_DISABLE_REMOTE=1`, or `ai.disable_remote: true` in a
  site config file, removes every remote provider from the registry before anything else sees it.
  It cannot be re-enabled from the interface.
- **Fail-closed PHI scrubber** (`rbgyanx/ai/scrubber.py`) for machine-generated text the assistant
  forwards on the user's behalf. An unconfident scrub is a refusal, never a smaller payload.
  Tracebacks are reconstructed against known-safe roots rather than redacted. `phi_guard` keeps
  its existing warn-never-block contract for text the user typed themselves.
- **Site-declared structure labels** (`RBGYANX_STRUCTURE_LABELS`) so departments naming structures
  in German, Spanish, Japanese or Russian are not refused constantly — a safety control that fires
  constantly gets switched off.
- **Frozen set**: the assistant can never modify the numeric core, its inputs, the tests that
  verify it, the test configuration, or its own guards. Creation of auto-loaded files that would
  re-open the boundary (`sitecustomize.py`, `.pth`, `conftest.py`, shadowing packages) is refused.
- **Verify/auto-revert loop** around every accepted edit: snapshot file bytes, apply, run the
  analytic positive controls, run the full suite, and restore automatically on any failure.
- **Literature quick-compare** with provenance tiers and an **export gate**. Any export containing
  an unverified row carries an orientation notice, keeps the rows marked, and refuses to drop the
  provenance column.
- **Reference packs** (`rbgyanx/ai/reference_packs/`), versioned and site-extensible. The shipped
  QUANTEC pack is marked `pending: not verified against primary sources` and its entries are
  export-gated until a reviewer clears them.
- **Append-only audit log** in the user's config directory, recording one PHI-free record per
  transmission and per guard refusal, plus `scripts/export_ai_audit.py` to export it as CSV with
  a summary.
- **Kimi K3 support**: `kimi-k3`, the `reasoning_effort` field (`low`/`high`/`max`, default
  `max`), and preserved thinking history — the complete assistant message, including
  `reasoning_content` and `tool_calls`, is replayed verbatim into the next turn.
- **`docs/AI_ASSISTANT_DESIGN.md`** (capability matrix, threat model, frozen set) and
  **`docs/RUNNING_WITH_A_REMOTE_PROVIDER.md`** (what is granted and denied on a remote provider).
- **Opt-in live-provider smoke test** (`RBGYANX_LIVE_LLM_TEST=1`) covering the wiring that mocked
  transports cannot.

### Changed

- The AI panel shows the active provider, install type and granted capabilities at all times, and
  builds its provider list from the kill-switch-filtered registry so a disabled provider is not
  selectable rather than refused after selection.
- The assistant tool layer is **opt-in and off by default**, ADVANCED-only, absent in BASIC.
- `pyproject.toml` declares `package-data` so the reference packs ship in a wheel.

### Tests

834 -> 1269 collected. The suite remains green with no test weakened, skipped or rewritten to
accommodate the new work.

## [1.1.0] - 2026-08-15 — release identifier FINAL_V3.2

Release-repair and freeze. **No scientific result changed**: every headline value was independently
recomputed and matched before this release was built, and nothing was rerun to produce it. Four
release blockers from the final completion audit are closed.

### Added

- **`analysis/` — the code that produced the reported results is now versioned** (blocker B1).
  Eleven analyses across `cohort/`, `radiomics/`, `ibsi/`, `dosiomics/`, `pinn/`, `bayesian/`,
  `ccs/`, `statistics/` and `provenance/`. `analysis/FINAL_ANALYSIS_CODE_MANIFEST.json` maps each
  headline result to its exact script (path + SHA-256 + line count), configuration, input and output
  manifests, random seed, package versions and source commit. Previously the engine was versioned
  but the analysis layer was not, so no commit described how the reported numbers were computed.
- `docs/DOSIOMICS_DATA_PROVENANCE.md` — the real-production-dosiomics vs synthetic-test-data
  distinction, stated explicitly.
- `engine_advanced/tests/test_dosiomics_production_safety.py` — 11 regression tests proving both
  halves of the guard: a missing real dose yields no production dosiomics, and explicit test mode
  still exercises the pipeline.

### Changed

- **Synthetic dose voxels can no longer enter a production dosiomics pathway** (blocker B2).
  `extract_oar_dose_volume()` previously ended in an unconditional
  `return synthetic_oar_dose_voxels(...)`, and the only production caller invoked it with no RTDOSE
  path at all — so every ADVANCED run populated `dosio_*` columns from generated voxels. Those
  surrogates were retracted and underlie no reported result. Now:
  - real RTDOSE is the only production source, resolved by `integration.find_rt_files()`;
  - with no real grid the extractor returns `(None, "NOT_AVAILABLE")` and logs loudly;
  - synthetic output requires an explicit `allow_synthetic=True` that no production path passes;
  - `assert_production_dose_source()` raises `SyntheticDoseInProductionError` for any other source,
    and an omitted `dose_source` is treated as `NOT_AVAILABLE` rather than trusted;
  - NTCP rows carry `dosiomics_status` / `dosiomics_source`, and a patient without a real grid gets
    no `dosio_*` column at all, so a missing measurement is visibly missing.
- `analysis/dosiomics/real_dosiomics.py`: the `--repo` default was an absolute local path; it now
  resolves from the file's own location. Same tree, no behavioural change.
- Version identifiers separated: software semver `1.1.0`, release identifier `FINAL_V3.2`.

### Documentation

- Manuscript B section 3.2: the two `[from manifest]` placeholders resolved to QC_PASSED **219** and
  OUTCOME_LINKED **127**, each cited to its `radiomics_manifest.json` key, with the 219 → 127 drop
  attributed to clinical-data loss rather than imaging QC (blocker B4).
- `docs/AUDIT.md` and `docs/IMPLEMENTATION_ROADMAP.md` corrected: the engine's `dose3d` module
  computes first-order dose features only; the reported 3-D texture dosiomics come from
  `analysis/dosiomics/real_dosiomics.py`.

## [1.0.0] - 2026-08-02

First public, citable release. BASIC (clinic decision-support) and ADVANCED (research)
governance is enforced by the engine; ML/xAI/PINN are ADVANCED-only and experimental.
**Not a regulated medical device.**

### Added

- **PySide6/Qt6 desktop interface** alongside the existing Tkinter app: Workflow, Run
  (live progress), Results (interactive DVH), Visualisation (dose → per-OAR NTCP → P+ Sankey,
  PRISMA-style cohort flow, SHAP/xAI), and an ADVANCED-only, opt-in AI assistant.
- **DVH integrity validator** (`engine/dicom_io/dvh_integrity.py`): every text-DVH ingest is
  sorted by dose and rejected — never silently repaired — if the cumulative curve is inverted,
  non-monotone, duplicated in dose, negative or non-finite. Shipped example DVHs are now a
  positive control for the reader.
- 22 analytic **positive controls** for the corrected NTCP models (`tests/test_ntcp_positive_controls.py`).

### Changed (user-visible behaviour)

- **Relative-seriality NTCP** now complements outside the voxel product
  (`NTCP = 1 − Π_i (1 − P_i^s)^{v_i})^{1/s}`); a prior formulation pinned the value near 1.0.
  Corrected values span a realistic range.
- **Bounded MLE calibration refit**: parameter fits are constrained to physiologic ranges and
  report "not identifiable (flat/degenerate likelihood)" instead of returning extreme values.
- **DVH dose units** are resolved from the file's own declarations (`[Gy]`/`[cGy]`), never guessed
  from magnitude, removing a 100× mis-scaling class of error.
- **NTCP is refused on target volumes.** A PTV/CTV/GTV/ITV/BOOST now returns an explicit
  "not applicable" instead of an NTCP computed from a fallback organ's parameters, and targets are
  excluded from the uncomplicated-control (P+) composition.

### Fixed

- Inverted/scrambled cumulative DVHs were previously accepted silently by the TPS text reader.
- The shipped synthetic demo DVHs are regenerated analytically at 1 Gy resolution as physically
  valid, smooth cumulative curves (clearly labelled SYNTHETIC).

### Notes

- **Do-no-harm:** the classical NTCP/TCP numerics that back the published validation are unchanged
  by the interface and DVH-integrity work (the validator is on the text path only; the validation
  cohorts are extracted from dicompylercore-computed DVHs). Full suite: 763 tests, 0 failures.
- No patient data, cohort tables, or DICOM are included in this repository.

## [Unreleased]

### Added

- TCIA HNSCC external validation acquisition scaffold (`external_validation/`).
- TG-263 structure normalization (`engine/config/tg263_aliases.py`).
- TCIA HNSCC DICOM adapter and clinical covariate mapper.
- External validation pipeline (`engine/validation/hnscc_external_val.py`).
- **Real DVH feature front-end** (`engine/dicom_io/cohort_features.py`) + analytic synthetic
  DICOM-RT factory (`tests/synthetic/dicom_rt_factory.py`); `cohort_features.csv` builder.
- **Four-class external benchmark** (`engine/validation/extval_benchmark.py`): classical,
  clinical, dosiomics ML, and LQ-constrained **PINN** (`engine/validation/outcome_pinn.py`)
  under centre-grouped CV, with AUC/Brier/H-L/ECE/calibration/DCA and optimism plots.
- Benchmark + ablation drivers, synthetic CI mirror (`external_validation/`), `extval` CI job.
- `load_hnscc_outcomes` multi-sheet outcome loader; results in `docs/EXTVAL_RESULTS.md`,
  paper section in `paper/EXTERNAL_VALIDATION.md`.

### Fixed

- Pin `pydicom>=2.4,<3.0` and remove the legacy `dicom` dependency — dicompyler-core 0.5.6
  needs pydicom < 3.0, and the legacy `dicom` package shadowed pydicom, breaking all
  real-DICOM DVH extraction.

## [1.0.0] - 2026-06-10

### Added

- Version single source of truth (`engine/rbgyanx_engine/_version.py`) and `tests/test_version_consistency.py`.
- NaN-safety tests (`tests/test_nan_safety.py`) for all NTCP primitives.
- Inverse-variance consensus (`uncertainty/inverse_variance_consensus.py`) for **uNTCP** and **uTCP**.
- MCD-based Mahalanobis CCS (`validation/cohort_consistency.py`) with raw-covariance regression baseline.
- Composite decision module: therapeutic index/window, P+ (uTCP×Π(1−uNTCP)), `delta_ntcp()`.
- Four-tier benchmarking harness (`validation/four_tier_harness.py`) with EPV guard and group k-fold.
- Governance tests (`tests/test_governance.py`) for BASIC vs ADVANCED ML gating.
- Paper-figure capsule (`paper/`) with CI `paper-figures` artifact job.
- Root `pyproject.toml` workspace, synthetic tests, Zenodo reproducibility packaging.

### Changed

- NTCP primitives return **NaN** (not 0.0) for degenerate/empty inputs.
- PINN training requires `experimental=True` and logs not-for-clinical-use notice.
- `CITATION.cff`, `VERSION.txt`, and `pyproject.toml` aligned to **1.0.0**.

### Fixed

- `code3` clinical `PatientId` column alias.
- TCP mean/range test aggregates all registered TCP models.
