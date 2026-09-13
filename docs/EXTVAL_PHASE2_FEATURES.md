# External validation — Phase 2: real DVH + feature front-end

Phase 2 adds the missing real-data front door: given a DICOM-RT triple
`(RTSTRUCT, RTDOSE[, RTPLAN])`, produce per-structure DVHs and one tidy
`cohort_features.csv` row per patient. Builds on the verified Phase-1 baseline
(`docs/EXTVAL_BASELINE.md`); Phase-0 data facts in `docs/EXTVAL_DATA_READINESS.md`.

## 1. Critical dependency fix (blocked the entire real-DICOM path)

`dicompyler-core` 0.5.6 imports `pydicom.pixel_data_handlers`, **removed in
pydicom 3.0**. With pydicom 3.0.1 installed its import shim silently fell back to
the legacy **`dicom` (pydicom 0.9.x)** package — which was *declared as a
dependency* in `engine/requirements.txt`. The result: `dicomparser` resolved
`Dataset` to `dicom.dataset.Dataset`, so **no modern pydicom dataset was ever
recognised** and every real DVH extraction failed (empty error, swallowed).

Fix:
- pin `pydicom>=2.4,<3.0` in `pyproject.toml`, `requirements.txt`, `engine/requirements.txt`;
- **remove** the legacy `dicom>=0.9.9.post1` line from `engine/requirements.txt`
  (and uninstall it) with a comment warning against re-adding it;
- environment reconciled to pydicom **2.4.5**; the full test suite is unchanged
  (**487 passed / 3 skipped / 0 failed**) under the downgrade.

## 2. Feature front-end (`engine/dicom_io/cohort_features.py`)

`build_patient_features(rt_struct, rt_dose, rt_plan) -> dict` assembles one row.
It **reuses** the validated radiobiology numerics (no new dose–response math):
`DVHExtractor` (dicompyler-core DVHs + Dx/Vx/HI/CI), `compute_geud`, `bdvh`
(EQD2), `lq_model` (BED/EQD2), `compute_dvh_shape_features` (DVH dosiomics).

**Parsing rules implemented** (per Phase 0):
- one prescription PTV via name priority (`PTV70`, `PTVHighOPT`, …);
- dysphagia OARs selected by a raw-name alias map, because the TG-263 mapper
  leaves `PharynxConst`, `Parotids`, etc. unmapped — with the rules **skip `-PTV`
  planning-subtraction volumes** and **prefer the pure organ over a PRV
  expansion** (`SpinalCord` over `SpinalCord_05`);
- one plan-sum RTDOSE per patient (`DoseSummationType==PLAN`; selected in the driver).

**NaN contract:** empty / out-of-grid / zero-volume ROIs yield **NaN** metrics
(sourced from `compute_dose_metrics`, never the silent `0.0` of an empty DVH).

### Feature schema (one row/patient)
- Provenance: `patient_id, prescription_dose_gy, n_fractions, approval_status,
  dose_summation_type, n_targets, n_oars_mapped`.
- PTV target: `PTV_{name, volume_cc, D95_gy, D2_gy, D98_gy, Dmean_gy, gEUD_gy,
  HI, CI, BED_gy, EQD2_gy, dose_skewness, dose_kurtosis, dose_std_gy}`
  (gEUD a=−10; tumour α/β=10).
- Dysphagia OARs `{PharynxConstrictor, Larynx, OralCavity, Parotids,
  Submandibular, SpinalCord}` × `{Dmean_gy, Dmax_gy, gEUD_gy, EQD2mean_gy,
  V30Gy_cc, V50Gy_cc}` (OAR α/β from `bdvh`; cord gEUD a=12, others a≈1).

## 3. Synthetic DICOM-RT factory (`tests/synthetic/dicom_rt_factory.py`)

Replaces the previous stub with an **analytic** factory that builds a
`dicompyler-core`-consumable RTSTRUCT+RTDOSE+RTPLAN triple with a **uniform** dose
grid, so DVH metrics have an exact closed form
(`Dmin=Dmean=Dmax=D95=D2=gEUD=D0`, `HI=0`, `CI=1`). CI-safe; no patient data.

## 4. Tests (6 new; all green)

`tests/test_cohort_features.py`:
1. round-trip factory → feature row;
2. uniform-dose closed form (Dx, gEUD, HI, CI, and BED/EQD2 vs the LQ formula);
3. NaN-not-zero on an empty / out-of-grid ROI.

`tests/test_extval_cohort_builder.py`: plan-sum-over-beam dose selection;
multi-sheet outcomes loader with event coercion; end-to-end zip → `cohort_features.csv`.

## 5. Reproduce the real cohort table

RT files are read **directly from the zip** (CT slices skipped — DVHs need only
RTSTRUCT+RTDOSE), plan-sum dose selected per patient, outcomes joined by ID:

```powershell
python external_validation/build_cohort_features.py `
  --zip  ".../HNSCC/Radiotherapy_HaN_Lung_AIRTP/HaN/TCIA2_Head-Neck-PET-CT.zip" `
  --clinical ".../clinical_demographic_data/Head-Neck-PET-CT.xlsx" `
  --out  "<work_dir>/cohort_features.csv"
```

The output is a derived, de-identified feature table; **no patient DICOM is
written or committed**. Frame results as *association on reference-planned dose*.

<!-- COHORT_STATS -->
## 6. Realised cohort table (`external_validation/data/cohort_features.csv`, gitignored)

Built from all 121 dose+contour patients (0 build errors):

| Quantity | Value |
|---|---|
| Patients × columns | **121 × 69** |
| Centres | CHUM 45, HGJ 38, HMR 29, CHUS 9 |
| Loco-regional events | **20 / 121** |
| Distant / Death | 20 / 121 · **25 / 121** |
| PTV features complete | 100% (median gEUD 71.3 Gy, BED 86.1, HI 0.10) |
| Dysphagia-OAR features complete | 100% (Submandibular 99% = 120/121, matches 134/135) |
| Covariates | age/T/N 121/121; HPV 63/121 |

Endpoint and structure counts reproduce `docs/EXTVAL_DATA_READINESS.md` exactly.
The table is the input to the Phase-3 four-class benchmark.
<!-- /COHORT_STATS -->
