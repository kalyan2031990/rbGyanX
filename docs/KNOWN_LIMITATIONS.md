# rbGyanX — Known Limitations (honest register)

Written during the independent engineering verification. Everything here is either a real constraint, a
thing deliberately left off, or a thing not proven. Nothing is hidden to make the software look better.

---

## 1. Data-readiness limitations (found on the authors' own cohorts)

**1.1 The parotid source folder is not de-identified.**
`internal_validation_data_NTCP/input_txtdvh` — all 54 files carry a **real patient name** in the
`Patient Name` header. A de-identified equivalent exists (`validation_study/derived/parotid_deid`, names
reduced to a bracketed token). The runs were executed from the raw folder at the owner's explicit
instruction, relying on the runner's pseudonymisation; **no identifier reached any output** (verified by
an automatic scan plus an independent check across 79 harvested name tokens). The raw files themselves
remain identifiable and must not be shared.

**1.2 SPARK DVH files embed hospital MRNs.** All 81 plan-sum exports set `Patient Name` and `Patient ID`
to the same 7-digit MRN. Same mitigation and same verification result as 1.1.

**1.3 The TCIA/AIRTP archive is partially downloaded.** Two `.part` files (≈2.5 GB) are unfinished. The
extracted `HaN_valid` folders contain **RTPLAN + RTDOSE only**; the structure sets live inside the
collection zips. Analysis therefore ran from a selective extraction of the zips.

**1.4 The lung arm has no contours at all.** `Lung_valid_RTPLAN+RTDOSE.zip` contains plan and dose for
~70 patients but **no RTSTRUCT**, so DVHs — and hence TCP/NTCP — are impossible for that arm. It is
processed as a documented reduced mode (`NO_STRUCT`), not as a result. There is no runnable
"TCIA lung with structures" cohort in the supplied data.

**1.5 CT series were deliberately not extracted.** DVHs are computed from RTDOSE + RTSTRUCT; the CT is
unused. Skipping it reduced staging from 29.6 GB to 11.5 GB. If a future feature needs image data
(e.g. image-based dosiomics), the CT must be extracted.

## 2. Scientific limitations

**2.1 Side-less OAR names get an arbitrary laterality.** A structure named simply `Parotid`
canonicalises to `Parotid_R` purely by alias-lookup order. The numbers are still computed, but every
such row is flagged `NTCP_DEFINITION_UNVERIFIED`. **Do not treat those rows as left/right-specific.**
For the parotid cohort this applies to all 54 patients.

**2.2 NTCP parameter CVs are round-number defaults.** The Monte-Carlo coefficients of variation
(0.15/0.20/0.25/0.30) are attributed to Deasy 1997 / Marks 2010 / Källman 1992 but are not values with a
documented per-parameter derivation, and no parameter covariance is encoded.

**2.3 A divergent degenerate-value contract still exists.** `engine/radiobiology` returns **NaN** on
degenerate input; the parallel `rbgyanx/core/tcp/*` implementation returns **0.0** (~14 sites). The
latter is off the cohort critical path (self-imports only) and was **not** changed — a validated
calculation is not something to "improve" in an engineering pass. Flagged for the authors.

**2.4 TCP on prostate SPARK targets is model-limited, not verified.** TCP was produced for CTV/PTV using
the configured prostate parameters; no outcome data was used, so these are predictions, not validated
results. Same for all NTCP values reported.

**2.5 Structure-definition guards cover paired glands only.** PRV-vs-organ, partial-organ contours and
merged multi-organ contours other than the bilateral case are not modelled.

## 3. Engineering limitations

**3.1 The definition guard records, it does not withhold.** `NTCP_DEFINITION_MISMATCH` /
`_UNVERIFIED` appear in `ntcp_results.csv`; there is no strict mode that refuses to emit the number.

**3.2 ADVANCED-mode columns are empty by design in these runs.** `ML_features`, `ML_predictions`,
`XAI_attributions`, `PINN_predictions` are written (stable columns) but unpopulated because every cohort
ran in `basic` mode. Their population through the cohort runner is **not** exercised end-to-end.

**3.3 PINN is CPU-only here.** `torch 2.12.0+cpu`, no CUDA. Training is gated behind `pinn_train`
(default off) and ADVANCED mode. It was verified to import, train, checkpoint, reload and infer in the
test suite, but **PINN inference quality was not benchmarked** — only that it runs. **Not deleted.**

**3.4 Bayesian NTCP verified only at import/execution level.** Not exercised on the real cohorts.

**3.5 DICOM DVH monotonicity is trusted, not re-validated.** `validate_cumulative_dvh` guards the TPS
text path; DICOM DVHs are assumed monotone as produced by dicompylercore. Wiring the validator into the
DICOM path too would make the guarantee uniform.

**3.6 The `PatientRegistry` PHI columns still exist.** `build_dataframe()` can emit
`PrimaryPatientID`/`PatientDOB`/`StudyDate`/`Institution`. The cohort runner bypasses it entirely, but
**any other caller of that class can still export PHI**. Flagged, not changed (backward compatibility).

**3.7 Legacy duplication retained.** Seven-plus overlapping entry points and a second TCP implementation
remain (`docs/AUDIT.md` T1–T4). Nothing was deleted — capability preservation was a hard constraint.

**3.8 Grid-vs-DVH mean-dose cross-check is available but not wired into the runner.**
`dose_units_check.mean_dose_agreement` exists; the runner does not yet call it per structure.

## 4. What was *not* tested

- Vendor-specific private DICOM tags, multi-frame RTDOSE geometry mismatches, and beam-level dose
  accumulation (`DoseSummationType=BEAM`) — no such data was present.
- The full 48 GB TCIA archive (explicitly out of scope; the authors will run it).
- Any Windows environment other than this one (Python 3.14.2, Windows 11).
- GUI paths — the cohort runner is headless only.
