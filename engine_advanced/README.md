# rbgyanx-advanced

ADVANCED-mode extensions for rbGyanX (CURSOR_FIXES Parts B & E).

- **B §16–18:** Clinical covariates merge, DVH shape features, model registry (core engine + PINN stub here)
- **B §19–20:** PINN scaffold and 3D dose pathway
- **E §27–28:** Dosiomics from OAR dose voxels (synthetic fallback when DICOM unavailable)

BASIC mode does not import this package. The GUI and `engine_bridge` set `RunConfig.mode="advanced"` only.

## Install

```bash
pip install -e ./engine
pip install -e ./engine_advanced
# Optional PINN training:
pip install torch
```

## Tests

```bash
cd engine_advanced
python -m pytest tests/ -q
```
