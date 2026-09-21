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

### Two seeds, one manifest field

Every `run_manifest.json` written by `scripts/run_cohort.py` records a `seed` value (default
`0`, from `RunnerConfig.seed`). That field is provenance metadata only — it is never passed to
the Monte-Carlo uncertainty module. The actual randomness behind every `uNTCP_*`/`uTCP_*` band
comes from a separately hardcoded `seed=42` in
`engine/uncertainty/ntcp_mc.py::NTCPUncertaintyConfig`, freshly instantiated (and therefore
reset) on every call via `pipeline.py`'s `NTCPUncertaintyConfig(n_samples=n_mc)`, which does not
override the seed. Results are deterministic and reproducible run to run — both seeds are fixed
constants — but a manifest asserting a seed that governs nothing is a false provenance claim if
read as "this is the seed that produced these bands." Neither seed is currently exposed on the
`rbgyanx-cohort` CLI. Unifying the two into one, CLI-settable seed is v1.4 work; this release
still ships with them separate, and this is the authoritative statement of that fact.

### Two interval conventions, one word: "band"

`engine/uncertainty/ntcp_mc.py::_agg` — the source of every cohort-run `uNTCP_*`/`uTCP_*`
band — reports **p5/p95, a 90% interval**. `utils/uncertainty_models.py::UncertaintyAwareTCP`
reports a genuine, parametric confidence interval via `confidence_level` (default `0.95`,
p2.5/p97.5 — a real 95% CI). Both are computed correctly for what they claim to be; neither
documented, until now, that the other exists or that they differ. A user comparing a
cohort-run NTCP band against a UTCP figure from the uncertainty-aware TCP path is comparing a
90% interval to a 95% one with nothing in either output saying so. State which convention is in
use wherever a band is reported downstream (tables, figures, manuscript text); do not assume
"the band" means the same coverage level across both modules.

### An unparameterised OAR is dropped silently, not refused

