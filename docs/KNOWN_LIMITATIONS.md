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

### The ML models hard-code `n_jobs=-1`

The ML estimators and both `GridSearchCV` calls in
`engine/ml_models/{random_forest,xgboost,lgbm}_tcp.py` hard-code `n_jobs=-1`. On a 12-thread
machine this spawns worker processes that exhausted memory on an 8 GB workstation. `n_jobs` is not
exposed as a parameter; constrain it externally with `LOKY_MAX_CPU_COUNT` and `OMP_NUM_THREADS`.
Making it configurable is v1.4.

Both variables are needed, because the three libraries honour different ones. Measured on
Windows / Python 3.10 (joblib 1.6.0, LightGBM 4.7.0) by counting processes and threads during a
real nested-CV fit:

- `LOKY_MAX_CPU_COUNT=1` removes the joblib worker processes for `GridSearchCV` and the random
  forest, and it also sets LightGBM's thread count: LightGBM resolves `n_jobs=-1` via joblib's CPU
  count and ran on one thread whether or not `OMP_NUM_THREADS` was set.
- `OMP_NUM_THREADS=1` is what bounds XGBoost, whose booster reports `nthread=-1` either way. It
  also caps the numerical library's thread pool.

With both variables set to 1, each model chose the same hyperparameters as a less constrained
control (two joblib workers for the random forest, `OMP_NUM_THREADS` unset for XGBoost and
LightGBM). An uncapped run was not measured.
Record both variables in the run provenance of any result produced under them.

## Scientific scope

### NTCP default parameters: what is sourced, and what is only illustrative

Since v1.5.0 every value in `engine/config/site_params_ntcp_default.yaml` carries a per-model
`provenance` block naming its source, the table and page it was transcribed from, the endpoint it
was fitted to, the dose basis, and what the structure was in the paper. `as_printed` holds the
numbers exactly as the paper prints them, and `conversion` states every derivation; the only one
used is `geud_a = 1/n`, the Kutcher–Burman DVH reduction the LKB probit model is defined on.

Two papers were read for this release: **Burman et al., IJROBP 21:123–135 (1991), Table 1, p. 125**
and **Rancati et al., IJROBP 75:915–923 (2009), p. 919**.

**Values with no published source are marked `illustrative: true`, and BASIC mode refuses them.**
ADVANCED mode computes them and labels every row with `param_illustrative` and `param_source`.
Twenty-one of fifty-seven organ entries are illustrative, in two groups.

*Awaiting a paper the project has not yet obtained:*

| Organ | Value kept | What is needed |
|---|---|---|
| HN `Parotid_L`, `Parotid_R` | `TD50 28.4 Gy`, `gamma50 0.6`, `geud_a 1` | Deasy JO et al., IJROBP 76(3 Suppl):S58–S63 (2010) — QUANTEC salivary glands |
| PROSTATE `Rectum` | `TD50 76.9 Gy`, `m 0.14`, `n 0.12` | Michalski JM et al., IJROBP 76(3 Suppl):S123–S129 (2010) — QUANTEC rectum |
| BREAST `Thyroid` | `TD50 37.7 Gy`, `gamma50 0.7` | A fit from Bakhshandeh et al., IJROBP 85(2):514–521 (2013) is proposed and awaiting approval |

The parotid is the project's most-used organ, so note the consequence plainly: **in BASIC mode an
HN run now reports no parotid NTCP** until that citation is in place. ADVANCED mode, which is what
the published cohort runs use, computes it and labels it illustrative.

*No published fit located in the sources read:* HN `OralCavity`, `PharynxConstrictor`,
`Submandibular_L/R`; LUNG `ChestWall`; BREAST `LAD`; BRAIN_GBM `Pituitary`; `Hippocampus_L/R` and
`Cochlea_L/R` at both brain sites; PROSTATE `Urethra`; LIVER `Duodenum`. Each one's provenance
block says why. Two were deliberately *not* substituted from a near neighbour: Burman's "Small
intestine" row is not the duodenum, and its "Ear (middle/external)" rows are not the cochlea.

### The esophagus NTCP models stricture and perforation, not acute esophagitis

