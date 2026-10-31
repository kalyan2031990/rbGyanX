# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] — sourced default NTCP parameters

**The scientific change of v1.5.0, kept separate from the code fixes on purpose.** Every value in
`engine/config/site_params_ntcp_default.yaml` now carries a per-model `provenance` block naming its
source, the table and page it was transcribed from, the endpoint it was fitted to, its dose basis,
and what the structure was in the paper. `as_printed` holds the numbers exactly as the paper prints
them and `conversion` states every derivation; the only derivation used is `geud_a = 1/n`, the
Kutcher-Burman DVH reduction the LKB probit model is defined on. **Values change. Numbers written
with v1.4.0 and earlier are not comparable with v1.5.0 output.**

Two papers were read and transcribed: **Burman et al., IJROBP 21:123-135 (1991), Table 1, p. 125**
and **Rancati et al., IJROBP 75:915-923 (2009), p. 919**.

### Changed — parameters now carry a citation

- **Spinal cord, at five sites.** `TD50` 45.0 → **66.5 Gy**, `m` 0.18 → 0.175 (Burman, myelitis /
  necrosis). The 45 Gy was a planning constraint, not a fit. `LUNG` and `PROSTATE` had no cord
  entry at all and now have one. `LIVER` already used 66.5 and gains the probit form, so all five
  sites finally agree.
- **Brain stem, at three sites.** `TD50` 53.0 → **65.0 Gy**, `m` 0.18 → 0.14, `n` 0.05 → **0.16**,
  `geud_a` 20.0 → 6.25. A threefold change in the volume effect, not only in TD50.
- **Larynx.** The unsourced log-logistic fit (`TD50` 44.0, `gamma50` 0.7) is replaced by
  **Rancati's LKB fit: `TD50` 47.3 Gy, `m` 0.23, `n` 1.17**, `geud_a` 0.855, for subacute/late
  grade >= 2 laryngeal edema scored by fiberoptic examination. Rancati fitted the EUD of EQD2 DVHs
  at alpha/beta 3 Gy, which is this organ's `alpha_beta_gy`, so the engine's EQD2 transform matches
  the fit.
- **Mandible.** Replaced by Burman's **TD50 72.0 Gy, m 0.10, n 0.07**. Read the endpoint before
  using it: the row is "TM joint and mandible" and the endpoint is **marked limitation of joint
  function**, not osteoradionecrosis. Both facts are on the value.
- **Esophagus, at four sites.** `TD50` 34.0 → **68.0 Gy**, with `m` 0.11, `n` 0.06 (Burman,
  clinical stricture / perforation). The old 34 Gy had no source and is about half Burman's, which
  is consistent with an acute-esophagitis threshold - **a different endpoint, and one v1.5.0 does
  not model.** `LIVER` had no esophagus entry and now has one.
- **Optic chiasm** `TD50` 55.0 → 65.0, **optic nerves** 54.0 → 65.0, both with `m` 0.14,
  `n` 0.25, `geud_a` 20.0 → 4.0 (Burman, blindness).
- **Brachial plexus** `TD50` 54.0 → 75.0, `m` 0.12, `n` 0.03, `geud_a` 33.33 (Burman, clinically
  apparent nerve damage).
- **Femoral heads** `TD50` 52.0 → 65.0, `m` 0.12, `n` 0.25 (Burman, necrosis; the structure is the
  femoral head **and neck**).
- **Rib** `TD50` 50.0 → 68.0, `m` 0.21, `n` 0.10, `geud_a` 20.0 → 10.0 (Burman, pathologic
  fracture; the reference volume is **one third of the rib cage**, not a single rib).
- **Stomach** `TD50` 68.0 → 65.0 with `m` 0.14, `n` 0.15 (Burman, ulceration / perforation).
- **Liver** `n` 0.97 → **0.32** and `geud_a` 0.97 → **3.125** (Burman, liver failure). TD50 and m
  already matched Burman; `geud_a` had been set to `n` rather than `1/n`, so the DVH reduction used
  the wrong quantity - registered as defect **#47**, found by the transcription itself.
- **Heart, lungs, normal brain and bladder** keep their TD50, which already equalled Burman's, and
  gain the `m` and `n` the log-logistic form cannot carry: heart 48.0 / 0.10 / 0.35, lung
  24.5 / 0.18 / 0.87 (`geud_a` 1.149, close to mean dose, as accepted for lung), brain
  60.0 / 0.15 / 0.25, bladder 80.0 / 0.11 / 0.5. `BRAIN_METS` had no normal-brain entry and now
  has one.

