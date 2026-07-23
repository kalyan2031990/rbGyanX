# rbGyanX de-identified real test cohort (v1.0.0)

**Companion to:** https://github.com/kalyan2031990/rbGyanX  
**Access:** Restricted — request via corresponding author (see software `CITATION.cff`).

## Contents

| Folder | Description |
|--------|-------------|
| `rbgyanx_test_data/clinical_data/` | HN toxicity / treatment parameter workbooks |
| `rbgyanx_test_data/HN57_OAR_Eclipse/` | HN57 OAR DVH (Eclipse export) |
| `rbgyanx_test_data/HN57_dDVH_CSV/` | HN57 differential DVH CSV |
| `rbgyanx_test_data/DICOM_samples/` | Small anonymised RT plan/dose/structure set |
| `rbgyanx_test_data/PTV_data/`, `kalpak_dcm_files/`, etc. | Additional integration subsets |

Validation run outputs (`_validation_*`, `_integration_*`) are **excluded** from this bundle.

## Layout on your machine

Extract to:

```
C:\Users\<you>\Desktop\input_folders\rbgyanx_test_data\
```

(or set `INPUT_ROOT` in `scripts/run_validation_report.py` / pass `--input-root` to inventory script).

## Reproduce author validation

```powershell
git clone https://github.com/kalyan2031990/rbGyanX.git
cd rbGyanX
.\scripts\install_dev.ps1
python scripts/run_validation_report.py
```

See `docs/TECHNICAL_DEVELOPMENT_NOTE.md` in the repository for interpreted results.

## Ethics

Do not redistribute outside approved collaborations. Synthetic-only reproduction does not require this archive.
