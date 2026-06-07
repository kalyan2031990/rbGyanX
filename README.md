# rbGyanX — radiobiology clinical decision support

[![GitHub](https://img.shields.io/github/stars/kalyan2031990/rbGyanX?style=social)](https://github.com/kalyan2031990/rbGyanX)

Windows desktop CDSS: DICOM RT + TPS DVH ingest, classical TCP/NTCP, UTCP, QUANTEC flags, plan-quality metrics. Optional ML/XAI in ADVANCED mode.

**Repository:** [github.com/kalyan2031990/rbGyanX](https://github.com/kalyan2031990/rbGyanX)

**Technical review:** [`docs/TECHNICAL_DEVELOPMENT_NOTE.md`](docs/TECHNICAL_DEVELOPMENT_NOTE.md) · [`docs/review/REVIEW_FOR_AI.md`](docs/review/REVIEW_FOR_AI.md)

## Layout

| Path | Role |
|------|------|
| `rbgyanx_gui.py` | Main GUI |
| `engine/` | `rbgyanx-engine` — clinic core (TCP, NTCP, DICOM, reporting) |
| `engine_advanced/` | ADVANCED Parts B & E (dosiomics, PINN registry, covariates) |
| `engine_advanced_f/` | ADVANCED Part F (Bayesian NTCP, PINN training) |
| `rbgyanx/` | Modes, engine bridge, input router |
| `code1`–`code7` | Legacy TPS / ML / integration steps |
| `tests/test_publication_suite.py` | 129-test software-paper validation suite |
| `packaging/` | PyInstaller + Inno Setup |

Patient DICOM and clinical files are **not** in this repository.

## Quick start

```powershell
git clone https://github.com/kalyan2031990/rbGyanX.git
cd rbGyanX
.\Install-rbGyanX.ps1
python rbgyanx_gui.py
```

## Verify (423 tests, synthetic data only)

```powershell
$env:RBGYANX_ENGINE_PATH = "$PWD\engine"
$env:PYTHONUTF8 = "1"
.\scripts\run_all_tests.ps1
```

Publication suite only:

```powershell
python -m pytest tests/test_publication_suite.py -v --tb=short
```

## Build installer (local only, gitignored)

```powershell
.\packaging\build_rbGyanX.ps1 -BuildInstaller
```

Requires Python **3.10** for the full TensorFlow bundle. Output: `dist\rbGyanX-1.0.0-full-Setup.exe`.

## Documentation

- [`docs/RBGYANX_1.0_DESKTOP.md`](docs/RBGYANX_1.0_DESKTOP.md) — desktop feature guide  
- [`docs/RBGYANX_MANIFESTO.md`](docs/RBGYANX_MANIFESTO.md) — philosophy and positioning  
- [`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md) — Parts A–F status  

Decision-support software — not a substitute for clinical judgment. MIT License.
