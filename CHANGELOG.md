# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.1] - 2026-11-12 — patch: NTCP is computed on EQD2, and three defects in what the evidence could show

A **patch** release, but **it changes every NTCP the software reports**. Four defects, all found by
review of the v1.5.0 evidence rather than by the test suite. No new scientific result; no analysis
rerun of its own.

### Fixed

- **#63 — the EQD2 conversion was skipped whenever the plan sat near 2 Gy per fraction.** The
  dose-volume histogram was converted to EQD2 only when the **plan's** dose per fraction was more
  than 0.3 Gy from 2.0, on the stated grounds that the transform was otherwise "the identity". It
  is the identity only for a bin that is itself at 2 Gy per fraction, and a histogram is not one
  dose: the conversion is bin-wise, so in a 70 Gy / 35 fraction plan a bin at 35 Gy receives 1 Gy
  per fraction and is 28 Gy EQD2 at α/β = 3. The published fits these parameters come from were
  made on EQD2 histograms — the larynx source
  ([doi:10.1016/j.ijrobp.2009.04.087](https://doi.org/10.1016/j.ijrobp.2009.04.087)) says so in
  its own methods, and the parameter file's provenance block already recorded it — so the software
  was scoring those organs on physical dose against EQD2 parameters. The conversion now runs
  whenever the fractionation is known; an unstated fractionation is still refused rather than
  assumed (#4/#5).
- **#62 — a refused target lost its percentile dose statistics.** `D2`, `D50` and `D98` are read
  off the histogram and depend on neither the prescription nor any model, but were computed only
  on the path where the model succeeded. They are now computed before any refusal returns.
- **#61 — the TCP model registry depended on how a run was batched.** The advanced models were
  registered as a side effect of a stage that runs after the patient loop, into a module-global
  registry, so the first patient of each process was scored without them and a resumed run
  produced a different set of rows from a straight-through one. They are registered once at run
  start. No value changes; the row set stops depending on process boundaries.
- **#64 — the run manifest reported on a prescription table that had never been consulted.** Two
  instances existed, one for the manifest and one for the lookups; only the second ever saw a
  patient, so a run overridden throughout was recorded as `n_patients_overridden: 0`. They now
  share one object, and every TCP row carries `prescription_source`. No computed value changes —
  what changes is that the output can now show whether a supplied table was applied.
- **A citation named someone who is not an author of the paper.** The larynx source read
  "Rancati T, Fiorino C, Fellin G, et al."; the paper has three authors, Rancati T, Fiorino C and
  Sanguineti G. Corrected against PubMed (PMID 19747783) and pinned by a test. The parameter
  values were already correct and are now pinned too.

### Changed — behaviour

- **NTCP is computed on EQD2 for every organ whenever the fractionation is known.** `gEUD_gy` on
  an NTCP row is the gEUD of the histogram the NTCP used, and the row records `ntcp_dose_basis`
  (`eqd2` or `physical`) and the α/β applied. The retired third value of that column,
  `physical_2gy_equivalent`, asserted the very thing that was wrong.
- **Direction of the change.** EQD2 is **below** physical dose where the dose per fraction is
  under 2 Gy and **above** it where the dose per fraction is over 2 Gy. NTCP therefore **mostly
  falls, but can rise**: in the one arm measured (116 patients, 750 patient-organ rows), **16 of
  750 gEUD values rose, the largest by +0.95 %**, against falls of up to about 50 %. Organ
  medians moved between −5 % and −37 %.
- **Reported dose statistics are unchanged.** `Dmean`, `Dmax`, `D2`, `D50`, `D98` and volume stay
  on the physical histogram; only the NTCP input is converted. Verified: 4,500 such values are
  bit-identical across a run with and without the fix.
- **QUANTEC constraints are evaluated on the physical histogram**, explicitly. Before #63 that
  basis depended on the plan's fractionation without saying so.

### Known limitations

- **Every release up to and including 1.5.0 computed NTCP on physical dose for conventionally
  fractionated plans.** Absolute NTCP and gEUD values published for 1.3.0, 1.4.0 and 1.5.0 are
  affected. Earlier version-to-version comparisons are **not** invalidated: both sides of the
  1.4.0 → 1.5.0 comparison scored on physical dose, so its attributions to the sourced parameters
  and to #47 stand. What moves is the absolute level, in both.
- The effect figures above are from a single treatment arm and are not cohort-wide.

## [1.5.0] - 2026-11-05 — minor: sourced parameters, defects that changed written numbers, and general software only

A **minor** release. It repairs software defects, replaces unsourced default parameters with
published fits, corrects documentation that described capabilities the software does not have, and
narrows the repository to general software usable by anyone with their own data. It **adds no new
scientific result** and reruns no analysis, and the release identifier stays **FINAL_V3.2** because
the analysis programme generation is unchanged.

**Three things to read before upgrading.**

1. **This release computes no CT radiomic feature.** The versioned record of one study's analysis
   was removed as study-specific material, and the CT feature engine went with it. The IBSI-1
   digital-phantom measurement of 56 of 63 reference features reproduced is a statement about
   **v1.4.0**, where that code shipped. See `docs/KNOWN_LIMITATIONS.md`.
2. **`Dmax_gy` is biased low and `Dmin_gy` high**, by `slice_thickness/2` x the local dose
   gradient - 1.5 Gy at a 3 mm slice and 1 Gy/mm - because the DVH end-caps structure volume but
   not the dose range. The direction is always the optimistic one. `Dmean_gy` and gEUD **at
   `a = 1`** are unaffected to within 0.5 Gy — but gEUD at `a = 20`, which is what the serial
   organs use, carries up to **−3 %** of the same bias, so spinal cord, oesophagus and mandible
   are not exempt. This is measured, bounded and documented, and **not fixed**: dose
   sampling sits in `dicompyler-core` and changing it would alter every DVH this project has
   produced. The convention choice is set out rather than taken.
3. **Default NTCP parameters changed**, organ by organ, to published fits with the source and
   endpoint recorded beside each value. If you relied on a previous default, read the parameter
   section below before comparing results across versions.

The work is grouped below as it was done, one block per tier, newest first.

---

### Fixed

- **gEUD dropped zero-dose bins**, so a negative exponent with an occupied 0 Gy bin gave a wrong
  answer (#45).
- **`geud_a` held `n` instead of `1/n`** (#47).
- **A DICOM read through the obsolete `dicom` package returned NaN everywhere without raising**,
  and the run completed and wrote a full output tree of them (#48).
- **Planning helper structures were scored as treated targets** — optimisation surrogates, rings,
  boolean subtractions and aggregate totals all mapped to `PTV` (#59).
- **Documentation claimed two capabilities the release does not contain**, and 21 references
  pointed at paths not in the repository (#53, #55).
- **`use_pyradiomics` was accepted and ignored** (#54).
- **A test asserted a guarantee it never checked** and would have passed with the code under test
  deleted (#57).
- **A declared version string that neither the release gate nor the consistency test read** (#58),
  and **version-bearing instructions in the documentation that nothing asserted on** — including an
  install command naming a wheel two releases old.
- **Test-configuration traps**: `-q` in `addopts` plus `-q` on the command line suppressed the
  totals line (#49); `pytest engine/tests` re-rooted and silently dropped `--strict-markers` and
  the import mode (#50).

### Changed (behaviour)

- **Default NTCP parameters are sourced**, organ by organ, to published fits, each with its source
  and the endpoint it was fitted to. Results computed with previous defaults are not comparable
  without reading the parameter section.
- **Targets are selected by name before DICOM type.** A structure matching a helper pattern is
  refused, logged and categorised `HELPER`, so target metrics and TCP no longer come from
  optimisation or ring structures. Studies whose structure sets contain such names will report
  fewer targets than before — that is the fix, not a loss.
- **The repository contains general software only.** One study's analysis record was removed, so
  **this release computes no CT radiomic feature**.
- **The CI matrix runs the default test selection** and excludes only marked tests.

### Added

- **An optional per-patient prescription table** (#60): a four-column CSV the user supplies, never
  inferred, with the plan's own values retained and the run manifest recording who was overridden.
- A `legacy` pytest marker, and tests pinning every defect above. The new test files are listed in
  the tier detail below.

### Deprecated

- `engine/dicom_io/tcia_hnscc_adapter.py` and `engine/validation/hnscc_external_val.py` remain as
  deprecation shims for the modules they were renamed to in this release
  (`dicom_cohort_adapter.py`, `external_validation_harness.py`). They are kept for one release.

### Known limitations

Carried into this release deliberately, each documented in `docs/KNOWN_LIMITATIONS.md` with its
measured magnitude:

- **The DVH end-caps volume but not the dose range** (#52): `Dmax_gy` low and `Dmin_gy` high by
  `slice_thickness/2 × gradient`, always in the optimistic direction. `Dmax` carries up to −15 %;
  serial-organ gEUD up to −3 %.
- **One prescription per plan**, taken from the RT Plan, unless the new table is supplied (#60).
- **Bilateral organ names receive no NTCP**: four of the eleven shipped head-and-neck organs are
  lateralised pairs, and a contour named without a side is refused rather than assigned one.
- **`pydicom < 3`** is required, because `dicompyler-core` imports a module removed in 3.0.
- **The illustrative organ count**, and which organs are illustrative rather than sourced.
- **`CalculateStructureVolume` returns `0.0` when shapely is absent** (#51) — unreachable from any
  rbGyanX call site, registered rather than fixed.

---

**Detail, by tier.**

The same work as it was done, newest first. The sections above are the summary; these are the
records, with the measurements and the reasoning behind each decision.


### Tier B/C: capabilities the docs claimed and the release did not have, and the test-suite blind spot

#### Fixed

**The documentation claimed two capabilities this release does not contain (defect #53).**

`docs/KNOWN_LIMITATIONS.md` stated, in the present tense, that "the radiomics implementation is
benchmarked against the IBSI-1 digital phantom and reproduces **56 of 63** reference features", and
pointed the reader at `analysis/ibsi/v3_ibsi_benchmark.py`. The CT feature engine and the benchmark
script were both removed with `analysis/` in "general software only". Measured on this commit:
searching every tracked file for any IBSI feature name — `glcm_*`, `glrlm_*`, `glszm_*`, `ngldm_*`,
`ngtdm_*`, `fo_*`, `shape_sphericity` — returns **no files**. **This release computes no CT radiomic
feature at all**, so the section described absent software and cited a path that resolved to
nothing. It now says so, attributes the 56-of-63 measurement to the version where that code shipped,
and states what is here instead. *Compliance* is still not claimed, as before.

`engine_advanced/rbgyanx_advanced/dose3d/dosiomics.py`'s docstring said the 3-D texture dosiomics
"(GLCM / GLRLM / GLSZM) are computed by this module", directly contradicting the sentence before it,
which said the module computes first-order dose statistics only. The scope-cleanup commit changed
exactly one line in that file: a pointer to another directory was re-aimed at the nearest module
instead of being deleted along with what it described. **The module has never computed a texture
feature** — it returns 20 first-order dose statistics. The docstring now states the scope
positively, denies the texture families by name, and records what the false sentence was.

**`use_pyradiomics` was accepted and ignored (defect #54).** `extract_dosiomics_features` declared
the parameter and never read it; the only related code was an import probe setting
`_PYRADIOMICS_AVAILABLE`, a name referenced nowhere in the repository. A caller asking for
pyradiomics-backed texture features received the ordinary first-order dictionary — no exception, no
warning, nothing in the returned data to say the request had been dropped. No call site passes it,
so no result was affected; it is fixed because a silently downgraded request is the failure mode
`assert_production_dose_source` exists in the same package to prevent. `True` now raises
`NotImplementedError` naming what the module does compute; `False`, the default, is unchanged and
returns exactly what it did before.

**Twenty-one references pointed at files that are not in the repository (defect #55).** The
scope cleanup removed 69 paths and left references to twenty of them behind, including: two live
Markdown links in README's documentation table; a string that `scripts/make_run_report.py` writes
into **every generated run report**; a line `scripts/build_zenodo_bundle.ps1` prints to the operator;
a module and its self-described "permanent positive control" test citing a pre-registration a reader
cannot obtain, as the justification for the module's default; two whole `KNOWN_LIMITATIONS` sections
written about an absent manifest; and audit findings cited by number to a removed report. Each one
now either resolves, or names the path together with the fact that it is not in this repository and
where it is. CHANGELOG entries that name a removed path *in order to record its removal* are left
alone — a changelog that cannot name what it deleted is not one.

The twenty-first was found by the new test rather than by the sweep, and has a different cause:
`docs/IMPLEMENTATION_ROADMAP.md` is titled after, and cited as its source, a `CURSOR_FIXES.md` that
`git log --all` shows **never existed in this repository**. That link never resolved for any reader
at any version.

`docs/CONSENSUS_B_RESULTS.md` is **removed**: 445 lines of cohort measurements — cohort size and
event counts, per-model Brier / ECE / AUC and calibration-slope tables, bootstrap confidence
intervals — which do not belong in general-purpose software. The mechanistic finding it supported
stays documented in `engine/uncertainty/inverse_variance_consensus.py`, stated as the algebraic
property it is: inverse-variance weighting uses `w = 1/σ²`, so one over-confident member captures
almost all the weight regardless of whether it is right. That property follows from the formula and
needs no dataset, and `engine/tests/test_consensus_robustness.py` pins it against a synthetic
over-confident member rather than against a cohort.

**CI ran 65 of 134 test files on the matrix (defect #46).** The `core` job — the one that runs on
ubuntu and windows × 3.10 / 3.11 / 3.12 — named six paths explicitly. The other **69 files, about
743 test functions**, ran only in the `full` job, which is a single configuration: ubuntu, 3.12,
full ML stack. So the whole `tests/ai_*` group (≈ 330 functions), the Qt smoke suite, the GUI-path
tests and the DVH integrity tests were never executed on Windows, and never on 3.10 or 3.11. A
regression confined to one of those would have passed a green CI.

The job now runs the **default selection** from `testpaths` and excludes **only by marker**. Adding
a test file can no longer leave it out of the matrix by omission, and excluding one requires marking
it, where a reader of that file sees the reason — rather than editing a path list in a workflow
nobody reads alongside the test. A `legacy` marker is declared for that purpose and **six tests in
three files carry it**: everything in `tests/test_tcp_analysis.py`, `tests/test_ntcp_analysis.py`
and `tests/test_integration.py`, which run `legacy/code3_ntcp_analysis_ml.py` and
`legacy/code6_tcp_analysis.py` in a subprocess. Those modules import `seaborn`, which is in the `ml`
extra; the core job installs only `.[dev]`, so the subprocess exits with `ModuleNotFoundError` and
the assertion on its return code fails. The code under test is retired lineage code the engine never
imports, and a contributor should not have to install a plotting library to run the core suite in
order to support it. The `full` job installs the extras and applies no marker filter, so those six
still run there — **the coverage moves, it does not go**.

How that was established, and where the local measurement was not enough: each of the 134 files
was run individually on Python 3.10.11 / Windows — the configuration the widening newly exposes —
giving **133 complete and 1 that does not finish**, `engine/tests/test_ml_models.py`.

**Local completion turned out not to imply a CI pass, and the first CI run on the widened selection
is what showed it.** The development virtual environment has `seaborn` installed from the `ml`
extra, so the six subprocess tests above passed locally and were recorded as needing no exclusion.
On the core job, which installs only `.[dev]`, five of them failed: **5 failed, 1820 passed, 49
skipped** on windows-latest / 3.11. The widening therefore did exactly what it was for — it surfaced
a real failure in files the matrix had never executed — and the claim that nothing needed the
`legacy` marker was wrong. It is corrected above rather than quietly dropped. Measuring a dependency
difference requires an environment that has the difference, and a venv assembled for development
does not. That file was already inside the
previous selection, so this change does not alter its exposure; it deadlocks on the development
machine after several nested cross-validation fits in one process (the hang point moves between
runs, each test passes in isolation, and `JOBLIB_MULTIPROCESSING=0` does not prevent it), and it
does not reproduce on CI. **The cause is not established and no fix is claimed.** The one check not
performed locally is a single whole-suite run, which would exercise cross-file interaction; it was
skipped because the machine is memory-constrained, the `full` job already performs exactly that run
on ubuntu, and the matrix performs it on every cell.

**A quiet flag in `addopts` could hide a failing run completely (defect #49).** pytest sums
verbosity flags, so `-q` in `addopts` plus `-q` on the command line is `-qq` — which suppresses the
totals line as well as the per-test output. A run with failures then printed no summary at all and
read like a run that had done nothing. `-q` is removed from the root `addopts`; CI passes it
explicitly where it wants it, so `pytest -q` from a shell now means one level of quiet.

**`pytest engine/tests` ran under weaker settings than intended (defect #50).** pytest chooses its
rootdir by walking **up** from its arguments to the nearest ancestor carrying a pytest
configuration, so that invocation stops at `engine/pyproject.toml` and never reads the root
`pyproject.toml`. The root `addopts` and marker list were silently dropped: `--strict-markers` was
off, so a mistyped marker name would be accepted and the test would run unmarked, and the import
mode fell back to `prepend`. Nothing failed — the suite just ran under different rules than the
author wrote, which is the worst form of this bug. The re-rooting is pytest's own documented
behaviour and is not changed; instead the load-bearing options are duplicated into
`engine/pyproject.toml`, so the checks are identical whichever configuration wins, and a new test
asserts the **effective** configuration so the two copies cannot drift apart again.
`engine/conftest.py`'s comment cited a `pytest.ini` that does not exist in this repository, and an
import mode that file did not in fact set; corrected.

**A test asserted a guarantee it never checked (defect #57).**
`tests/test_ntcp_analysis.py::test_ntcp_validation` claimed to check that the clinical-data
validation rejects a file with missing required columns. Its assertion began
`result.returncode != 0 or ...`, which **any** non-zero exit satisfies, and the command it ran
passed `--dvh_dir test_data/DVH_files` — a path that does not exist in this repository. Measured:
the script prints `DVH directory ... not found` and exits 1 *without ever opening the clinical
file*. So the test passed because of a missing directory, and on the CI core job because of a
`ModuleNotFoundError`, and **it would have passed with the validation code deleted**.

It now takes the `synthetic_data_dir` fixture its three siblings already use, so the script reaches
the clinical file, and asserts two things instead of a disjunction: that the run did *not* exit on a
missing DVH directory — naming this failure mode, so its return is caught — and that the output
carries a validation message, with the message stating explicitly that a non-zero return code alone
is not evidence the validation code ran. The script does reject the file, and the test now
demonstrates that rather than asserting around it.

#**Planning helper structures were scored as targets (defect #59).** Optimisation surrogates
(`…OPT`), dose-shaping rings (`Ring…`), boolean subtractions of one target from another
(`PTVLow-PTVMid`) and aggregate totals (`PTV_Total`) were all mapped to canonical `PTV` and scored
as treated targets, receiving TCP and target dose metrics that mean nothing for them. Because such
structures share a name stem with the real target and often overlap it, a study could report
several apparent "targets" with near-identical dose.

The reason the DICOM type did not prevent it: planning systems write
`RTROIInterpretedType = PTV` on these structures, describing what the contour was derived from
rather than what is treated. The name is now checked first; a structure matching a helper pattern
is refused as a target, logged with its reason, and categorised `HELPER`. If every candidate is
refused, the run says so explicitly rather than reporting "no target". The patterns describe naming
conventions used across planning systems and sit in one place to be extended.

**One prescription per plan, now overridable (defect #60).** The engine takes a single prescription
from the RT Plan's `DoseReferenceSequence`. That is wrong whenever an archive writes a nominal
value into every plan while the real per-patient prescription lives elsewhere — and it is not
cosmetic, because TCP's EQD2 and BED are computed from the prescription rather than from the
target's measured dose, and V95/V100 coverage, conformity and gradient index are scaled by it. A
wrong prescription changes reported numbers while every dose value stays the same.

v1.5.0 adds an **optional** per-patient prescription table the user supplies: a four-column CSV
(`patient,target_roi,prescription_gy,n_fractions`) passed as `RunnerConfig.prescription_table`. It
is never inferred. A patient absent from it keeps the RT Plan value; the plan's own values are
retained in the output under `*_from_rtplan`; every row records a `prescription_source`; and the
run manifest records the table's path, its SHA-256 and which patients were overridden. A dose
outside 1–120 Gy, a fraction count outside 1–60, a duplicate patient or a non-numeric field stops
the run at load time rather than halfway through a cohort.

#### Added

- `engine_advanced/tests/test_v150_dosiomics_scope_claims.py` — 5 tests for #53 and #54. Three fail
  on v1.4.0.
- `engine/tests/test_v150_pytest_config_trap.py` — 8 tests for #49 and #50, asserting the effective
  pytest configuration and that both config files carry the same load-bearing options. Five fail
  against the pre-fix engine configuration.
- `tests/test_v150_doc_links_resolve.py` — 38 cases, one per tracked Markdown file outside
  `docs/archive/` and `legacy/`, asserting that every relative Markdown link resolves. This covers
  the objectively checkable part of #55 and deliberately nothing more: a regex cannot tell prose
  that names a dead path from prose that names it in order to say it is gone, and the corrected text
  does the latter on purpose.
- `engine/dicom_io/prescription_table.py` — the optional per-patient prescription table, with
  `engine/tests/test_v150_prescription_table.py` (22 tests).
- `engine/tests/test_v150_helper_target_refusal.py` — 39 tests for #59.
- A `legacy` pytest marker, declared in both configs, as the mechanism for #46's exclusions, and
  applied to the six subprocess tests that drive retired `legacy/` modules.
- `tomli>=2.0` in the `dev` extra for `python_version < '3.11'`. Declared rather than inherited
  from another dev dependency: the configuration test reads both `pyproject.toml` files as TOML,
  `tomllib` is stdlib only from 3.11, and a skip on 3.10 would be a silent gap in the one test whose
  purpose is to stop a silent configuration difference.

#### Notes

`analysis/` is still listed in the ruff exclusion list although the directory is absent. That is
deliberate and the comment there now says why: the directory is retrievable from the `v1.4.0` tag,
and its scripts are pinned by SHA-256 to the exact bytes that produced the reported results, so a
restored checkout of it must not be silently reformatted.

### Tier D: refusing to read DICOM through the obsolete `dicom` package

#### Fixed

**With pydicom 3 installed, every DICOM read silently returned nothing.** `dicompylercore`
guards its reader import with `try: from pydicom.dicomio import read_file / except ImportError:
from dicom import read_file`. **pydicom 3 removed that name**, and no released dicompyler-core
(0.5.6 is the latest) has stopped importing it — verified against pydicom 3.0.1, where it is the
only one of the four names dicompyler-core imports that is missing. So with pydicom >= 3 **and**
the obsolete `dicom` distribution installed, the fallback succeeds and the reader binds to a
library written for Python 2, which raises `RuntimeError: generator raised StopIteration` on
Python 3.7+.

The failure was the dangerous kind: **not an exception, but NaN everywhere.** No dose grid was
read, so no DVH was extracted, so every TCP and NTCP came out NaN — and the run *completed*,
writing a full output tree of them.

`engine/dicom_io/reader_guard.py` now checks what `dicompylercore.dicomparser.read_file` actually
resolved to and **raises before any DICOM is read**, naming the resolved module, both versions and
the two ways to fix it. It guards `DVHExtractor.extract_all_dvhs` — the one rbGyanX read that goes
through dicompyler-core. `dicom_reader` and `cohort_discovery` call pydicom directly and are
unaffected; a test pins that they stay unguarded, because guarding them refuses runs that are in
fact sound.

Two dependency declarations lacked an upper bound and now have one: the `dose3d` extra in
`engine_advanced/pyproject.toml` and `packaging/requirements-build.txt`. The other five
declaration sites already said `pydicom>=2.4,<3` with the reason, and the fault still occurred —
**a declaration constrains an install, not an environment that drifted afterwards**, which is why
the runtime check is the substantive part of this fix.

#### Added

`run_manifest.json` records **`dicom_reader`**: the module the reader resolved to, the pydicom and
dicompyler-core versions, and a boolean. A manifest recording pydicom's version alone, as it did,
cannot show which reader was bound.

#### Notes

No rbGyanX code path calls `dicompylercore`'s `CalculateStructureVolume`, which returns `0.0`
rather than refusing when shapely is absent. Structure volumes come from the DVH's own histogram,
so that zero cannot reach an output, and **shapely is deliberately not added as a dependency**.
Recorded so the next caller knows to wrap it in a refusal first.

Tests: `engine/tests/test_v150_dicom_reader_guard.py` (14) — both branches of the guard with the
resolved module substituted, the message asserted to be actionable on its own, the guarded door,
and the two doors that must stay unguarded.

### Scope: general software only

The repository now contains general software: usable by anyone with their own data, with nothing
specific to one study in its code, docs, tests or history. Measurements on a particular cohort,
manuscript references and journal names belong in that study's own evidence package.

Everything removed below exists at the `v1.4.0` tag and in the archive deposited for that release,
so it stays retrievable. Verified file by file before removal: all 75 paths resolve at `v1.4.0`.

#### Removed — study-specific material

- `analysis/` — the analysis pipeline for one study, its scripts numbered to that study's own
  figure and table order.
- `paper/` — a figure capsule for one manuscript, and the CI job that ran it. Its data was
  synthetic, but its purpose was not general.
- `scripts/cohort_builder/`, `scripts/dvh_builder/`, `scripts/audit_spark_dataset.py`,
  `scripts/run_ntcp_benchmark_workspace.py`, `scripts/build_parotid_cohort_workspace.py` — these
  drove one study's workspace. The DVH inspection tools took no arguments at all: they walked up
  for a directory named after the study workspace and then into a hard-coded centre and patient
  folder.
- The dataset-acquisition half of `external_validation/`: the download script, the
  collection-specific validation runner, the feature builder that read one archive's zip layout,
  and their READMEs. **The general half is kept** — the synthetic feature-table mirror, the
  benchmark runner and the ablation analysis, which CI, an example and the tests use.
- `clinical/hnscc_covariate_mapper.py` — a column map for one clinical workbook. The harness now
  takes a `clinical_mapper` callable instead, defaulting to reading the sheet as it stands with
  column names normalised, so adapting a workbook is the caller's business.
- Eight run reports and investigations under `docs/`, and `docs/MANUSCRIPT_EVIDENCE.md`.
- `reproducibility/README_REAL_DATA.md` and `ZENODO_UPLOAD_GUIDE.md`. The synthetic reproduction
  guide stays, because that is the reproduction path this repository supports.
- `tests/test_extval_cohort_builder.py` and `tests/test_real_dosiomics_resume.py`, whose targets
  were removed with the above.

#### Changed

- `DATA_AVAILABILITY.md` is now a short general statement: the software ships no patient data, the
  tests run on synthetic data only, and users supply their own DICOM under their own governance.
  The cohort inventory it used to carry is study material.
- Cohort measurements are gone from the historical entries below. Each entry keeps its version,
  its date and the feature itself; a count measured on one cohort does not describe the software.
- About two dozen comments and docstrings across `engine/` and the test suite no longer name a
  dataset as the place a behaviour was observed. Every defect keeps its number, how it was found
  and its status.

#### Fixed — a NaN model column could shorten a composite, a ranking or a metric

Four organs lost their `NTCP_LKB_loglogit` **value** when an unsourced log-logistic block was
replaced by a published probit fit: HN `Larynx`, HN `Mandible`, BREAST `Thyroid`, and `Esophagus`
at every site. The column still exists and is NaN for them, which is correct as a reported value —
that model was not applied, and NaN says so.

The hazard was downstream, and it was real. With the organs of a site now split between the two
model forms, **no single model column covered a whole OAR set**, so three consumers that each read
one fixed column took NaN for part of their input:

- **P+ refused outright.** `compute_utcp` read one column, reported the organs scored by the other
  model as missing, and returned NaN with `UTCP_INCOMPLETE_OAR_SET` — at a site where every OAR
  had in fact been scored. Whichever model was requested, four of the eight head-and-neck OARs
  came back missing. The refusal guard behaved correctly; the input it was given was wrong.
- **The patient summary's "top OARs" was silently shortened.** It coerced one column to numeric
  and took the five largest, so organs scored by the other model dropped out of the ranking with
  no indication.
- **A validation metric could be computed on nothing.** The per-organ NTCP validation iterated the
  model columns and would have scored an all-NaN prediction vector.

All three now read the NTCP **per organ** through the new `radiobiology.ntcp_row.select_ntcp`,
which returns the value and the model that produced it, preferring a requested model and falling
back through the rest. `ntcp_model` remains a preference and is no longer the only option.

Because a P+ may now draw on more than one model form, that is recorded rather than hidden:
`scored_OAR_models` on the result, `UTCP_NTCP_models` and `UTCP_mixed_NTCP_models` on the row. An
organ with no finite NTCP from any model is still refused, so containment did not become
permissiveness. `engine/tests/test_v150_nan_model_column_containment.py` (26 tests) pins all of
it, including that a genuinely missing organ still refuses P+.

#### Deprecated

Two modules were named for one public collection although what they do is general. Both were
renamed, and a thin shim at each old path re-exports the new names and raises
`DeprecationWarning`. The shims will be removed in the release after next.

| Old path | New path | Renamed symbols |
|---|---|---|
| `engine/dicom_io/tcia_hnscc_adapter.py` | `engine/dicom_io/dicom_cohort_adapter.py` | `HNSCCPatientRecord` → `DicomPatientRecord`, `adapt_hnscc_cohort` → `adapt_dicom_cohort` |
| `engine/validation/hnscc_external_val.py` | `engine/validation/external_validation_harness.py` | `run_hnscc_external_validation` → `run_external_validation` |

The harness's `DISCLAIMER` keeps the distinction that matters — validating against a recurrence or
survival endpoint says nothing about whether an NTCP model predicts toxicity, because they are
different endpoints — and no longer names a collection.

### Parameters: sourced default NTCP values

**The scientific change of v1.5.0, kept separate from the code fixes on purpose.** Every value in
`engine/config/site_params_ntcp_default.yaml` now carries a per-model `provenance` block naming its
source, the table and page it was transcribed from, the endpoint it was fitted to, its dose basis,
and what the structure was in the paper. `as_printed` holds the numbers exactly as the paper prints
them and `conversion` states every derivation; the only derivation used is `geud_a = 1/n`, the
Kutcher-Burman DVH reduction the LKB probit model is defined on. **Default parameter values change,
so NTCP written by v1.4.0 and earlier is not comparable with v1.5.0 output.**

Three sources were read and transcribed: **Burman C, Kutcher GJ, Emami B, Goitein M. IJROBP
21:123-135 (1991), Table 1, p. 125**, **Rancati T, Fiorino C, Fellin G, et al. IJROBP
75:915-923 (2009), p. 919**, and **Bakhshandeh M, Hashemi B, Mahdavi SRM, et al. IJROBP
85(2):514-521 (2013), Table 2, p. 517**.

#### Changed — parameters now carry a citation

- **Spinal cord, at five sites.** `TD50` 45.0 -> **66.5 Gy**, `m` 0.18 -> 0.175 (Burman, myelitis /
  necrosis). The 45 Gy was a planning constraint, not a fit. `LUNG` and `PROSTATE` had no cord
  entry at all and now have one. `LIVER` already used 66.5 and gains the probit form, so all five
  sites finally agree.
- **Brain stem, at three sites.** `TD50` 53.0 -> **65.0 Gy**, `m` 0.18 -> 0.14, `n` 0.05 -> **0.16**,
  `geud_a` 20.0 -> 6.25. A threefold change in the volume effect, not only in TD50.
- **Larynx.** The unsourced log-logistic fit (`TD50` 44.0, `gamma50` 0.7) is replaced by
  **Rancati's LKB fit: `TD50` 47.3 Gy, `m` 0.23, `n` 1.17**, `geud_a` 0.855, for subacute/late
  grade >= 2 laryngeal edema scored by fiberoptic examination. Rancati fitted the EUD of EQD2 DVHs
  at alpha/beta 3 Gy, which is this organ's `alpha_beta_gy`, so the engine's EQD2 transform matches
  the fit.
- **Mandible.** Replaced by Burman's **TD50 72.0 Gy, m 0.10, n 0.07**. Read the endpoint before
  using it: the row is "TM joint and mandible" and the endpoint is **marked limitation of joint
  function**, not osteoradionecrosis. Both facts are on the value.
- **Esophagus, at four sites.** `TD50` 34.0 -> **68.0 Gy**, with `m` 0.11, `n` 0.06 (Burman,
  clinical stricture / perforation). The old 34 Gy had no source and is about half Burman's, which
  is consistent with an acute-esophagitis threshold - **a different endpoint, and one v1.5.0 does
  not model.** `LIVER` had no esophagus entry and now has one.
- **Optic chiasm** `TD50` 55.0 -> 65.0, **optic nerves** 54.0 -> 65.0, both with `m` 0.14,
  `n` 0.25, `geud_a` 20.0 -> 4.0 (Burman, blindness).
- **Brachial plexus** `TD50` 54.0 -> 75.0, `m` 0.12, `n` 0.03, `geud_a` 33.33 (Burman, clinically
  apparent nerve damage).
- **Femoral heads** `TD50` 52.0 -> 65.0, `m` 0.12, `n` 0.25 (Burman, necrosis; the structure is the
  femoral head **and neck**).
- **Rib** `TD50` 50.0 -> 68.0, `m` 0.21, `n` 0.10, `geud_a` 20.0 -> 10.0 (Burman, pathologic
  fracture; the reference volume is **one third of the rib cage**, not a single rib).
- **Stomach** `TD50` 68.0 -> 65.0 with `m` 0.14, `n` 0.15 (Burman, ulceration / perforation).
- **Liver** `n` 0.97 -> **0.32** and `geud_a` 0.97 -> **3.125** (Burman, liver failure). TD50 and m
  already matched Burman; `geud_a` had been set to `n` rather than `1/n`, so the DVH reduction used
  the wrong quantity.
- **Thyroid.** The unsourced log-logistic fit (`TD50` 37.7, `gamma50` 0.7) is replaced by
  **Bakhshandeh's LKB probit fit: `TD50` 44.3 Gy, `m` 0.25, `n` 0.92**, `geud_a` 3.0 -> 1.087, and
  the **relative-seriality fit from the same table is added: `D50` 43.5 Gy, `gamma` 1.49,
  `s` 0.05**, which needs no conversion because the engine's RS block is the paper's own
  parameterisation. The endpoint is any (clinical or subclinical) hypothyroidism within 1 year,
  fitted to the EUD of EQD2 histograms at alpha/beta 3 Gy, which is this organ's own alpha/beta.
  `n` 0.92 and `s` 0.05 agree with each other: an almost fully parallel organ. The organ is no
  longer illustrative, so **BASIC mode now computes it**. Two things are recorded on the value
  rather than left implicit: the fit comes from a head-and-neck cohort and is applied here to the
  incidental irradiation a breast plan delivers, a different dose distribution; and the same
  paper's Table 4 offers a more conservative fit for *clinical* hypothyroidism only
  (`n` 0.49, `m` 0.24, `D50` 60 Gy), kept in `alternative_fit` as the documented alternative.
- **Heart, lungs, normal brain and bladder** keep their TD50, which already equalled Burman's, and
  gain the `m` and `n` the log-logistic form cannot carry: heart 48.0 / 0.10 / 0.35, lung
  24.5 / 0.18 / 0.87 (`geud_a` 1.149, close to mean dose, as accepted for lung), brain
  60.0 / 0.15 / 0.25, bladder 80.0 / 0.11 / 0.5. `BRAIN_METS` had no normal-brain entry and now
  has one.

**Five probit blocks used to share the identical `m = 0.18, n = 0.05`** across SpinalCord,
BrainStem, BrachialPlexus, OpticChiasm and OpticNerve, at four sites. Five organs cannot share one
volume effect; Burman gives 0.05, 0.16, 0.03 and 0.25 for the same four. A test now refuses that
pair anywhere in the library.

#### Added — `illustrative`, and BASIC mode refuses it

Twenty of fifty-seven organ entries have no citable source and are marked
`illustrative: true`. **BASIC mode refuses them**: the column is NaN and the row carries
`ILLUSTRATIVE_PARAMS_IN_BASIC_MODE`. ADVANCED mode computes them and labels every row with
`param_source` and `param_illustrative`. The refusal is per model, so an organ with a sourced
probit fit and an unsourced relative-seriality block keeps the first and loses the second.

**Note the consequence for the parotid**, which is a commonly reported organ: it keeps its
QUANTEC-consistent values (`TD50 28.4`, `geud_a 1`) but stays illustrative until Deasy et al. 2010
can be cited with a page, so **a BASIC-mode head-and-neck run reports no parotid NTCP**. Run in
ADVANCED mode to compute it, labelled.

`site_params_ntcp_user.yaml` overrides are handled the same way: a model supplied without its own
provenance becomes unsourced, because the shipped citation described a different number.

#### Changed — PELVIS P+ is refused as unsupported

`UTCP_OAR_MAP["PELVIS"]` lists six OARs and there is no `PELVIS` NTCP block at all, so none can be
scored. P+ for PELVIS is refused with the new reason **`UTCP_SITE_UNSUPPORTED`**, which
`allow_partial=True` deliberately does not override: a partial product means "score the organs I
have", and here there are none. Every other site in the map is now fully scorable - the gaps a
published fit could fill (LUNG and PROSTATE SpinalCord, BRAIN_METS NormalBrain, LIVER Esophagus)
were filled from Burman.

#### Changed — ntcp_results.csv

Four columns are added, per model row: `param_source`, `param_illustrative`, `param_endpoint`,
`param_table_page`. Four organs lose their `NTCP_LKB_loglogit` value, which becomes NaN, because
the unsourced log-logistic block was replaced by a sourced probit fit: HN `Larynx`, HN `Mandible`,
BREAST `Thyroid`, and `Esophagus` at all four sites.

#### What a parameter change does to a reported NTCP

Changing TD50, m or n changes every NTCP the model produces, and the direction is not always the
same for every structure. Where the new fit is *shallower* than the one it replaced, the two
dose-response curves cross: below the crossing dose the new fit predicts **more** risk, above it
less. The larynx is such a case - Rancati's `m = 0.23` against the previous `gamma50 = 0.7` - so
this release must not be summarised as "NTCP went down".

The quantitative effect on any particular dataset is a property of that dataset, not of the
software, and is reported in the accompanying evidence package rather than here.

#### Tests

`engine/tests/test_v150_sourced_parameters.py` (58): the schema (every model block has provenance,
every provenance block declares all required fields, a sourced block names a page and an endpoint,
`as_printed` matches the shipped value, `geud_a == 1/n` for every sourced probit fit), the
transcription of 22 Burman values, the Rancati fit and both Bakhshandeh blocks with their 95%
confidence intervals, the pinned illustrative inventory, the BASIC-mode refusal including the
per-model and user-override cases, and the agreement of the AI reference pack with the engine
config.

`engine/config/site_params_ntcp_default.yaml` no longer claims to be generated, and no longer
points at a path outside the repository: each value's own `provenance` block is the record, so the
transcription is checkable from that file alone.

### Tier A: the defects that change written numbers

Thirteen output-affecting defects in `engine/`, each with a test that fails at v1.4.0 (`ffd69ef`)
and passes after the fix. **These change numbers.** Several change them on every run, so output
produced with v1.4.0 and earlier is not comparable with v1.5.0 output. Default NTCP parameters are
deliberately **not** touched here; they are a separate change with its own section above.

#### Fixed — values that were simply wrong

- **gEUD dropped every zero-dose bin.** `compute_geud` masked `doses > 0`, so the unirradiated part
  of a partly covered target vanished from the generalised mean and the remaining volume was
  renormalised to 1: its gEUD read as the hot dose alone. For a differential DVH with 50% of the
  volume at 0 Gy and 50% at 70 Gy, v1.4.0 returned **70.0 Gy** at a = 1, a = 3 and a = -10 alike;
  the correct values are **35.0, 55.56 and 0.0 Gy**. The error is one-directional: gEUD is
  overstated, so a target with a cold region looks better covered than it is. Zero-dose bins are
  kept now; for a < 0 the limit 0.0 is returned with the reason `GEUD_ZERO_DOSE_NEG_A`, carried to
  the TCP row as `gEUD_reason`. A structure that received no dose reads 0 Gy instead of NaN - "no
  dose" and "not computable" are different statements.
- **The EPV guard counted the wrong class.** It hard-coded `events = sum(y == 0)`, correct only for
  one coding convention. With an outcome coded the other way round it counted the majority class:
  for 12 events in 100 cases labelled 1 = event it reported **88 events and EPV 44.0** instead of
  12 and 6.0, so a model that should have been refused was waved through. `event_label` is now a
  required keyword argument with no default and nothing inferred; a non-binary outcome and a label
  absent from the data are both refused. Threaded through every caller, including
  `extval_benchmark._run_c2`, which had its own minority-class inference that disagreed with the
  event count the same module reports.
- **PRV expansions were scored with organ parameters.** A planning-risk volume is the organ grown
  by a margin, so its DVH is colder and larger, and scoring it against the organ's published
  parameters is scoring a different structure. `SpinalCord_05` and `BrainStem_03` carried no alias,
  fell through to fuzzy TG-263 matching and came back as the organ itself; `brainstemprv` was
  mapped onto the organ by the alias table outright. Because the two then share one `structure`
  label, an organ and its own PRV could arrive as indistinguishable rows. PRVs now get their own
  canonical key, `<Organ>_PRV`, with `is_prv` and `prv_of` on the mapping result, and are never
  scored with organ parameters unless the operator maps that key themselves.
- **Each SIB target is scored against its own dose level.** A plan carries one
  `prescription_dose_gy`, so on a simultaneous integrated boost every target was given the highest
  level - a PTV56 was scored at 70 Gy, which overstates its TCP. The level is read from the
  `DoseReferenceSequence` item referencing the ROI or matching its description, else from the
  target's own name (`PTV63`, `PTV_5040_cGy`), else TCP is refused. `dose_level_gy` and
  `dose_level_source` are written on every row.
- **The manifest's seed did not drive the Monte Carlo.** `RunnerConfig.seed` was recorded in
  `run_manifest.json` while `ParamUncertaintyConfig` and `NTCPUncertaintyConfig` both stayed at a
  hard-coded 42, so the manifest named a seed the run had not used. It is threaded through now,
  which means **uncertainty bands change**: the manifest is true, and the cohort runner's own
  default seed is 0.

#### Fixed — refusing instead of publishing

- **No prescription or fractionation is invented from a TPS text export.** The prescription fell
  back to the DVH maximum and the dose per fraction to a flat 2.0 Gy, with a logged warning beside
  the written number. A DVH maximum is not a prescription - it overstates the dose on a hot plan
  and understates it on a cold one - and 2 Gy per fraction is a guess about someone else's clinic.
  A header stating neither used to yield a prescription equal to the DVH maximum and a fraction
  count derived from it; both defaults are gone. TCP is refused with `RX_MISSING` /
  `FRACTIONATION_MISSING`; NTCP still runs, on physical dose, with `ntcp_dose_basis` saying so; and
  `--rx-gy` / `--n-frac` state what the header cannot. `RunConfig.dose_per_fraction` and
  `RunnerConfig.dose_per_fraction` default to `None` rather than 2.0.
- **TCP is refused outside the LQ model's validity range.** A dose per fraction above
  `lq_valid_max_dpf_gy` only raised `lq_caution`. `LUNG_SBRT` at 18 Gy x 3 is an extrapolation, so
  TCP is now refused with `LQ_INVALID_DPF` unless `allow_lq_extrapolation=True` is passed
  explicitly. A refused row keeps its dose metrics.
- **A site with TCP parameters but no NTCP block reports rather than falls silent.**
  `PROSTATE_SBRT` and `LUNG_SBRT` have no organs in `site_params_ntcp_default.yaml`, so
  `allowed_oar_names()` was empty, the OAR filter discarded every contour, and the run produced no
  NTCP rows and no reason - indistinguishable from a case with no OAR contours. Each OAR now gets a
  row with NaN for every model, `definition_ok = False` and `NO_NTCP_PARAMS_FOR_SITE`.
- **P+ over an incomplete OAR set is refused.** The UTCP OAR map had drifted from the canonical
  vocabulary: HN, BRAIN_GBM and BRAIN_METS said `Brainstem` where everything else says `BrainStem`,
  so **the brainstem never entered P+ at three sites**; BREAST listed `Lung_Ipsi` and `Lung_Contra`,
  which both canonicalise to `LungTotal`, so one organ entered the product twice. Every entry is
  resolved through `canon_target()` and de-duplicated on the higher severity weight. Since P+ is a
  product over all the site's OARs, dropping one raises it, so an incomplete set gives NaN with
  `UTCP_INCOMPLETE_OAR_SET` and the missing organs named, unless `allow_partial=True`.
  `UTCP_OARs_scored` and `UTCP_OARs_missing` are on every row, including rows that got no UTCP.
- **An arbitrary tie-break between plans is refused.** Plan selection ranked APPROVED, then latest,
  then SOPInstanceUID. When several plans are all UNAPPROVED with the same prescription and date,
  only the UID separates them - an accident of the archive that a re-export can reorder. Such a
  case is refused with `AMBIGUOUS_PLAN_SELECTION`, the candidate labels are listed, and
  `--plan-label` or a per-case override resolves it. Approval, a later date or a different
  prescription still separate plans without an operator.

#### Fixed — saying what a number means

- **Every uncertainty band declares its coverage.** `p5`-`p95` is a 90% interval and nothing on the
  row said so, while `utils/uncertainty_models.py` reports a genuine parametric 95% CI on a
  different path. Column names are unchanged; `band_level` is now on every aggregate - 0.90 in the
  engine, `confidence_level` in the utils path - and the two docstrings that had drifted are one.
- **EPV is printed to three significant figures.** `{epv:.1f}` rendered a true EPV of 0.024 as
  `EPV=0.0 < 5`, which reads as no events at all.
- **Organ-key reachability is measured against real structure names.**
  `_validate_default_organ_keys_reachable()` asserted `canon_target(key) == key`, which compares
  the alias table with itself and passes however far it has drifted from what a planning system
  writes - `PharynxConst`, a common export spelling, went unmapped while the check was green.
  Reachability is now measured against `tests/fixtures/contour_name_corpus.txt`, a corpus of
  structure-name variants collected from public sources (**names only; no patient data**). The
  organ keys the corpus cannot reach are pinned by the test so the inventory cannot drift, with the
  reason recorded for each - a site the corpus does not cover, or an organ whose name carries no
  laterality and so must not be given one.

#### Known gaps surfaced, not closed

- **Five UTCP sites listed OARs their NTCP block could not score**, so P+ at those sites was NaN by
  default: BRAIN_METS/NormalBrain, LUNG/SpinalCord (both fractionations), PROSTATE/SpinalCord,
  LIVER/Esophagus, and all six organs of PELVIS, which has no NTCP block at all. The first four are
  filled in the parameter section above; PELVIS remains, because supplying parameters is a
  scientific decision, not a code fix.
- **`ITV50` maps to UNKNOWN** rather than a target: the dose-embedded-name pass covers the gtv,
  ctv and ptv prefixes and not itv. Pre-existing and out of Tier A's scope.

### The DICOM path through the desktop app

Three defects found by driving the Qt app over a synthetic DICOM-RT study. **All three sat in the
GUI and service layer; the engine beneath was correct throughout**, which is why they went
unnoticed — every written CSV carried the right numbers. **No published result is affected and no
analysis was rerun**: `engine/` is unchanged, and cohort runs go through
`rbgyanx_engine.cohort_runner`, which touches none of this.

#### Fixed

- **The folder check refused a cohort root the engine handles.** `_looks_like_dicom_dir` inspected
  only the chosen folder, so a cohort laid out one patient per subfolder — what
  `scripts/make_synthetic_dicom_cohort.py` writes, and what `docs/GUI_MODES_AND_HELP.md` tells the
  operator to browse to — was rejected with *"Folder does not look like DICOM RT"*, although the
  engine processed that same root correctly when called directly. It now also checks immediate
  subfolders. Depth stays bounded at one level on purpose: a wrongly chosen folder must never cost
  a full recursive walk.
- **The Cohort flow view raised on a DICOM result.** Its opening stage counted files while the
  next counted structures. One DVH text file is one structure, so the text path was monotone; one
  RTSTRUCT carries many, so DICOM was not, and `CohortFlowSpec` correctly refused a flow that
  grows — the `ValueError` then escaped `MainWindow.populate_results`. The file stage is now shown
  only when it bounds the structure count, which is exactly when it is meaningful.
- **Structure volume was lost on the DICOM path.** The results table read `nan` in Volume (cm³)
  for every row while the written `ntcp_results.csv` carried the real value. The adapter asked
  rows for `volume_cc`; the engine names it **`total_volume_cc`**. A single mis-spelled lookup,
  silently defaulting to NaN — the text path was unaffected because it reads the parsed object
  rather than an engine row.

`tests/test_dicom_gui_path.py` covers all three.

## [1.4.0] - 2026-10-17 — minor: provenance, laterality and determinism repaired

A **minor** release. It repairs software defects and **adds no new scientific result**: no analysis
was rerun to produce it, every headline value in the head-and-neck evidence package is a
measurement rather than a change, and the release identifier stays **FINAL_V3.2** because the
analysis programme generation is unchanged.

### Fixed

- **Provenance was computed and discarded.** `site`, `site_confidence` and `dvh_mode` are now
  populated on every cohort row instead of none, and `dose_selected` — a column that did not
  previously exist — on every row as well.
- **The structure mapper assigned a laterality absent from the source contour name.** A fuzzy
  match that would assign a side not present in the contour name is now **refused**. Consequence,
  stated with the loss: `Submandibular_R` previously yielded **1,062** NTCP rows with a laterality
  absent from the source contour name and now yields none; `PharynxConstrictor` becomes reachable,
  **0 of 121 → 121 of 121**, adding 1,071 rows. Net NTCP rows **9,057 → 9,066**, reconciling
  exactly as +1,071 − 1,062 = +9. Organ reachability stays 7 of 11, but its composition changes
  from six correct plus one unsupported laterality to **seven correct**.
- **Site-detection `evidence` strings rendered non-deterministically**, so the same input could
  produce byte-different evidence values between runs. They are now stable, asserted by
  `engine/tests/test_output_determinism.py::test_evidence_strings_are_identical_across_hash_seeds`
  across `PYTHONHASHSEED` values. This covers the `evidence` strings, not every output.

### Added

- **LLM-assisted structure mapping that proposes and never decides.** Every proposal is validated
  in code before use; the model cannot introduce a mapping the validator rejects. The proposal,
  validation and approval pipeline is tested against a mocked provider; no evaluation against a
  live model is included in this release.

### Known issues

- The obsolete **`dicom`** distribution (pydicom's pre-1.0 name, unmaintained since 2017) shadows
  `pydicom` for `dicompylercore`. On an interpreter carrying it, six tests fail and the **shipped
  synthetic positive control returns all-NaN without raising**. Install into a clean environment.
  Declaring the conflict with a startup refusal is the highest-priority follow-up.
- `engine/VERSION` is a vestigial file reading `1.0.0` that nothing reads; the version-agreement
  gate does not check it. Queued for deletion rather than for a bump.

### Provenance note

The cohort runs that produced the evidence package for this release executed at commit
**`7f42c4d0`**,
which **predates this version bump**, so their `run_manifest.json` files carry the embedded string
`1.3.0`. That is not fixable retroactively and was deliberately not rerun. **The commit SHA
recorded in each manifest is the authoritative identifier** of what produced that artefact — not
the tag, and not the embedded version string. The non-test `engine/` tree is byte-identical across
`7f42c4d0`, `492fef9` and the tagged commit.

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

- **A multi-structure `dvh_txt` file no longer collapses to a single row.** With
  `preserve_canonical=False` — the legacy default — `_read_txt_structures` routed
  multi-structure files to the *single*-structure reader, which has no per-block boundary reset.
  It returned one row carrying the **last** structure's name over dose and volume data
  accumulated across every structure in the file, so the numbers on that row belonged to no
  structure at all. It now always uses `parse_multi_structure_dvh_text`; `preserve_canonical`
  controls naming only, never structure splitting. This matches the DICOM path, where colliding
  structures each survive as their own row.

  *Migration:* a caller that read one row per multi-structure file now gets one row **per
  structure**, so row counts rise and any index- or length-based assumption about the result
  breaks. Code that consumed the old single row was consuming a figure computed across mixed
  structures; there is no way to reproduce it, and it should not be reproduced.

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

- **The release workflow runs the frozen application before packaging it.** PyInstaller omits a
  module it cannot find with only a warning, so a successful freeze said nothing about what was
  inside it: the installer shipped with no `shap` while every release job stayed green, because
  nothing ever executed the frozen exe. The build now runs the exe's own self-test — a real DVH
  loaded into a live `QWebEngineView`, with the rendered DOM queried via JavaScript to confirm
  Plotly actually drew — and fails the job on a non-zero exit. `packaging/rbGyanX-qt.spec` had
  asserted the opposite of what it shipped; the comment now describes the artefact, and `shap` is
  listed in `excludes` so its absence is a guarantee rather than a side effect of the build's
  install line. The installer's own SHA-256 is now recorded in the build log as well, so a
  downloader can verify the binary independently; CI previously logged only the artifact zip
  digest, which says nothing about the `.exe` attached to a release.

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

- The two `[from manifest]` placeholders in the draft report resolved from the run manifest,
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

- External-validation tooling (`external_validation/`): a synthetic feature-table mirror,
  the benchmark runner and the ablation analysis. The dataset-acquisition scripts this
  originally shipped with were removed in v1.5.0 as study-specific.
- TG-263 structure normalization (`engine/config/tg263_aliases.py`).
- DICOM cohort adapter, reading a directory of DICOM-RT studies one patient per
  subdirectory (renamed from a collection-specific name in v1.5.0; the clinical
  covariate mapper it shipped with was a column map for one workbook and was removed).
- External-validation harness (`engine/validation/external_validation_harness.py`;
  renamed from a collection-specific name in v1.5.0).
- **Real DVH feature front-end** (`engine/dicom_io/cohort_features.py`) + analytic synthetic
  DICOM-RT factory (`tests/synthetic/dicom_rt_factory.py`); `cohort_features.csv` builder.
- **Four-class external benchmark** (`engine/validation/extval_benchmark.py`): classical,
  clinical, dosiomics ML, and LQ-constrained **PINN** (`engine/validation/outcome_pinn.py`)
  under centre-grouped CV, with AUC/Brier/H-L/ECE/calibration/DCA and optimism plots.
- Benchmark + ablation drivers, synthetic CI mirror (`external_validation/`), `extval` CI job.
- Multi-sheet outcome loader for a clinical workbook (removed in v1.5.0: its sheet and
  column names described one collection). Results in `docs/EXTVAL_RESULTS.md`,
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
