# rbGyanX — Cohort Runbook (PowerShell)

One command per cohort. Runs are **resumable** (re-run to continue after an interruption),
**idempotent** (re-running a finished cohort changes nothing), **deterministic** (same input →
byte-identical numeric CSVs), and **pseudonymised** (no PHI in the output tree).

> **PHI rule (C2):** the raw-ID ↔ pseudonym map is written to `--pseudonym-map-dir`, which **must be a
> folder OUTSIDE this repository** (it is the only place raw identifiers appear). The `Outputs/` tree and
> any `*_pseudonym_map.csv` are gitignored. Never commit them.

## One-time setup

```powershell
cd <path-to>\project_rbGyanx_latest
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -e .\engine -e ".[dev]"     # add ,ml for the ADVANCED research stack
$env:PYTHONUTF8 = "1"                    # UTF-8 console (also fixed at source; harmless to set)
```

## Output layout (written under `--output-root`)

```
Outputs\<InternalValidation|ExternalValidation>\<Cohort>\
    PatientLevel\<PSEUDONYM>\   per-patient summary + completion marker
    CohortLevel\                16 CSVs (see below) — the machine-readable results
    Figures\  QA\  Logs\        figures, QA, per-patient log records
    run_manifest.json           versions, git commit, config hash, seed, per-patient status
```

16 cohort CSVs (always written, even when empty): `patient_features, physical_metrics, tcp_results,
ntcp_results, plan_quality, site_detection, structure_mapping, dvh_summary, benchmark, ML_features,
ML_predictions, XAI_attributions, PINN_predictions, QA, cohort_summary, failures`.

---

## 1 — Parotid (internal, TPS DVH text)

```powershell
python scripts\run_cohort.py `
  --input-root  <PAROTID_DVH_TXT_FOLDER> `
  --cohort      Parotid `
  --output-root <OUTPUT_ROOT> `
  --validation  InternalValidation `
  --input-kind  dvh_txt `
  --site        HN `
  --pseudonym-map-dir <OUTSIDE_REPO>\_pseudonym_maps
```

## 2 — SPARK (internal, TPS DVH text)

```powershell
python scripts\run_cohort.py `
  --input-root  <SPARK_DVH_TXT_FOLDER> `
  --cohort      SPARK `
  --output-root <OUTPUT_ROOT> `
  --validation  InternalValidation `
  --input-kind  dvh_txt `
  --site        PROSTATE `
  --pseudonym-map-dir <OUTSIDE_REPO>\_pseudonym_maps
```

## 3 — TCIA Head-and-Neck (external, DICOM-RT, has CT)

```powershell
python scripts\run_cohort.py `
  --input-root  <TCIA_HN_DICOM_ROOT> `
  --cohort      TCIA_HN `
  --output-root <OUTPUT_ROOT> `
  --validation  ExternalValidation `
  --input-kind  dicom `
  --site        HN `
  --pseudonym-map-dir <OUTSIDE_REPO>\_pseudonym_maps
```

## 4 — TCIA Lung (external, DICOM-RT, may have NO CT)

```powershell
python scripts\run_cohort.py `
  --input-root  <TCIA_LUNG_DICOM_ROOT> `
  --cohort      TCIA_Lung `
  --output-root <OUTPUT_ROOT> `
  --validation  ExternalValidation `
  --input-kind  dicom `
  --site        LUNG `
  --pseudonym-map-dir <OUTSIDE_REPO>\_pseudonym_maps
```

Missing CT is **not** an error — such patients still process (`MISSING_CT` reason code, `degraded_mode =
FULL`). Patients with no dose or no structure set degrade to `NO_DOSE` / `NO_STRUCT` / `INSUFFICIENT` and
are recorded in `failures.csv` / `QA.csv`, never crashing the cohort.

---

## Expected console output

```
[rbGyanX] cohort=TCIA_HN kind=dicom → <OUTPUT_ROOT>\Outputs
  [1/121] TCIA_HN-0001: completed (3.2s), 9 structures
  [2/121] TCIA_HN-0002: completed (2.9s), 8 structures
  ...
[rbGyanX] done: {'cohort': 'TCIA_HN', 'completed': 118, 'skipped': 2, 'failed': 1, 'attempted': 121}
```

## Expected runtime (indicative; confirm from `Logs\*.json` after your first patients)

| Input | Per patient | Notes |
|---|---|---|
| TPS DVH text | ~0.2–0.5 s | no DICOM decode |
| DICOM-RT (basic) | ~2–5 s | dicompylercore DVH from the dose grid dominates |
| ADVANCED (`--mode advanced`) | +seconds–minutes | dosiomics/ML; PINN training only if explicitly enabled |

Phase-6 staged testing (`docs/VERIFICATION_REPORT.md`) reports measured timings on real cohorts.

## If a run is interrupted

Just run the **same command again.** Completed patients (those with a
`PatientLevel\<PSEUDONYM>\_COMPLETED.json` marker) are skipped and reported as `cached`; the run resumes
from where it stopped and rebuilds the cohort CSVs identically. To force a clean re-run of one patient,
delete that patient's `PatientLevel\<PSEUDONYM>\` folder; to re-run the whole cohort, delete the cohort
`Outputs\...\<Cohort>\` folder (the pseudonym map is preserved so pseudonyms stay stable).
```
