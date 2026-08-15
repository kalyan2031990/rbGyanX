# Data availability

rbGyanX is released as **software and results**. No patient data of any kind is distributed with it —
no DICOM, no dose grids, no contours, no clinical tables, no pseudonym maps.

## Validation cohorts (n = 283)

| Cohort | n | Role | Availability |
|---|---:|---|---|
| Parotid | 54 | internal validation, xerostomia G≥2 | **Not redistributable.** Identifiable institutional data under the governing ethics approval. Available to collaborators under a data transfer agreement; contact the corresponding author in `CITATION.cff`. |
| SPARK | 43 | external validation, no outcome linkage | **Not redistributable.** Same conditions. |
| TCIA-HN | 186 | external validation | **Public, obtain from the source.** The Cancer Imaging Archive, HNSCC and related head-and-neck RT collections. rbGyanX does not mirror them. |
| TCIA-Lung | 70 | **excluded entirely** | Never read, never counted, present in no analysis. |

The TCIA multimodal subset used for CT radiomics and dosiomics follows three separate denominators
that are never substituted for one another: **219** imaging-eligible → **127** outcome-linked → **114**
in the supervised modelling frame. See `analysis/FINAL_ANALYSIS_CODE_MANIFEST.json`.

## What *is* distributed

- **Source code** — the engine, the GUI, and `analysis/`, the scripts that produced every reported
  result, with per-analysis provenance in `analysis/FINAL_ANALYSIS_CODE_MANIFEST.json`.
- **Derived, aggregate results** — model performance, statistics, radiomics and dosiomics summary
  tables, posterior summaries, figures. These are cohort-level or feature-level aggregates; no row
  identifies a patient.
- **Synthetic test data on demand** — `scripts/make_synthetic_dicom_cohort.py` generates a complete,
  UID-consistent DICOM-RT study (CT + RTSTRUCT + RTPLAN + RTDOSE) from nested ellipsoids in a water
  background. It has no patient origin and exists so the pipeline can be exercised end to end
  without any real data. It is **test data, never a source of reported results** — see
  `docs/DOSIOMICS_DATA_PROVENANCE.md`.

## Privacy

Cohort identifiers are replaced by per-cohort pseudonyms. The pseudonym maps are held **outside** the
repository and are not published. No patient name, MRN, date of birth, accession number, institution
identifier or source filename bearing a name appears in any distributed file; the release build
scans for all of these and the scan report ships with the package.

## Reproducing the results

The published aggregates can be recomputed from the versioned scripts given the cohort data, which
must be obtained through the routes above. Seeds, package versions and configurations are recorded
per analysis in `analysis/FINAL_ANALYSIS_CODE_MANIFEST.json`; the environment and commands are in
`REPRODUCIBILITY_GUIDE.md`.

Without the restricted cohorts the TCIA-HN arm remains fully reproducible from public data; the
Parotid and SPARK arms are not, and no synthetic substitute for them is provided or implied.
