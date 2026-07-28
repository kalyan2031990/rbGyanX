# rbGyanX v2 (Qt6) — GUI screenshots

High-resolution (2×, 3000×1900 px) captures of the five main screens of the PySide6/Qt6
interface, for the manuscript. All captured under `QT_QPA_PLATFORM=offscreen` on the shipped
**synthetic demo data** (`examples/data/dvh_txt`) — **no patient data**.

| File | Screen | Shows |
|------|--------|-------|
| `01_workflow.png` | Workflow | Global settings + the 7-step pipeline with live status (ADVANCED mode) |
| `02_run_live_progress.png` | Run | Live streaming run — progress bar and per-file log |
| `03_results_dvh.png` | Results | Per-structure NTCP table + the dose–volume histogram |
| `04_visualisation_sankey.png` | Visualisation | Dose → per-OAR NTCP → uncomplicated control (P+) Sankey |
| `05_assistant.png` | Assistant | ADVANCED-only AI panel with the data-safety notice (synthetic exchange) |

## Regenerating

```bash
QT_QPA_PLATFORM=offscreen python scripts/capture_gui_screenshots.py
```

Notes:
- The offscreen platform ships no font, so the script loads a system font (else text is "tofu").
- A QtWebEngine (Chromium) view composits to its own surface and grabs blank offscreen, so the
  two plot screens (Results, Visualisation) show the **same spec** rendered through the
  Matplotlib viz backend — the viz API guarantees the interactive and static renderings carry
  identical data, so these are faithful stills of the embedded interactive views.
