# rbGyanX verification report

**Date:** 2026-06-10  
**Scope:** Phases 0–5 professionalization (partial DICOM factory)

## Reproduce (zero env vars)

```powershell
.\scripts\install_dev.ps1
$env:PYTHONUTF8 = "1"
pytest --import-mode=importlib -q
pytest tests/synthetic -v
.\scripts\verify.ps1
```

## Python matrix

| Context | Versions |
|---------|----------|
| CI | 3.10, 3.11, 3.12 × ubuntu + windows |
| Installer / TF | 3.10 |
| Local dev | 3.14 best-effort |

## Test counts (target)

| Suite | Before | After (expected) |
|-------|--------|------------------|
| Full monorepo | ~436 | ~450+ |
| `tests/synthetic` | 0 | ~15+ |
| Skips | 3 | 3 (GUI, validation_utils) |

## Scientific decisions

1. **NaN contract:** NTCP primitives return `NaN` on degenerate input (not `0.0`).
2. **RS parametrisation:** YAML `gamma` = `gamma_eff`; see `docs/RS_PARAMETRISATION.md`.
3. **RS organ anchor:** NTCP = 0.5 at uniform D=D50 when **s = 1**; voxel P(D50) = 0.5 always.

## Coverage

- Gate: **≥70%** overall (raising to 85% as GUI/legacy paths gain tests)
- Radiobiology core: targeted via `engine/tests/test_ntcp_scientific_anchors.py` + publication suite

## CI

- `.github/workflows/ci.yml` — core job (no ML) + full job (optional stack)
- `.github/workflows/release.yml` — CITATION.cff validate + release artifact

## Known gaps

- Synthetic DICOM RT triple factory is a stub; e2e uses `tps_factory` (TPS txt DVH).
- TPS txt reader does not map OAR names for NTCP — DICOM required for OAR NTCP e2e.

## Author sign-off

- [ ] RS `gamma_eff` YAML naming accepted
- [ ] NaN contract change accepted for legacy code3 re-exports (still return 0.0 in `rbgyanx/core`)
