# rbGyanX GUI — BASIC vs ADVANCED (verified 1.0.0)

## Quick reference

| Item | BASIC (clinic) | ADVANCED (research) |
|------|----------------|---------------------|
| **Ask rbGyanX / LLM** | Off | On (Help menu) |
| **ML / SHAP / CCS** | Off by default | Available |
| **DICOM TCP+NTCP** | **Yes** — `rbgyanx-engine` | Yes (+ optional legacy ML) |
| **TPS text DVH** | Legacy Steps 1–3 | Full legacy + engine where applicable |
| **Uncertainty MC** | Off (`no_uncertainty`) | Configurable |

## Recommended clinic workflow (BASIC)

1. Launch app → choose **BASIC**.
2. Step 1: Input source **DICOM RT** → browse `test_data\dicom_input` or patient folder.
3. Analysis mode **TCP + NTCP**.
4. Output directory → any writable folder.
5. **Run Step 3** (Step 1 not required for DICOM engine path).
6. Review dashboard + `tcp_benchmarking.xlsx`, `ntcp_benchmarking.xlsx`, `plan_quality_summary.xlsx`.

## Version & help (auto-sync)

- Product version: **`VERSION.txt`** at project root.
- On startup: `feature_registry.json` is synced to that version.
- **Help → User Manual**: regenerates when version or registry is newer than the HTML manual.
- **About**: uses `VERSION.txt`, not stale registry `1.1.0`.

## Verify without opening GUI

```powershell
cd C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx
python scripts\verify_gui_modes.py
python qa\self_test_engine.py   # or Tools → Self-Test in GUI
```

## Known redundancy (by design for now)

- **Steps 1–2** vs **DICOM engine**: Steps 1–2 target TPS text; DICOM cohorts can skip to Step 3.
- **`analysis_mode`** vs **`analysis_type`**: legacy mirror; mode drives execution.
- **Novel features** (FDVH, uTCP checkbox, CCS): uTCP is computed by engine when TCP+NTCP on DICOM; checkboxes mainly affect legacy/subprocess paths.

Future UX pass: collapse to a single “Analysis path” selector (DICOM engine vs TPS legacy).