The esophagus now carries Burman's fit — `TD50 68 Gy`, `m 0.11`, `n 0.06`, endpoint **clinical
stricture/perforation**. The value it replaced, `TD50 34 Gy`, had no source and is about half
Burman's, which is consistent with an acute-esophagitis threshold rather than a late-stricture
TD50. **Acute esophagitis is therefore not modelled.** A run that needs it must supply its own
parameters in `site_params_ntcp_user.yaml`, where they will be marked illustrative unless their
own provenance is supplied with them.

### The mandible NTCP is a joint-function model, not osteoradionecrosis

Burman's row is **"TM joint and mandible"** with the endpoint **"marked limitation of joint
function"**. Both facts are recorded in `structure_definition` and `endpoint`, because a column
headed *mandible NTCP* will otherwise be read as osteoradionecrosis risk, which this is not. The
structure the fit assumes is the temporomandibular joint and the mandible together.

### Two structure definitions do not match a contoured volume

- **Spinal cord.** Burman's reference volume is a **20 cm length** of cord, not a contoured
  volume. The engine reduces whatever cord volume the DVH covers. The mismatch is recorded on the
  value and is not resolvable without a different published fit.
- **Rib.** Burman's reference volume is **one third of the rib cage** (p. 124: only tolerance
  doses for ⅓ of the rib cage were available), not a single rib. The organ key is `Rib`.

### PELVIS has an OAR map but no NTCP parameters, so P+ is refused

`radiobiology.utcp.UTCP_OAR_MAP["PELVIS"]` lists six OARs — Rectum, Bladder, FemoralHead_L/R,
BowelBag, SpinalCord — and `site_params_ntcp_default.yaml` has no `PELVIS` block at all, so none
of them can be scored. P+ for PELVIS is refused with `UTCP_SITE_UNSUPPORTED`, which
`allow_partial=True` deliberately does **not** override: a partial product means "score the organs
I have", and here there are none. Inventing parameters for a pelvic site is a scientific decision,
not a code fix. Every other site in the map is now fully scorable, and
`engine/tests/test_v150_utcp_oar_set.py` pins the inventory so it cannot drift either way.

### A user override drops the shipped citation

If `site_params_ntcp_user.yaml` supplies a model block without also supplying a `provenance` entry
for it, that model becomes unsourced and illustrative: the shipped citation described a different
number and must not be inherited by a new one. Supply your own provenance alongside your values to
keep a model sourced.

### Relative-seriality blocks were not part of the v1.5.0 parameter review

Three organs keep an `RS` block — HN `Parotid_L/R` and `SpinalCord`, LUNG `LungTotal` — and none of
them has a source. They are marked illustrative per model, so BASIC mode refuses the `NTCP_RS`
column for them while still computing the sourced `NTCP_LKB_probit` beside it.


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

### Two seeds, one manifest field — RESOLVED in v1.5.0 (defect #6)

Until v1.5.0, `run_manifest.json` recorded a `seed` from `RunnerConfig.seed` that was never passed
to the Monte-Carlo modules: `NTCPUncertaintyConfig` and `ParamUncertaintyConfig` both stayed at a
hardcoded 42, so a manifest asserting "this is the seed that produced these bands" was a false
provenance claim. Both results were deterministic — two fixed constants — but they were not the
constant the manifest named.

The seed is now threaded `RunnerConfig.seed` → `RunConfig.seed` →
`apply_uncertainty_and_hypoxia` / `apply_ntcp_uncertainty` → both MC configs, and is settable on
the CLI. **Band values from a cohort run therefore change between v1.4.0 and v1.5.0**, because the
seed that drives them is now the run's own (0 by default from `RunnerConfig`) rather than 42. The
manifest is true.

### Two interval conventions, one word: "band" — now declared on the row (defect #7)

