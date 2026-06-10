# rbGyanX synthetic test data (v1.0.0)

**Companion to:** https://github.com/kalyan2031990/rbGyanX  
**License:** MIT (software); synthetic clinical rows are simulated, not real patients.

## Contents

| Path | Description |
|------|-------------|
| `synthetic_cohort/` | 30-patient simulated NTCP/TCP clinical workbooks (`SyntheticClinicalDataGenerator`, seed 42) |
| `tests_synthetic/` | In-repo synthetic factories (TPS DVH, cohort, property tests) |
| `engine_synthetic_data/` | Engine unit-test DVH fixtures |
| `validation_report.json` | Latest automated validation summary from the authors' run |
| `pytest_results.txt` | Full pytest summary bundled with this archive |
| `requirements-lock.txt` | Pinned dependencies for reproducible installs |
| `DATA_INVENTORY.json` | File-count inventory of author real-data folders (no PHI) |

## Reproduce pytest (no real data)

```powershell
git clone https://github.com/kalyan2031990/rbGyanX.git
cd rbGyanX
.\scripts\install_dev.ps1
$env:PYTHONUTF8 = "1"
pytest --import-mode=importlib -q
```

Expected: **462 passed**, 3 skipped (GUI headless, optional validation_utils).

## Cite

Use the Zenodo DOI for this record **and** the GitHub repository DOI from `CITATION.cff`.
