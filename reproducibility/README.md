# rbGyanX reproduction package

This folder documents how to reproduce validation results and what to publish on **Zenodo** separately from the GitHub source code.

| Artifact | Where | Audience |
|----------|-------|----------|
| Source code + tests | [GitHub](https://github.com/kalyan2031990/rbGyanX) | Public |
| Synthetic test data + pytest log | Zenodo record **A** (public) | Anyone |
| De-identified real cohort | Zenodo record **B** (restricted) | Approved researchers |

## Build archives locally

```powershell
.\scripts\install_dev.ps1
.\scripts\build_zenodo_bundle.ps1
```

Outputs (gitignored):

- `reproducibility/dist/rbGyanX_synthetic_test_data_v1.0.0.zip`
- `reproducibility/dist/rbGyanX_real_test_data_v1.0.0.zip`

## Reproduce tests (synthetic only, no PHI)

```powershell
.\scripts\install_dev.ps1
$env:PYTHONUTF8 = "1"
pytest --import-mode=importlib -q
```

## Reproduce full validation (requires local real data)

Place cohorts under `input_folders/` (see `DATA_INVENTORY.json`), then:

```powershell
python scripts/run_validation_report.py
```

Results: `docs/validation_report.json`, `docs/TECHNICAL_DEVELOPMENT_NOTE.md`.

## Zenodo

Step-by-step upload instructions: [`ZENODO_UPLOAD_GUIDE.md`](ZENODO_UPLOAD_GUIDE.md).

After publishing, add the Zenodo DOI to `CITATION.cff` and tag a GitHub release.
