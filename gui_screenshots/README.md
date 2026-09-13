# rbGyanX (Qt6) — GUI screenshots

Captures of the five main screens of the PySide6/Qt6 interface. All captured under
`QT_QPA_PLATFORM=offscreen` on the shipped **synthetic demo data**
(`examples/data/dvh_txt`) — **no patient data**.

**Resolution.** The files tracked here are 1600 px wide (~300 KB total), which is sufficient for
on-screen reading and keeps the clone small. The original 2× captures (3000×1900 px, ~1.4 MB) are
attached to the [v1.1.0 release](https://github.com/kalyan2031990/rbGyanX/releases/tag/v1.1.0) as
`rbGyanX-1.1.0-gui-screenshots-full-resolution.zip`, and are what should be used for print
figures. Both sets come from the same capture run; only the raster size differs.

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
