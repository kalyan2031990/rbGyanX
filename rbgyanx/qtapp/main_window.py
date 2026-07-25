"""
rbGyanX Qt shell — main window (v2 Phase 4 · Slice 3).

A thin **view** over :mod:`rbgyanx.services`: this module reads widgets and paints results; it
computes nothing. Two real screens are implemented end to end —

    Run      : choose input -> validate -> run -> live log/progress
    Results  : per-structure table + an embedded INTERACTIVE Plotly DVH (QWebEngineView)

BASIC vs ADVANCED follows the existing product split: BASIC is the clinic-safe subset;
ADVANCED exposes research controls (extra NTCP models, interactive export). Remaining screens
(Sankey, PRISMA cohort flow, live training view, SHAP) land in later commits.

PHI: nothing is written to disk by this window, and nothing is transmitted anywhere.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from rbgyanx.qtapp.branding import PALETTE, STYLESHEET, icon_path
from rbgyanx.qtapp.screens import AiPanelScreen, VisualisationScreen, WorkflowScreen
from rbgyanx.services.progress import CallbackReporter
from rbgyanx.services.run_controller import RunController, RunResult, StructureResult
from rbgyanx.services.run_request import RunRequest
from rbgyanx.services.ui_policy import UiFeature, UiPolicy

__all__ = ["MainWindow", "AppMode"]

APP_TITLE = "rbGyanX — radiobiology clinical decision support"

# NTCP model sets and feature gating live in rbgyanx.services.ui_policy (single authority).


class AppMode:
    BASIC = "BASIC"
    ADVANCED = "ADVANCED"


class _RunWorker(QThread):
    """Runs the controller off the UI thread so the window stays responsive."""

    line = Signal(str)
    stage = Signal(str)
    pct = Signal(float)
    done = Signal(object)

    def __init__(self, request: RunRequest, models: dict) -> None:
        super().__init__()
        self._request = request
        self._models = models

    def run(self) -> None:  # noqa: D102 - Qt entry point
        reporter = CallbackReporter(
            log=self.line.emit, status=self.stage.emit, progress=self.pct.emit
        )
        try:
            result = RunController(reporter).run_dvh_text(self._request, ntcp_models=self._models)
        except Exception as exc:  # never let a worker exception kill the app
            result = RunResult(ok=False, errors=[f"{type(exc).__name__}: {exc}"])
        self.done.emit(result)


class MainWindow(QMainWindow):
    """The application shell."""

    def __init__(self, mode: str = AppMode.BASIC) -> None:
        super().__init__()
        self.mode = mode
        self.policy = UiPolicy.from_name(mode)
        self._result: RunResult | None = None
        self._worker: _RunWorker | None = None

        self.setWindowTitle(APP_TITLE)
        self.resize(1180, 780)
        self.setStyleSheet(STYLESHEET)
        ico = icon_path()
        if ico:
            self.setWindowIcon(QIcon(str(ico)))  # existing rbGyanX branding

        self._build_menu()
        self.tabs = QTabWidget()
        self.workflow = WorkflowScreen(self.policy)
        self.workflow.run_requested.connect(self._start_run)
        self.tabs.addTab(self.workflow, "Workflow")
        self.tabs.addTab(self._build_run_tab(), "Run")
        self.tabs.addTab(self._build_results_tab(), "Results")
        self.visualisation = VisualisationScreen(self.policy)
        self.tabs.addTab(self.visualisation, "Visualisation")
        self.ai_panel = AiPanelScreen(self.policy)
        self.tabs.addTab(self.ai_panel, "Assistant")
        self.setCentralWidget(self.tabs)
        self._apply_mode()
        self.statusBar().showMessage("Ready")

    # ------------------------------------------------------------------ chrome

    def _build_menu(self) -> None:
        mode_menu = self.menuBar().addMenu("&Mode")
        for label in (AppMode.BASIC, AppMode.ADVANCED):
            act = QAction(f"{label.title()} mode", self, checkable=True)
            act.setChecked(label == self.mode)
            act.triggered.connect(lambda _=False, m=label: self.set_mode(m))
            mode_menu.addAction(act)
            setattr(self, f"_act_{label.lower()}", act)

        help_menu = self.menuBar().addMenu("&Help")
        about = QAction("About rbGyanX", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _about(self) -> None:
        QMessageBox.information(
            self,
            "About rbGyanX",
            "rbGyanX — radiobiology-guided clinical decision support.\n\n"
            "Research and education use. Not a certified medical device.\n"
            "Patient data stays on this machine: nothing is uploaded.",
        )

    # ------------------------------------------------------------------ run tab

    def _build_run_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)

        box = QGroupBox("Input")
        form = QVBoxLayout(box)

        row = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Folder of TPS DVH text exports…")
        browse = QPushButton("Browse…")
        browse.setProperty("variant", "secondary")
        browse.clicked.connect(self._pick_input)
        row.addWidget(QLabel("DVH folder:"))
        row.addWidget(self.input_edit, 1)
        row.addWidget(browse)
        form.addLayout(row)

        row2 = QHBoxLayout()
        self.source_combo = QComboBox()
        self.source_combo.addItems(["dvh_txt", "dicom"])
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["NTCP", "TCP", "BOTH"])
        self.ml_check = QCheckBox("Enable ML (needs clinical CSV)")
        row2.addWidget(QLabel("Source:"))
        row2.addWidget(self.source_combo)
        row2.addSpacing(16)
        row2.addWidget(QLabel("Endpoint:"))
        row2.addWidget(self.mode_combo)
        row2.addSpacing(16)
        row2.addWidget(self.ml_check)
        row2.addStretch(1)
        form.addLayout(row2)
        outer.addWidget(box)

        controls = QHBoxLayout()
        self.run_btn = QPushButton("Run analysis")
        self.run_btn.clicked.connect(self._start_run)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        controls.addWidget(self.run_btn)
        controls.addWidget(self.progress, 1)
        outer.addLayout(controls)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("Run log…")
        outer.addWidget(self.log, 1)

        self.mode_banner = QLabel()
        self.mode_banner.setAlignment(Qt.AlignmentFlag.AlignRight)
        outer.addWidget(self.mode_banner)
        return page

    def _build_results_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        split = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Structure", "Patient", "Mean dose (Gy)", "Volume (cm³)", "NTCP"]
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        split.addWidget(self.table)

        self.plot_host = QWidget()
        self.plot_layout = QVBoxLayout(self.plot_host)
        self.plot_placeholder = QLabel("Run an analysis to see the interactive DVH.")
        self.plot_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.plot_placeholder.setStyleSheet(f"color: {PALETTE['muted']};")
        self.plot_layout.addWidget(self.plot_placeholder)
        split.addWidget(self.plot_host)
        split.setSizes([260, 480])

        layout.addWidget(split)
        self.export_btn = QPushButton("Export interactive HTML…")
        self.export_btn.setProperty("variant", "secondary")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_html)
        layout.addWidget(self.export_btn, alignment=Qt.AlignmentFlag.AlignRight)
        return page

    # ------------------------------------------------------------------- mode

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.policy = UiPolicy.from_name(mode)
        for label in (AppMode.BASIC, AppMode.ADVANCED):
            getattr(self, f"_act_{label.lower()}").setChecked(label == mode)
        self._apply_mode()

    def _apply_mode(self) -> None:
        """Apply the CENTRAL policy to every surface; no local mode logic here."""
        policy = self.policy
        self.ml_check.setVisible(policy.allows(UiFeature.ML_TOGGLE))
        self.source_combo.setEnabled(policy.allows(UiFeature.INPUT_SOURCE_CHOICE))
        self.export_btn.setVisible(policy.allows(UiFeature.INTERACTIVE_EXPORT))
        if not policy.allows(UiFeature.INPUT_SOURCE_CHOICE):
            self.source_combo.setCurrentText("dvh_txt")
        self.mode_banner.setText(f"<b>{policy.name}</b> mode — {policy.banner().split('— ')[-1]}")
        if hasattr(self, "workflow"):
            self.workflow.apply_policy(policy)
        if hasattr(self, "visualisation"):
            self.visualisation.apply_policy(policy)
        if hasattr(self, "ai_panel"):
            self.ai_panel.apply_policy(policy)

    @property
    def models(self) -> dict:
        """NTCP model set for the active mode (from the central policy)."""
        return self.policy.models()

    # -------------------------------------------------------------------- run

    def _pick_input(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select DVH folder")
        if folder:
            self.input_edit.setText(folder)

    def build_request(self) -> RunRequest:
        """Widgets -> headless request (the only place the view touches the model)."""
        return RunRequest(
            analysis_mode=self.mode_combo.currentText(),
            input_path=Path(self.input_edit.text()) if self.input_edit.text() else None,
            output_dir=Path.cwd(),
            input_source=self.source_combo.currentText(),
            enable_ml=self.ml_check.isChecked(),
            basic_mode=self.mode == AppMode.BASIC,
        )

    def _start_run(self) -> None:
        request = self.build_request()
        validation = RunController().validate(request)
        if not validation.ok:
            QMessageBox.critical(self, "Validation Error", validation.message())
            return

        self.log.clear()
        self.progress.setValue(0)
        self.run_btn.setEnabled(False)
        self._worker = _RunWorker(request, self.models)
        self._worker.line.connect(self.log.appendPlainText)
        self._worker.stage.connect(self.statusBar().showMessage)
        self._worker.pct.connect(lambda f: self.progress.setValue(int(f * 100)))
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_done(self, result: RunResult) -> None:
        self._result = result
        self.run_btn.setEnabled(True)
        self.statusBar().showMessage(result.summary)
        self.populate_results(result)
        if result.ok:
            self.tabs.setCurrentIndex(1)
        else:
            QMessageBox.warning(self, "Run failed", "\n".join(result.errors[:8]) or "Unknown error")

    # ---------------------------------------------------------------- results

    def populate_results(self, result: RunResult) -> None:
        """Fill the table and render the embedded interactive DVH."""
        self.table.setRowCount(len(result.structures))
        for r, s in enumerate(result.structures):
            ntcp = ", ".join(f"{k}: {v:.3f}" for k, v in s.ntcp.items() if v == v)
            for c, text in enumerate(
                [s.label, s.patient_id, f"{s.mean_dose_gy:.2f}", f"{s.volume_cc:.1f}", ntcp]
            ):
                self.table.setItem(r, c, QTableWidgetItem(text))
        self.export_btn.setEnabled(
            bool(result.structures) and self.policy.allows(UiFeature.INTERACTIVE_EXPORT)
        )
        self._render_dvh(result)
        if hasattr(self, "visualisation"):
            self.visualisation.set_result(result)
        if hasattr(self, "ai_panel"):
            self.ai_panel.set_result(result)  # aggregate summary only; no per-patient rows

    def dvh_html(self, result: RunResult) -> str:
        """Interactive DVH as standalone HTML (also what the export button writes)."""
        from rbgyanx.viz import DVHCurve, DVHSpec, get_backend

        curves = [
            DVHCurve(f"{s.label} ({s.patient_id})", s.dose_gy, s.volume_pct)
            for s in result.structures
            if s.dose_gy and s.volume_pct
        ]
        if not curves:
            return "<p>No plottable DVH curves in this run.</p>"
        spec = DVHSpec(curves=curves[:12], title="Dose-volume histogram")
        return get_backend("plotly").dvh(spec).to_html()

    def _render_dvh(self, result: RunResult) -> None:
        html = self.dvh_html(result)
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:  # QtWebEngine unavailable -> keep the app usable
            self.plot_placeholder.setText(
                "QtWebEngine is not available; use “Export interactive HTML” instead."
            )
            return
        while self.plot_layout.count():
            item = self.plot_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        view = QWebEngineView()
        view.setHtml(html)
        self.plot_layout.addWidget(view)

    def _export_html(self) -> None:
        if not self._result:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export interactive DVH", "dvh.html", "*.html")
        if path:
            Path(path).write_text(self.dvh_html(self._result), encoding="utf-8")
            self.statusBar().showMessage(f"Wrote {path}")


def _selftest() -> int:
    """Headless end-to-end check of the packaged QtWebEngine stack.

    Builds a real interactive Plotly DVH and loads it into a live ``QWebEngineView``, then asks
    the rendered page (via JavaScript, in the QtWebEngine renderer process) whether a Plotly
    graph actually drew. This is the check that proves a *packaged* build ships a working
    QtWebEngine — the blank-plot class of bug only shows up once the helper process and ``.pak``
    resources have to be found on disk. Prints ``SELFTEST OK``/``SELFTEST FAIL`` and returns a
    process exit code; run it from the frozen exe with ``RBGYANX_QT_SELFTEST=1``.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()

    # Self-contained synthetic DVH -> a real interactive Plotly page. Deliberately does NOT read
    # any bundled data file: the check must prove the *rendering* stack, not data packaging.
    result = RunResult(
        ok=True,
        n_files=1,
        structures=[
            StructureResult(
                label="Parotid_L (selftest)",
                patient_id="SELFTEST",
                dose_gy=[float(d) for d in range(0, 71, 5)],
                volume_pct=[max(0.0, 100.0 - d * 1.4) for d in range(0, 71, 5)],
                mean_dose_gy=26.0,
            )
        ],
    )
    html = window.dvh_html(result)

    state: dict[str, object] = {"loaded": False, "plotly_nodes": -1}
    view = QWebEngineView()

    def _on_load(ok: bool) -> None:
        state["loaded"] = ok
        # Count Plotly's SVG containers in the live DOM — >0 means the plot really rendered.
        view.page().runJavaScript(
            "document.querySelectorAll('.plotly, .plot-container').length",
            lambda n: (state.update(plotly_nodes=n), app.quit()),
        )

    view.loadFinished.connect(_on_load)
    view.setHtml(html)
    QTimer.singleShot(20000, app.quit)  # never hang the build machine
    app.exec()

    nodes = state["plotly_nodes"]  # QtWebEngine returns JS numbers as float
    ok = bool(state["loaded"]) and isinstance(nodes, (int, float)) and nodes > 0

    # The bundled SHAP/xAI path: fit a tiny RandomForest, get real SHAP values, render a bar.
    # Proves shap is actually shipped and computes inside the frozen exe (not just importable).
    shap_ok, shap_note = _selftest_shap()
    ok = ok and shap_ok

    print(
        f"SELFTEST {'OK' if ok else 'FAIL'} "
        f"(loaded={state['loaded']}, plotly_nodes={state['plotly_nodes']}, "
        f"structures={len(result.structures)}, html_bytes={len(html)}, shap={shap_note})"
    )
    return 0 if ok else 1