**Five probit blocks used to share the identical `m = 0.18, n = 0.05`** across SpinalCord,
BrainStem, BrachialPlexus, OpticChiasm and OpticNerve, at four sites. Five organs cannot share one
volume effect; Burman gives 0.05, 0.16, 0.03 and 0.25 for the same four. A test now refuses that
pair anywhere in the library.

### Added — `illustrative`, and BASIC mode refuses it

Twenty-one of fifty-seven organ entries have no citable source and are marked
`illustrative: true`. **BASIC mode refuses them**: the column is NaN and the row carries
`ILLUSTRATIVE_PARAMS_IN_BASIC_MODE`. ADVANCED mode computes them and labels every row with
`param_source` and `param_illustrative`. The refusal is per model, so an organ with a sourced
probit fit and an unsourced relative-seriality block keeps the first and loses the second.

**Note the consequence for the parotid**, which is the project's most-used organ: it keeps its
QUANTEC-consistent values (`TD50 28.4`, `geud_a 1`) but stays illustrative until Deasy et al. 2010
can be cited with a page, so **a BASIC-mode HN run reports no parotid NTCP**. The published cohort
runs use ADVANCED mode, where it is computed and labelled.

`site_params_ntcp_user.yaml` overrides are handled the same way: a model supplied without its own
provenance becomes unsourced, because the shipped citation described a different number.

### Changed — PELVIS P+ is refused as unsupported

`UTCP_OAR_MAP["PELVIS"]` lists six OARs and there is no `PELVIS` NTCP block at all, so none can be
scored. P+ for PELVIS is refused with the new reason **`UTCP_SITE_UNSUPPORTED`**, which
`allow_partial=True` deliberately does not override: a partial product means "score the organs I
have", and here there are none. Every other site in the map is now fully scorable - the five gaps
reported in the Tier A notes (LUNG and PROSTATE SpinalCord, BRAIN_METS NormalBrain, LIVER
Esophagus) were filled from Burman.

### Changed — ntcp_results.csv

Four columns are added, per model row: `param_source`, `param_illustrative`, `param_endpoint`,
`param_table_page`. Three organs lose their `NTCP_LKB_loglogit` value, which becomes NaN, because
the unsourced log-logistic block was replaced by a sourced probit fit: HN `Larynx`, HN `Mandible`
and `Esophagus` at all four sites.

### Measured on the HN cohort

At a uniform dose equal to each organ's own median mean dose in the TCIA2 head-and-neck cohort
(VMAT 4-arc arm, n = 116 patients, as recorded in the v1.3.0 run), which isolates the parameter
change from the DVH shape:

| Organ | median Dmean | NTCP before | NTCP after |
|---|---|---|---|
| Larynx | 34.6 Gy | 0.337 | **0.121** |
| Mandible | 33.6 Gy | 0.188 | **~0.000** |
| Esophagus | 5.2 Gy | 0.0052 | ~0.000 |
| SpinalCord | 14.7 Gy | 0.00009 | ~0.000 |
| BrainStem | 5.3 Gy | ~0.000 | ~0.000 |

The direction is consistent: the unsourced values were markedly more pessimistic than the published
fits. The per-patient cohort comparison over real DVHs comes with the v1.5.0 re-run.

### Tests

`engine/tests/test_v150_sourced_parameters.py` (49): the schema (every model block has provenance,
every provenance block declares all required fields, a sourced block names a page and an endpoint,
`as_printed` matches the shipped value, `geud_a == 1/n` for every sourced probit fit), the
transcription of 22 Burman values and the Rancati fit, the pinned illustrative inventory, and the
BASIC-mode refusal including the per-model case and the user-override case.

## [Unreleased] — Tier A: the defects that change written numbers

Thirteen output-affecting defects in `engine/`, each with a test that fails at v1.4.0 (`ffd69ef`)
and passes after the fix. **These change numbers.** Several change them on every run, so results
produced with v1.4.0 and earlier are not comparable with v1.5.0 output without the version
comparison that accompanies the release. Default NTCP parameters are deliberately **not** touched
here; they are proposed separately, with a source and page for every value, and await review.

### Fixed — values that were simply wrong

