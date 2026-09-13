# Known limitations and planned work

Recorded openly so that a reviewer or contributor does not have to discover them by reading the
tree. Each item is a real constraint on the current release, not a placeholder.

---

## Code structure

### `rbgyanx_gui.py` is a 9,100-line monolith

The original Tkinter desktop application is a single module of roughly 9,100 lines (~396 KB). It
works, it is exercised by the GUI integration tests, and the service layer beneath it is properly
factored — but the file itself is too large to review comfortably and mixes widget construction,
event handling, threading and presentation logic.

This is a legacy-first artefact: the Tkinter app predates the Qt6 application
(`rbgyanx.qtapp`) and the headless service layer, both of which are cleanly separated. It is
retained because some users depend on it and because rewriting a working clinical-facing UI
carries its own risk.

**Planned split**, in dependency order:

1. `gui/widgets/` — pure widget construction, no business logic
2. `gui/controllers/` — event handling delegating to `rbgyanx.services`
3. `gui/workers/` — the threading and progress-streaming layer
4. `gui/app.py` — assembly only

The Qt6 application already follows this arrangement and is the reference. No behaviour change is
intended; `tests/test_gui_service_equivalence.py` exists specifically to pin the two front-ends to
identical service-layer results and should stay green throughout.

Contributors: please do not add new features to `rbgyanx_gui.py`. Add them to the service layer
and surface them in `rbgyanx.qtapp`.

### `run_analysis_pipeline` cannot execute its subprocess steps

`rbgyanx.logic.pipeline.run_analysis_pipeline` orchestrates the analysis by invoking the `code1`
through `code7` scripts as subprocesses. Those scripts live in `legacy/`, which is quarantined and
never imported, while the pipeline resolves them against the application root. Every step
therefore reports `Script not found` and the function returns `status='partial'` with four errors
rather than performing any analysis.

Until v1.3.0 this was masked by a worse defect: the function raised `UnboundLocalError` on its
first call in the default BASIC configuration, so nobody reached the subprocess stage. It now runs
to completion and degrades honestly, which is an improvement but not a working pipeline.

**Use the service layer instead.** `rbgyanx.services.run_controller.RunController` is the
supported entry point, is what both GUIs call, and is what the README quickstart demonstrates.
Reconnecting or retiring the subprocess pipeline is deferred work; it is an architectural change,
not a defect fix, and doing it properly means deciding whether the `code1`–`code7` lineage should
be revived at all.

---

## Scientific scope

### IBSI compliance is not claimed

The radiomics implementation is benchmarked against the IBSI-1 digital phantom and reproduces
**56 of 63** reference features. Two families reproduce only in part: neighbouring grey-level
dependence (3 of 7) and morphology (1 of 4). See
`analysis/ibsi/v3_ibsi_benchmark.py` and the compliance matrix it writes.

Compliance is a status; what this release supports is a benchmark measurement. Any downstream
radiomic result is bounded by the two partial families.

### Poisson TCP saturates

The Poisson linear-quadratic tumour-control implementation saturates at the dose levels present in
the validation cohorts (median indistinguishable from 1.000, negligible interquartile range). It
is correct at the doses it was designed for and is retained for completeness, but a saturated
probability carries no information and it should not be quoted as one.

### Delivery uncertainty is implemented but not propagated

Dosimetric (ICRU 91 / TG-119) and setup (van Herk) uncertainty modules are implemented and unit
tested, but were not propagated into the published cohort analyses because the archives carry no
per-patient setup data. Reported uncertainty spreads are **parameter uncertainty only** and
understate total uncertainty.

### Dosiomics require a real 3-D dose grid

Spatial dose texture is computed only where an RTDOSE grid exists. Planning-system DVH text
cohorts return a `NOT APPLICABLE` status rather than a feature vector. An earlier internal
analysis that synthesised texture features for such cohorts has been **retracted**; the current
engine refuses to fabricate `dosio_*` columns from synthetic voxels.

### Parotid laterality cannot be reconstructed from DVH text exports

Where a structure export carries a single parotid volume per patient, single-gland and bilateral
contouring conventions are indistinguishable. The engine's `Parotid_R` label in such cases is an
ordering artefact. The manuscript-facing name is `Parotid_unspecified` and affected rows carry
`NTCP_DEFINITION_UNVERIFIED`. No lateralised parotid result should be reported from these inputs.

### Cohort Consistency Score thresholds are uncalibrated

The 0.5 decision threshold is not an established boundary. CCS verdicts are directional signals,
not calibrated judgements.

### No SBRT-specific lung TCP parameter set has been adopted

`LUNG_SBRT` resolves to its own parameter object, but the values in it are the **conventional**
thoracic NSCLC parameters: TCD50 84.5 Gy, derived for conventional fractionation. Before v1.3.0
the key silently resolved to the `LUNG` entry, so a caller asking for SBRT parameters received
conventional ones with nothing saying so. The substitution is gone and the object now declares
what it carries, but the underlying gap is unchanged — no validated lung-SBRT parameter set has
been adopted, and none was invented to fill the hole.

`lq_valid_max_dpf_gy` is deliberately left at 10 Gy for this site so that typical SBRT
fractionation trips the LQ-validity guard rather than passing unremarked. Treat TCP for
`LUNG_SBRT` as indicative only. By contrast `PROSTATE_SBRT` does carry a genuinely distinct set
(TCD50 36.25 Gy vs 72.0 conventional); those values existed all along and were simply unreachable.