`get_oar_structures()` (`engine/dicom_io/structure_mapper.py`) excludes any ROI whose canonical
name isn't in the requested site's configured organ set with a bare `continue` — no warning, no
QA reason code, no row in `failures.csv`. The organ is indistinguishable in the output from that
patient simply never having had the structure. This was the mechanism behind a real defect (seven
organ keys in `site_params_ntcp_default.yaml` didn't string-match what `canon_target()` produces
for that organ — see below — so BrainStem NTCP silently never computed for any patient, in any
cohort, in any release before this fix); the keys are fixed, but the *mechanism* that let a fixed
config error hide with zero trace is unchanged. A structure a user has every reason to expect NTCP
for (it's a real ROI, the site has SOME organs parameterised) can still vanish without a mark if a
future config error, a new site, or a differently-named ROI hits the same silent-`continue` path.

Recording this as a proper refusal (an organ-level reason code, surfaced the same way a
patient-level refusal already is) requires changing what `get_oar_structures()` and
`get_target_structures()` return — a structural change to a shared discovery path, not a
parameter or a config fix, and not something to do in a release week alongside everything else
already changing in v1.3.0. Deferred to v1.4. The reachability guard added in v1.3.0 (see below)
prevents the *specific* class of defect that caused this from shipping silently again; it does not
make a silently-dropped OAR visible in a given run's output.

### Every shipped NTCP organ key is validated against `canon_target()` at import time

Added in v1.3.0 after the defect above was found: `config/site_ntcp_params.py` asserts, once at
module import, that every organ key in every site block of `site_params_ntcp_default.yaml`
resolves through `canon_target()` to itself as a recognised OAR. A mismatch now raises
`RuntimeError` immediately rather than silently dropping that organ's NTCP for every patient.
Covered by `engine/tests/test_ntcp_organ_key_reachability.py`, which also pins the three fixes
this found: `BrainStem` (was mis-cased `Brainstem` in HN/BRAIN_GBM/BRAIN_METS), `LungTotal` (was
two separate, both-unreachable keys `Lung_Ipsi`/`Lung_Contra` in BREAST — already parameterised
identically, so merging changed no computed value), and `FemoralHead_L`/`FemoralHead_R` (missing
a self-matching alias in `config/structure_aliases.py`, so `canon_target()` didn't recognise them
as OARs at all). This guard only covers the shipped default file — a user-supplied
`site_params_ntcp_user.yaml` is not validated, and can reintroduce the same class of defect for
whatever it overrides.

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
fractionation trips the LQ-validity guard — but tripping that guard switches the calculation to a
USC-corrected EQD2/BED (`lq_caution=True`, recorded per-row) and the engine **still returns a
TCP number**; it does not refuse. Confirmed directly, not just implied by the parameter table:
`engine/tests/test_radiobiology.py::test_poisson_usc_lowers_tcp_vs_lq` runs 54 Gy in 3 fractions
(18 Gy/fraction, SBRT-range) through `SITE_PARAMS["LUNG"]` and receives a finite TCP, not an
exception. Treat TCP for `LUNG_SBRT` as indicative only. By contrast `PROSTATE_SBRT` does carry a
genuinely distinct set (TCD50 36.25 Gy vs 72.0 conventional); those values existed all along and
were simply unreachable. Turning the LUNG_SBRT case into a refusal (matching how `PELVIS` behaves
below) would be a breaking behaviour change and is deferred to v1.4 with its own tests, not done
in this release.

### `PELVIS` has no TCP parameters at all

A pelvic volume is treated as multi-target — cervix, endometrium, rectum, nodal volumes, with
different alpha/beta and clonogen assumptions per target — and no single published parameter set
applies. Requesting TCP for `PELVIS` raises `SiteParamsUnavailable` naming the reason; it does not
fall back to a nearby site. DVH, NTCP and UTCP scoring are unaffected. This is reachable from real
data: the DICOM site detector maps `PELVIS`, `CERVIX` and `ENDOMETRIUM` onto that key, so a pelvic
plan will be refused TCP rather than given a number of uncertain provenance.

## TPS-text (dvh_txt) input

DICOM-RT is the supported input path. Planning-system DVH text exports are supported with the
limits below. Where a limit is marked rather than refused, the entry says so.
Use `--site` and `--dose-per-fraction` to state what the file cannot.

### Fractionation is assumed, not required

The no-substitution rule in the `site_params.py` docstring was applied to **site parameters** and
**not** to fractionation. When a text export omits total dose, fraction count or dose per
fraction, the reader substitutes (total dose = DVH maximum; dose per fraction = the configured
default, 2.0 Gy unless `--dose-per-fraction` is given; fraction count derived from the two) and
continues. As of v1.3.0 the assumption is **marked**: each result row carries
`total_dose_source`, `n_fractions_source` and `dose_per_fraction_source` (`parsed` only when every
input was stated in the file, otherwise `assumed`), and a warning naming the assumed values is
logged at read time. Refusing outright is v1.4 work; it would change existing behaviour.

### Per-structure site detection has no file-level context

`detect_site_from_text` runs per structure and uses that structure's own raw name as a stand-in
plan label. OAR names collide with `_PELVIS_KEYWORDS` (`RECTUM`, `BLADDER`), so an OAR is
detected as `PELVIS`, which has no TCP parameters and raises `SiteParamsUnavailable`; a bare
`PTV` yields `UNKNOWN`. Measured before the v1.3.0 collision fix, on a 41-patient multi-structure
prostate cohort: **6 of 41 completed without `--preserve-structure-canonical` and 0 of 41 with it**
— the flag relocates the failure rather than removing it. After the fix every structure is
detected separately, so the un-flagged path now fails loudly where it used to return a
contaminated single row (spot-checked on one patient file, n=1; not re-measured across the
cohort). `--site` makes detection inert as a failure source and is the current workaround.

### A structure-level exception fails the whole patient

An exception raised for one structure propagates out of `collect_txt_tcp` to the per-patient
handler in `cohort_runner.py`, discarding every other structure of that patient, including valid
targets. Scoping the failure to the structure is v1.4 work.

### PRV expansions canonicalise to the base organ name

`SpinalCord_05` maps to `SpinalCord`, so organ NTCP is ambiguous between the organ and its
planning-risk volume. Measured across 186 public-cohort patients: **median 19%, max 91%**
difference within colliding NTCP pairs. A PRV is a planning margin, not the organ. On the DICOM
path colliding structures are each kept as their own row and, from v1.3.0, `structure_mapping.csv`
records each row's `raw_name` and `roi_number`; downstream aggregation must choose between them by
a stated rule. Changing the naming policy is v1.4 work.

### `PROSTATE_SBRT` has TCP parameters but no NTCP block

`PROSTATE_SBRT` resolves to a distinct TCP parameter set, but `site_params_ntcp_default.yaml` has
no `PROSTATE_SBRT` site, so no organ receives NTCP under that key.

### `--site X` without `--preserve-structure-canonical` coerces every structure to a pseudo-target

Every structure is coerced to a target type, so no OAR receives NTCP. Verified: **0 NTCP rows
across all 41 SPARK patients** under that configuration. Since the v1.3.0 collision fix each
structure is kept as its own row (distinguishable by `raw_name`), which also means OARs now
appear as TCP rows labelled `PTV` (spot-checked on one patient file: 6 rows, n=1). Use
`--preserve-structure-canonical` for any file that contains OARs.

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

### The AI literature pack claims a generator that doesn't exist

`rbgyanx/ai/reference_packs/rbgyanx_lkb_defaults.json` declares
`"generated_from": "engine/config/site_params_ntcp_default.yaml"`, but no generator script exists
anywhere in the repository — it is a hand-maintained mirror of the yaml, guarded only by
`tests/test_ai_literature.py::test_the_lkb_pack_agrees_with_the_engine_yaml`. It drifted the
moment the yaml's organ keys were corrected in this release (see "Every shipped NTCP organ key is
validated..." above) and had to be hand-edited back into agreement. The test catches drift after
the fact; it does not make the `generated_from` claim true. This is the same defect class as the
stale analysis-manifest hashes above: a provenance statement the repository does not actually
back. **v1.4 work, not done here:** either write the generator the field claims exists, or remove
the `generated_from` field and say plainly that the pack is hand-maintained.

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