- **gEUD dropped every zero-dose bin (#45).** `compute_geud` masked `doses > 0`, so the
  unirradiated part of a partly covered target vanished and its gEUD read as the hot dose alone:
  for 50% of the volume at 0 Gy and 50% at 70 Gy, v1.4.0 returned **70.0 Gy** where the gEUD is
  35.0 (a = 1), 55.56 (a = 3) and 0.0 (a = −10). Zero-dose bins are kept. For a < 0 the
  generalised mean has no finite value when an occupied bin sits at 0 Gy, so the limit 0.0 is
  returned with the reason `GEUD_ZERO_DOSE_NEG_A`, carried to the TCP row as `gEUD_reason`. A
  structure that received no dose now reads 0 Gy instead of NaN — "no dose" and "not computable"
  are different statements.
- **The EPV guard counted the wrong class (#36).** It hard-coded `events = sum(y == 0)`, correct
  only for this project's own 0 = recurrence convention. On a cohort coded the other way round it
  counted the majority: for 12 events among 100 patients labelled 1 = event it reported **88
  events and EPV 44.0** instead of 6.0, so a model that should have been refused was waved
  through. `event_label` is now a required argument with no default and nothing inferred; a
  non-binary outcome and a label absent from the data are both refused. Threaded through every
  caller, including `extval_benchmark._run_c2`, whose own minority-class inference disagreed with
  the event count the same module reports.
- **Volume was lost through the structure mapper onto PRV expansions (#9, #19).** A
  planning-risk volume is the organ grown by a margin, so its DVH is colder and larger.
  `SpinalCord_05` and `BrainStem_03` carried no alias, fell through to fuzzy TG-263 matching and
  came back as the organ itself; `brainstemprv` was mapped onto the organ by the alias table
  outright. Measured on the TCIA2 cohort the organ and its own PRV collided in **121 of 121
  patients**, and spinal-cord NTCP differed **sevenfold** between the two, so which one was
  scored changed the published number. PRVs now get their own canonical key, `<Organ>_PRV`, with
  `is_prv` and `prv_of` on the mapping result, and are never scored with organ parameters unless
  the operator maps that key themselves.
- **Each SIB target is scored against its own dose level (#25).** A plan carries one
  `prescription_dose_gy`, so on a simultaneous integrated boost every target was given the
  highest level — a PTV56 was scored at 70 Gy, which overstates its TCP. The level is read from
  the `DoseReferenceSequence` item referencing the ROI or matching its description, else from the
  target's own name (`PTV63`, `PTV_5040_cGy`), else TCP is refused. `dose_level_gy` and
  `dose_level_source` are written on every row.
- **The manifest's seed did not drive the Monte Carlo (#6).** `RunnerConfig.seed` was recorded in
  `run_manifest.json` while `ParamUncertaintyConfig` and `NTCPUncertaintyConfig` both stayed at a
  hard-coded 42, so the manifest named a seed the run had not used. It is threaded through now,
  which means **cohort uncertainty bands change**: the manifest is true, and the cohort runner's
  own default seed is 0.

### Fixed — refusing instead of publishing

- **No prescription or fractionation is invented from a TPS text export (#4, #5).** The
  prescription fell back to the DVH maximum and the dose per fraction to a flat 2.0 Gy, with a
  logged warning beside the written number. A DVH maximum is not a prescription — it overstates
  the dose on a hot plan and understates it on a cold one — and 2 Gy per fraction is a guess about
  someone else's clinic. Both defaults are gone. TCP is refused with `RX_MISSING` /
  `FRACTIONATION_MISSING`; NTCP still runs, on physical dose, with `ntcp_dose_basis` saying so;
  and `--rx-gy` / `--n-frac` state what the header cannot. `RunConfig.dose_per_fraction` and
  `RunnerConfig.dose_per_fraction` default to `None` rather than 2.0.
- **TCP is refused outside the LQ model's validity range (#10).** A dose per fraction above
  `lq_valid_max_dpf_gy` only raised `lq_caution`. `LUNG_SBRT` at 18 Gy × 3 is an extrapolation, so
  TCP is now refused with `LQ_INVALID_DPF` unless `allow_lq_extrapolation=True` is passed
  explicitly. A refused row keeps its dose metrics.
- **A site with TCP parameters but no NTCP block reports rather than falls silent (#11).**
  `PROSTATE_SBRT` and `LUNG_SBRT` have no organs in `site_params_ntcp_default.yaml`, so
  `allowed_oar_names()` was empty, the OAR filter discarded every contour, and the run produced no
  NTCP rows and no reason — indistinguishable from a patient with no OAR contours. Each OAR now
  gets a row with NaN for every model, `definition_ok = False` and `NO_NTCP_PARAMS_FOR_SITE`.
- **P+ over an incomplete OAR set is refused (#20).** The UTCP OAR map had drifted from the
  canonical vocabulary: HN, BRAIN_GBM and BRAIN_METS said `Brainstem` where everything else says
  `BrainStem`, so **the brainstem was missing from P+ on every patient at three sites**; BREAST
  listed `Lung_Ipsi` and `Lung_Contra`, which both canonicalise to `LungTotal`, so one organ
  entered the product twice. Every entry is resolved through `canon_target()` and de-duplicated on
  the higher severity weight. Since P+ is a product over all the site's OARs, dropping one raises
  it, so an incomplete set gives NaN with `UTCP_INCOMPLETE_OAR_SET` and the missing organs named,
  unless `allow_partial=True`. `UTCP_OARs_scored` and `UTCP_OARs_missing` are on every row,
  including rows that got no UTCP at all.
- **An arbitrary tie-break between plans is refused (#18).** Plan selection ranked APPROVED, then
  latest, then SOPInstanceUID. When several plans are all UNAPPROVED with the same prescription and
  date, only the UID separates them — an accident of the archive that a re-export can reorder. Such
  a patient is refused with `AMBIGUOUS_PLAN_SELECTION`, the candidate labels are listed, and
  `--plan-label` or a per-patient override resolves it. Approval, a later date or a different
  prescription still separate plans without an operator.

### Fixed — saying what a number means

- **Every uncertainty band declares its coverage (#7).** `p5`–`p95` is a 90% interval and nothing
  on the row said so, while `utils/uncertainty_models.py` reports a genuine parametric 95% CI on a
  different path. Column names are unchanged; `band_level` is now on every aggregate — 0.90 in the
  engine, `confidence_level` in the utils path — and the two docstrings that had drifted are one.
- **EPV is printed to three significant figures (#35).** `{epv:.1f}` rendered a true EPV of 0.024
  as `EPV=0.0 < 5`, which reads as no events at all.
- **Organ-key reachability is measured against real contour names (#22).**
  `_validate_default_organ_keys_reachable()` asserted `canon_target(key) == key`, which compares
  the alias table with itself and passes however far it has drifted from what a planning system
  writes: `PharynxConst`, exported by **135 of 135** TCIA2 patients, went unmapped while the check
  was green. Reachability is now measured against `tests/fixtures/contour_name_corpus.txt` — 491
  real contour names harvested from this project's own recorded run provenance, **names only, with
  no identifier, date, dose or outcome**. 21 of 37 organ keys are reached; the 16 that are not are
  pinned by the test so the inventory cannot drift, 12 because the corpus covers only
  head-and-neck and prostate, and 4 because that cohort contoured the salivary glands side-lessly,
  which must not be given a side.

### Known gaps surfaced, not closed

- **Five UTCP sites list OARs their NTCP block cannot score**, so P+ at those sites is NaN by
  default: BRAIN_METS/NormalBrain, LUNG/SpinalCord (both fractionations), PROSTATE/SpinalCord,
  LIVER/Esophagus, and all six organs of PELVIS, which has no NTCP block at all. Supplying
  parameters is a scientific decision, so the inventory is pinned by a test rather than papered
  over.
- **`ITV50` maps to UNKNOWN** rather than a target: the dose-embedded-name pass covers the gtv,
  ctv and ptv prefixes and not itv. Pre-existing and out of Tier A's scope.

## [Unreleased] — the DICOM path through the desktop app

Three defects found by driving the Qt app over a synthetic DICOM-RT study. **All three sat in the
GUI and service layer; the engine beneath was correct throughout**, which is why they went
unnoticed — every written CSV carried the right numbers. **No published result is affected and no
analysis was rerun**: `engine/` is unchanged, and cohort runs go through
`rbgyanx_engine.cohort_runner`, which touches none of this.

### Fixed

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
  populated on **357 of 357** cohort rows instead of **0 of 357**, and `dose_selected` — a column
  that did not previously exist — on 357 of 357.
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

The three AFTER cohort runs that produced the evidence package executed at commit **`7f42c4d0`**,
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
  `preserve_canonical=False` — the SPARK configuration — `_read_txt_structures` routed
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