### `PELVIS` has no TCP parameters at all

A pelvic volume is treated as multi-target — cervix, endometrium, rectum, nodal volumes, with
different alpha/beta and clonogen assumptions per target — and no single published parameter set
applies. Requesting TCP for `PELVIS` raises `SiteParamsUnavailable` naming the reason; it does not
fall back to a nearby site. DVH, NTCP and UTCP scoring are unaffected. This is reachable from real
data: the DICOM site detector maps `PELVIS`, `CERVIX` and `ENDOMETRIUM` onto that key, so a pelvic
plan will be refused TCP rather than given a number of uncertain provenance.

---

## Reproducibility

### Two cohorts are not independently reproducible

The public head-and-neck analysis is fully reproducible from public archives. The internal parotid
and external prostate cohorts are institutional and cannot be redistributed; reproduction requires
a data-transfer agreement. De-identified derived tables sufficient to regenerate the reported
values accompany the associated publications.

### Analysis provenance and software release carry distinct commits

`analysis/FINAL_ANALYSIS_CODE_MANIFEST.json` stamps a different `source_commit` from the software
release tag. This is deliberate and should not be reconciled: which code produced a number and
which version was distributed are different questions.

### Eight analysis scripts no longer match their recorded SHA-256

`analysis/FINAL_ANALYSIS_CODE_MANIFEST.json` records a SHA-256 for each script that produced a
reported result — that mapping is the whole point of the manifest, and it closed audit blocker B1.
Recomputing those digests against the current files, **15 of 23 match and 8 do not**:

```
analysis/radiomics/p14_ct_radiomics.py          analysis/pinn/v2_pinn.py
analysis/radiomics/p14_assemble_radiomics.py    analysis/cohort/t2_resolve_linkage.py
analysis/ibsi/v3_ibsi_benchmark.py              analysis/cohort/build_patient_features.py
analysis/dosiomics/real_dosiomics.py            analysis/bayesian/v3_bayesian_pymc.py
```

The drift predates v1.3.0 — the files are byte-identical to their state at the v1.2.1 tag, so it
was introduced earlier and has not been reconciled. For those eight, the manifest no longer
identifies the exact bytes that produced the reported numbers, and the provenance claim is weaker
than the manifest's own wording implies. The digests of the remaining fifteen are intact.

This is recorded rather than repaired because there are only two honest repairs and both are
decisions for the authors, not a cleanup: re-run those analyses and re-stamp the manifest, or
restore the exact script versions the digests refer to. Silently re-stamping the manifest against
the current files would make the hashes agree while destroying the evidence that anything changed.

`analysis/` is excluded from linting and formatting for this reason — it is a frozen provenance
artefact, not maintained code.

### The AI assistant is explanation-only, and its guards are not a proof

The assistant added in this release is experimental, ADVANCED-only and off by default. Three
limits are worth stating plainly.

**The PHI guard fails closed, and still cannot prove a negative.** As of v1.3.0 a finding on
anything bound for a remote provider refuses the send outright, with no user override — text the
user typed themselves included. That is the right failure direction, and it is a real change from
v1.2.1, where the guard warned and transmitted anyway. What it is *not* is a guarantee. The guard
is a pattern matcher over an allow-list of shapes it recognises: DICOM field labels and UIDs, long
digit runs, dates, e-mail addresses, absolute paths, "Last, First" names. It cannot recognise a
patient described in prose, a nickname, an unusual institutional identifier format, or a rare
structure-label convention. A false positive costs a refused send; a false negative is a leak, and
no deny-list can demonstrate that none remain. **Use the Local provider for anything
patient-identifiable.** The block is a backstop for mistakes, not a licence to paste real data.

**The frozen set constrains the assistant, not a human.** Anyone with write access to the
installed source can remove any of it. It closes the path where an agent edits the numeric core
or the tests that verify it and then reports a green build; it is not a defence against a
determined operator.

**The shipped QUANTEC reference pack is orientation only.** Its entries are single-organ
constraints under conventional fractionation; they do not compose, they do not apply to SBRT,
re-irradiation or paediatric cases, and they are not a plan-acceptance standard. Sites should
ship their own pack rather than treat the shipped one as authoritative.

---

## Dependencies

### pydicom is pinned to a version with a known path-traversal advisory

`pydicom` is pinned `>=2.4,<3.0` because `dicompyler-core` 0.5.6 — the latest release — imports
`pydicom.pixel_data_handlers`, which pydicom 3.0 removed. Installing pydicom 3.0.2 makes
`import dicompylercore.dicomparser` fail outright; this was verified directly, not inferred.

pydicom 2.4.5 therefore carries **PYSEC-2026-2266**, a path traversal in the `FileSet` /
DICOMDIR API, fixed in 3.0.2. This codebase does not use that API — `FileSet`, `fileset`,
`DICOMDIR` and `ReferencedFileID` appear nowhere in it, and DICOM is read as individual files
through `DicomParser` and `dcmread` — so the exposure is nil rather than merely unlikely. The
advisory is accepted as a documented `pip-audit` exception. `SECURITY.md` states the full
justification and, importantly, what would invalidate it.

Lifting the pin requires replacing or vendoring `dicompyler-core`, which changes the DVH
ingestion path rather than a dependency version.

---

## Reporting an issue

Security-sensitive reports: see [`SECURITY.md`](../SECURITY.md). Everything else: please open an
issue with the release identifier from `VERSION.txt` and, where relevant, the analysis manifest
entry.