`engine/uncertainty/ntcp_mc.py::_agg` and `parameter_mc.py::_aggregate_mc` — the source of every
cohort-run `uNTCP_*`/`uTCP_*` band — report **p5/p95, a 90% interval**.
`utils/uncertainty_models.py::UncertaintyAwareTCP` reports a genuine parametric confidence
interval via `confidence_level` (default `0.95`, p2.5/p97.5 — a real 95% CI). Both are correct for
what they claim to be, but until v1.5.0 nothing in either output said which was which, so a
cohort NTCP band and a UTCP figure could be compared as though they had the same coverage.

Every aggregate now carries **`band_level`**: 0.90 from the engine modules, `confidence_level`
from the utils path. The column names are unchanged on purpose, so nothing downstream breaks;
read `band_level` before comparing two bands. The two docstrings that had drifted apart are now
one shared text.

The limitation that remains is only this: the two conventions still coexist. Nothing forces a
downstream table or figure to print `band_level` beside the interval, so state the coverage
wherever a band is reported.

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

**Partly addressed in v1.5.0.** Two of the three ways this could hide are closed:

- A site with **no NTCP parameter block at all** (`PROSTATE_SBRT`, `LUNG_SBRT`) used to make
  `allowed_oar_names()` empty, so the filter discarded every contour and the run produced no NTCP
  rows and no reason. Those OARs are now discovered unfiltered and each gets a row with NaN for
  every model, `definition_ok = False` and `NO_NTCP_PARAMS_FOR_SITE` (defect #11).
- The reachability guard that was supposed to catch a mis-keyed organ was a tautology — it
  compared the alias table with itself. It is now measured against 491 real contour names from
  this project's own recorded runs, which is how `PharynxConst` (exported by 135 of 135 TCIA2
  patients, and unmapped while the guard was green) was found (defect #22).

What is **still** unaddressed: on a site that *does* have parameters, an ROI whose canonical name
is not among them is still dropped by a bare `continue` in `get_oar_structures()`, with no row and
no reason code. Surfacing that requires changing what `get_oar_structures()` and
`get_target_structures()` return — a structural change to a shared discovery path — and is not
part of v1.5.0.

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

### The NTCP applicability guard is blind on the DICOM path

`cohort_runner.py` calls `evaluate_ntcp_applicability(struct, "OAR", r.get("raw_name", struct))`.
On the DICOM path the NTCP row carries no `raw_name`: `collect_dicom_ntcp` sets `AnonPatientID`
and the site metadata but never copies `dvh_r.raw_name` onto the row, although `collect_dicom_tcp`
does exactly that for target rows and `collect_txt_ntcp` does it for text-path OAR rows. The
`r.get(..., struct)` fallback therefore hands the guard the canonical organ name *as* the raw name,
and `classify_definition()` compares the canonical against itself.

The guard consequently cannot distinguish an organ from its own PRV expansion — `SpinalCord` from
`SpinalCord_05`, which across 186 patients differ by a median of 19% and a maximum of 91% in NTCP
(see "PRV expansions canonicalise to the base organ name" below). It will not refuse a
planning-risk volume being reported as the organ, because it cannot see that it is one. This is a
false negative in the applicability check, on the primary supported input path.

The code change is two lines. The consequence is not: populating `raw_name` changes `definition_ok`
and `reason_codes` for DICOM rows in `ntcp_results.csv`, so existing NTCP output would gain
verdicts it does not currently carry, including refusals. Deferred to v1.4 with its own tests.

### Dosiomics require a real 3-D dose grid

Spatial dose texture is computed only where an RTDOSE grid exists. Planning-system DVH text
cohorts return a `NOT APPLICABLE` status rather than a feature vector. An earlier internal
analysis that synthesised texture features for such cohorts has been **retracted**; the current
engine refuses to fabricate `dosio_*` columns from synthetic voxels.

### Parotid laterality cannot be reconstructed from DVH text exports

Where a structure export carries a single parotid volume per patient, single-gland and bilateral
contouring conventions are indistinguishable. The engine's `Parotid_R` label in such cases is an
ordering artefact. The reporting name is `Parotid_unspecified` and affected rows carry
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
`PTV` yields `UNKNOWN`, on which the engine aborts.

**Shipped behaviour.** Measured on the current code against a 41-patient multi-structure prostate
cohort (all 41 processed, both arms): **0 of 41 complete without `--preserve-structure-canonical`,
and 0 of 41 with it.** Without the flag the 41 failures split by mechanism — **28
`SiteParamsUnavailable`** (an OAR name detected as `PELVIS`) and **13 `ValueError`** (site
`UNKNOWN`); with the flag all 41 are `ValueError`. Site detection is therefore not a partially
working path on this cohort: it fails for every patient, and the flag relocates the failure rather
than removing it.

`--site` makes detection inert as a failure source and is the current workaround: with
`--site PROSTATE --dose-per-fraction 2.0` the same 41 patients all complete, at the cost described
two entries below — every structure is coerced to a target, so no OAR receives NTCP. That arm also
shows the collision fix working: the same 41 patients yield **1,084 TCP rows on current code
against 369 before the fix** (26.4 versus 9.0 rows per patient), so **715 rows that previously
overwrote one another now survive as their own rows**.

*Historical, superseded:* before the v1.3.0 canonical-key collision fix, the un-flagged arm was
measured at **6 of 41 completed**. Those 6 were not successes — the fix showed they were single
rows onto which several colliding structures had collapsed. Both the count and its character
changed with the fix: what used to return a contaminated row now refuses. The 0-of-41 figure for
the flagged arm is unchanged.

Both arms were re-measured with identical inputs and flags so that code was the only variable;
outputs are in `02_Run_Outputs/v1_3_0_spark_post_b1_remeasure/`, alongside the pre-fix trees which
are kept as record. This cohort is a limitation probe only — no result from it is reported anywhere
else.

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

Every structure is coerced to a target type, so no OAR receives NTCP. Verified on current code
across all 41 patients of the multi-structure prostate cohort: **41 of 41 complete, 1,084 TCP rows
and 0 NTCP rows.** Since the v1.3.0 collision fix each structure is kept as its own row, which
also means OARs now appear as TCP rows labelled `PTV` — 920 of those 1,084 rows are `PTV` and 164
are `CTV`, against 360 and 9 before the fix, on the same input. The OARs are therefore not merely
absent from NTCP; they are present in TCP under a target label. Use
`--preserve-structure-canonical` for any file that contains OARs.

One caveat on auditing that: `raw_name` is blank in `tcp_results.csv` for every dvh_txt row, in
both the pre-fix and current runs, so which physical ROI produced a given row cannot be read from
that table alone. B.2 populated `raw_name` for the DICOM path; the text path's result table still
does not carry it.

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

### Eight analysis scripts match their recorded SHA-256 only with CRLF line endings

`analysis/FINAL_ANALYSIS_CODE_MANIFEST.json` records a SHA-256 for each script that produced a
reported result — that mapping is the whole point of the manifest, and it closed audit blocker B1.
Hashing the files as checked out, **15 of 23 match and 8 do not**:

```
analysis/radiomics/p14_ct_radiomics.py          analysis/pinn/v2_pinn.py
analysis/radiomics/p14_assemble_radiomics.py    analysis/cohort/t2_resolve_linkage.py
analysis/ibsi/v3_ibsi_benchmark.py              analysis/cohort/build_patient_features.py
analysis/dosiomics/real_dosiomics.py            analysis/bayesian/v3_bayesian_pymc.py
```

This was earlier recorded as drift of unknown origin. It is not a content change. All eight match
their recorded digests exactly once the file is converted from LF to CRLF: the manifest was stamped
on Windows line endings, and `.gitattributes` (`* text=auto eol=lf`) normalises the repository copy
to LF. Measured 2026-09-27 over all 23 entries: 15 match as LF, 8 match as CRLF, **0 match
neither**. So for every script, the manifest still identifies the exact code that produced the
reported numbers. What it does not identify is the byte form, which a verifier has to know is CRLF
for those eight.

`real_dosiomics.py` has since been changed in v1.3.0, for resume and skip reasons only. Its
manifest entry keeps the recorded digest (the version that produced the results) and adds
`sha256_v1_3_0` with a note stating what changed, rather than overwriting it. Re-stamping any entry
against the current file would make the hashes agree while destroying the evidence of which bytes
produced the results.

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
