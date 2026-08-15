# Dosiomics data provenance — real production dosiomics vs synthetic test data

This document exists because the two were once indistinguishable in the output tables. They are now
separated by construction, by a hard guard, and by regression tests.

## The distinction

| | REAL PRODUCTION DOSIOMICS | SYNTHETIC TEST DATA |
|---|---|---|
| Voxel source | the patient's RTDOSE grid, masked by the RTSTRUCT ROI | `numpy` normal draws around a chosen mean |
| `dose_source` label | `real_rtdose` | `synthetic_test_fixture` |
| May appear in a manuscript | **yes** | **never** |
| May be called "dosiomics" | yes | **no** — they are surrogates |
| Reachable in production | yes | no: requires an explicit `allow_synthetic=True` |
| Purpose | measurement | exercising the code path in tests and development |

## What went wrong before

`extract_oar_dose_volume(...)` ended with an unconditional fallback:

```python
if fallback_mean_dose_gy is not None and not math.isnan(fallback_mean_dose_gy):
    return synthetic_oar_dose_voxels(mean_dose_gy=fallback_mean_dose_gy)
return synthetic_oar_dose_voxels()
```

and the only production caller, `integration.attach_dosiomics_to_ntcp_results`, invoked it as
`extract_oar_dose_volume(None, None, organ, fallback_mean_dose_gy=mean_d)` — passing no RTDOSE path
at all. Every ADVANCED run therefore populated `dosio_*` columns from voxels generated around the
mean dose. Those features are a deterministic function of the mean dose and carry no spatial
information; they were **retracted** and are not the basis of any reported result.

## What the code does now

1. **Real RTDOSE is the only production source.** `integration.find_rt_files()` resolves the staged
   patient's RTDOSE and RTSTRUCT by modality, and the extractor masks the resampled grid with the
   ROI contour.
2. **No silent fabrication.** With no real grid, `extract_oar_dose_volume_with_source()` returns
   `(None, "NOT_AVAILABLE")` and logs a warning. `extract_oar_dose_volume()` returns `None`. The
   `fallback_mean_dose_gy` argument is inert unless synthetic mode is explicitly requested.
3. **Synthetic requires opt-in.** `allow_synthetic=True` must be passed by the caller. Nothing in a
   production pathway passes it, and the call logs loudly when it is used.
4. **A hard guard.** `assert_production_dose_source(source)` raises `SyntheticDoseInProductionError`
   for anything but `real_rtdose`. `extract_dosiomics_features(..., production=True)` applies it, and
   an omitted `dose_source` is treated as `NOT_AVAILABLE` rather than trusted.
5. **Rows are labelled.** Every NTCP row gets `dosiomics_status` (`OK` / `NOT_AVAILABLE`) and
   `dosiomics_source`. A patient without a real grid gets **no** `dosio_*` column at all, so a
   missing measurement is visibly missing instead of quietly filled.
6. **Tests both ways.** `engine_advanced/tests/test_dosiomics_production_safety.py` proves that a
   missing real dose yields no production dosiomics, and that explicit test mode still exercises the
   whole pipeline.

## Which engine produced which result

| Result | Engine | Location |
|---|---|---|
| Reported 3-D texture dosiomics, TCIA-HN n=186, 735 features (first-order 300, GLCM 180, GLRLM 120, GLSZM 135) | `real_dosiomics.py` against real RTDOSE grids | versioned at `analysis/dosiomics/real_dosiomics.py` |
| First-order dose statistics attached to NTCP rows in ADVANCED runs | `engine_advanced/rbgyanx_advanced/dose3d/dosiomics.py` | this module |

The manuscript dosiomics arm (AUC 0.682) comes from the first row. This module computes first-order
statistics only; it does not compute GLCM/GLRLM/GLSZM and does not claim to.

Parotid and SPARK are marked NOT APPLICABLE for dosiomics: those cohorts supply TPS DVH text, not a
3-D dose grid. That is a real limitation of the input data and is reported as such rather than being
filled with generated voxels.