def _selftest_shap() -> tuple[bool, str]:
    """Fit a small RandomForest, compute genuine SHAP values, render the xAI bar. Returns (ok, note)."""
    try:
        import numpy as np
        import shap
        from sklearn.ensemble import RandomForestClassifier

        from rbgyanx.viz import get_backend, shap_spec_from_values

        rng = np.random.default_rng(0)
        x = rng.normal(size=(60, 4))
        y = (x[:, 0] + 0.5 * x[:, 1] > 0).astype(int)  # signal in features 0 and 1
        rf = RandomForestClassifier(n_estimators=25, random_state=0).fit(x, y)
        sv = shap.TreeExplainer(rf).shap_values(x)
        if isinstance(sv, list):
            sv = sv[1]
        sv = np.asarray(sv)
        if sv.ndim == 3:  # some shap versions return (samples, features, classes)
            sv = sv[:, :, 1]
        spec = shap_spec_from_values(["dose", "volume", "age", "noise"], sv)
        html = get_backend("plotly").render(spec).to_html()
        return (len(html) > 500 and len(spec.features) == 4), "rendered"
    except Exception as exc:  # bundled-shap failure must be visible, not fatal to the whole test
        return False, f"FAILED:{type(exc).__name__}:{exc}"


def main(argv: list[str] | None = None) -> int:
    """Launch the Qt application."""
    import os

    if os.environ.get("RBGYANX_QT_SELFTEST") == "1":
        return _selftest()

    from PySide6.QtWidgets import QApplication

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("rbGyanX")
    ico = icon_path()
    if ico:
        app.setWindowIcon(QIcon(str(ico)))
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
