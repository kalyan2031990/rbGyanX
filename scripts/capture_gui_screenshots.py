"""
Capture high-resolution PNGs of the five v2 Qt screens for the manuscript.

Runs entirely under ``QT_QPA_PLATFORM=offscreen`` on the shipped **synthetic** demo data
(examples/data/dvh_txt) — no patient data is touched.

Two offscreen realities are handled explicitly:
  * the offscreen platform ships no font, so a real system font is loaded (else text is "tofu");
  * a QtWebEngine (Chromium) view composits to its own surface and grabs blank offscreen, so for
    the two plot screens the SAME spec is rendered through the Matplotlib viz backend (the viz
    API guarantees identical data) into a QLabel — a faithful still of the interactive view.

Usage:
    QT_QPA_PLATFORM=offscreen python scripts/capture_gui_screenshots.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "gui_screenshots"
EXAMPLES = ROOT / "examples" / "data" / "dvh_txt"
TMP = Path(os.environ.get("TEMP", "/tmp")) / "_rbgyanx_shot_plot.png"

from PySide6.QtCore import QEventLoop, Qt, QTimer  # noqa: E402
from PySide6.QtGui import QFont, QFontDatabase, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

from rbgyanx.qtapp.main_window import AppMode, MainWindow  # noqa: E402
from rbgyanx.services.run_controller import RunController  # noqa: E402
from rbgyanx.services.run_request import RunRequest  # noqa: E402
from rbgyanx.viz import get_backend  # noqa: E402


def _load_font(app: QApplication) -> None:
    for cand in ("C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(cand).exists():
            fam = QFontDatabase.addApplicationFont(cand)
            families = QFontDatabase.applicationFontFamilies(fam)
            if families:
                app.setFont(QFont(families[0], 10))
                return


def _pump(ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _inject_plot(layout, spec) -> None:
    """Replace a layout's contents with a Matplotlib still of ``spec`` (for web-view screens)."""
    get_backend("matplotlib").render(spec).save(TMP, dpi=200)
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
    label = QLabel()
    pix = QPixmap(str(TMP))
    label.setPixmap(pix.scaledToWidth(1000, Qt.TransformationMode.SmoothTransformation))
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)


def _grab(widget, path: Path) -> None:
    widget.repaint()
    _pump(150)
    widget.grab().save(str(path))
    print(f"  wrote {path.relative_to(ROOT)}")


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    _load_font(app)
    OUT.mkdir(exist_ok=True)

    win = MainWindow(AppMode.ADVANCED)
    win.setStyleSheet(win.styleSheet())  # re-apply with the loaded font
    win.resize(1500, 950)
    win.show()
    _pump(300)

    req = RunRequest(
        analysis_mode="NTCP", input_path=EXAMPLES, output_dir=ROOT, input_source="dvh_txt"
    )
    result = RunController().run_dvh_text(req, ntcp_models=win.models)
    win.visualisation.set_result(result)

    # Display a clean, portable path in the figures (the run above used the real path).
    demo_path = "examples/data/dvh_txt"

    # 1) Workflow -------------------------------------------------------------
    win.tabs.setCurrentWidget(win.workflow)
    win.workflow.input_edit.setText(demo_path)
    win.workflow.refresh_status()
    _pump(200)
    _grab(win, OUT / "01_workflow.png")

    # 2) Run (live progress) --------------------------------------------------
    win.tabs.setCurrentIndex(1)
    win.input_edit.setText(demo_path)
    win.progress.setValue(62)
    win.log.setPlainText(
        "Found 16 DVH file(s)\n"
        "[OK] EX-001_Parotid_L_dvh.txt\n"
        "[OK] EX-001_Parotid_R_dvh.txt\n"
        "[OK] EX-001_SpinalCord_dvh.txt\n"
        "Reading 10/16 …"
    )
    win.statusBar().showMessage("Reading 10/16")
    _pump(200)
    _grab(win, OUT / "02_run_live_progress.png")

    # 3) Results (DVH) — matplotlib still of the same DVH spec ----------------
    win.tabs.setCurrentIndex(2)
    win.populate_results(result)
    _inject_plot(win.plot_layout, win.visualisation.build_spec("dvh"))
    _pump(200)
    _grab(win, OUT / "03_results_dvh.png")

    # 4) Visualisation (Sankey) — matplotlib still of the Sankey spec ---------
    win.tabs.setCurrentWidget(win.visualisation)
    idx = win.visualisation.view_combo.findData("sankey")
    if idx >= 0:
        win.visualisation.view_combo.setCurrentIndex(idx)
    _inject_plot(win.visualisation.host_layout, win.visualisation.build_spec("sankey"))
    _pump(200)
    _grab(win, OUT / "04_visualisation_sankey.png")

    # 5) Assistant (ADVANCED AI panel) ---------------------------------------
    win.tabs.setCurrentWidget(win.ai_panel)
    win.ai_panel.set_result(result)
    win.ai_panel._append(
        "You", "Explain why the left parotid NTCP is higher than the right in this plan."
    )
    win.ai_panel._append(
        "rbGyanX",
        "In this synthetic plan the left parotid received a higher mean dose, and the LKB probit "
        "model rises steeply near TD50, so a few extra Gy translate into a noticeably higher "
        "NTCP. This explains the model output only — it is not a clinical recommendation.",
    )
    _pump(200)
    _grab(win, OUT / "05_assistant.png")

    win.close()
    if TMP.exists():
        TMP.unlink()
    print(f"\nCaptured {len(list(OUT.glob('*.png')))} screenshots to {OUT.relative_to(ROOT)}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
