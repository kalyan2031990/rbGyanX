# Phase R2 complete (2026-05-29)

## rbGyanX_cdss (engine)

- **149 tests passed** (full suite)
- Package: `rbgyanx-engine` at `C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss`

## rbgyanx_dual (private GUI)

### Wired

1. **`rbgyanx/logic/engine_bridge.py`** — loads local engine, `run_engine_analysis()`, publishes outputs for code7
2. **`rbgyanx/logic/pipeline.py`** — `_run_tcp_analysis` / `_run_ntcp_analysis` use engine for DICOM + classical models
3. **`rbgyanx_gui.py`**
   - Input source: **DICOM RT** vs **TPS .txt** (secondary)
   - BASIC mode requires DICOM
   - Step 3 skips Step 1 when DICOM + engine available
   - Dashboard **Site Detection (engine)** card from `site_detection.csv`
4. **`requirements-engine.txt`** — editable install path to local repo

### Install engine for GUI

```powershell
pip install -e "C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss"
```

Or set `RBGYANX_ENGINE_PATH=C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss`.

### Usage

1. Select **DICOM RT** input source
2. Browse to DICOM folder (e.g. `py_tcpx_test_input\dicom_input`)
3. Run Step 3 (TCP / NTCP / both) — uses `rbgyanx-engine`, not code3/code6 subprocess

Legacy code3/code6 still runs for: TPS text-only, FDVH, uTCP, CCS, ML/SHAP.
