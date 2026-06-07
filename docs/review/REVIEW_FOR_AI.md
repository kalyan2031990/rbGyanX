# rbGyanX — guide for AI / external code review

Read in this order:

| # | Document | Purpose |
|---|----------|---------|
| 1 | **`docs/TECHNICAL_DEVELOPMENT_NOTE.md`** | Architecture, lineage, validation posture, review focus |
| 2 | **`docs/RBGYANX_MANIFESTO.md`** | Product philosophy, safety, what the system must not do |
| 3 | **`docs/RBGYANX_1.0_DESKTOP.md`** | Clinician-oriented feature summary |
| 4 | **`docs/GUI_MODES_AND_HELP.md`** | BASIC vs ADVANCED, workflow |
| 5 | **`README.md`** | Install, build, quick commands |

## Core code paths (start here in the tree)

| Area | Path |
|------|------|
| GUI entry | `rbgyanx_gui.py` |
| Engine API | `engine/rbgyanx_engine/engine.py`, `pipeline.py` |
| DICOM + DVH IO | `engine/dicom_io/` |
| TCP / NTCP math | `engine/radiobiology/` |
| GUI → engine | `rbgyanx/logic/engine_bridge.py` |
| Input auto-detect | `rbgyanx/logic/input_router.py` |
| Clinical Excel | `clinical/clinical_adapter.py` |
| Legacy steps | `code1_dvh_preprocess.py` … `code7_tcp_ntcp_integration.py` |

## Automated checks (no patient data in repo)

```powershell
$env:RBGYANX_ENGINE_PATH = "$PWD\engine"
python -m pytest engine/tests/ -q
python scripts\verify_all_phases.py
```

`verify_all_phases.py` references **local** test folders under `input_folders\` on the developer machine; clone reviewers can skip those lines or substitute de-identified paths.

## What is intentionally excluded from Git

- `test_data/` — DICOM cohort (PHI risk, large binaries)
- `dist/`, `build/` — installers and PyInstaller output
- `docs/archive/` — Cursor prompts and internal session reports (not product docs)

## Build installer (optional)

```powershell
.\packaging\build_rbGyanX.ps1 -BuildInstaller
```

Output: `dist\rbGyanX-1.0.0-full-Setup.exe` (not committed).
