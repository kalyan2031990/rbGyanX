# Known limitations and planned work

Recorded openly so that a reviewer or contributor does not have to discover them by reading the
tree. Each item is a real constraint on the current release, not a placeholder.

---

## Code structure

### `rbgyanx_gui.py` is a 9,093-line monolith

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

---

## Reporting an issue

Security-sensitive reports: see [`SECURITY.md`](../SECURITY.md). Everything else: please open an
issue with the release identifier from `VERSION.txt` and, where relevant, the analysis manifest
entry.
