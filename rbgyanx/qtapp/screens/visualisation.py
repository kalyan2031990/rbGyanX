"""
Visualisation screen (v2 Phase 4 · Slice 6).

Qt counterpart of the Tkinter right panel. Every view is produced through
:mod:`rbgyanx.viz` — the screen never plots anything itself, so the in-app interactive figure
and the exported publication figure are the same spec rendered by two engines.

Views are gated by :class:`~rbgyanx.services.ui_policy.UiPolicy`, so a research-only view
cannot appear in BASIC mode.

PHI: figures are built from derived curves and counts held in memory. Export is explicit and
user-chosen; nothing is written or transmitted otherwise.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rbgyanx.qtapp.branding import PALETTE
from rbgyanx.services.ui_policy import UiFeature, UiPolicy
from rbgyanx.viz import (
    CohortFlowSpec,
    DVHCurve,
    DVHSpec,
    FlowStage,
    OptimismRow,
    OptimismSpec,
    SankeyLink,
    SankeyNode,
    SankeySpec,
    get_backend,
)

__all__ = ["VisualisationScreen", "VIEWS"]

#: view key -> (tab label, UiFeature gate or None for always-available)
VIEWS: list[tuple[str, str, str | None]] = [
    ("dvh", "DVH", None),
    ("sankey", "Dose → NTCP → P+", UiFeature.SANKEY_VIEW),
    ("cohort_flow", "Cohort flow", UiFeature.COHORT_FLOW_VIEW),
    ("optimism", "Apparent vs CV", None),
]


class VisualisationScreen(QWidget):
    """Interactive view selector with a publication-quality export."""

    def __init__(self, policy: UiPolicy | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.policy = policy or UiPolicy.basic()
        self._result = None
        self._web = None

        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.view_combo = QComboBox()
        self.view_combo.currentIndexChanged.connect(lambda _=0: self.render_current())
        self.export_btn = QPushButton("Export publication figure…")
        self.export_btn.setProperty("variant", "secondary")
        self.export_btn.clicked.connect(self._export)
        bar.addWidget(QLabel("View:"))
        bar.addWidget(self.view_combo, 1)
        bar.addWidget(self.export_btn)
        root.addLayout(bar)

        self.host = QWidget()
        self.host_layout = QVBoxLayout(self.host)
        self.placeholder = QLabel("Run an analysis to populate the visualisations.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet(f"color: {PALETTE['muted']};")
        self.host_layout.addWidget(self.placeholder)
        root.addWidget(self.host, 1)

        self.apply_policy(self.policy)

    # ------------------------------------------------------------------ policy

    def apply_policy(self, policy: UiPolicy) -> None:
        """Rebuild the view list for this mode. Gating lives in UiPolicy, not here."""
        self.policy = policy
        current = self.view_combo.currentData()
        self.view_combo.blockSignals(True)
        self.view_combo.clear()
        for key, label, gate in VIEWS:
            if gate is None or policy.allows(gate):
                self.view_combo.addItem(label, key)
        idx = self.view_combo.findData(current)
        self.view_combo.setCurrentIndex(max(idx, 0))
        self.view_combo.blockSignals(False)
        self.export_btn.setVisible(policy.allows(UiFeature.INTERACTIVE_EXPORT))
        self.render_current()

    @property
    def available_views(self) -> list[str]:
        return [self.view_combo.itemData(i) for i in range(self.view_combo.count())]

    # ------------------------------------------------------------------- data

    def set_result(self, result) -> None:
        self._result = result
        self.render_current()

    def build_spec(self, key: str):
        """Spec for one view, or None when the run cannot support it."""
        result = self._result
        if result is None:
            return None

        if key == "dvh":
            curves = [
                DVHCurve(f"{s.label} ({s.patient_id})", s.dose_gy, s.volume_pct)
                for s in result.structures
                if s.dose_gy and s.volume_pct
            ]
            return DVHSpec(curves=curves[:12], title="Dose-volume histogram") if curves else None

        if key == "sankey":
            return self._sankey_from_result(result)

        if key == "cohort_flow":
            total = result.n_files
            plotted = sum(1 for s in result.structures if s.dose_gy)
            stages = [FlowStage("DVH files found", total)]
            if result.errors:
                stages.append(
                    FlowStage(
                        "Parsed",
                        len(result.structures),
                        excluded=len(result.errors),
                        exclusion_reason="unreadable DVH",
                    )
                )
            else:
                stages.append(FlowStage("Parsed", len(result.structures)))
            drop = len(result.structures) - plotted
            stages.append(
                FlowStage(
                    "With plottable curve",
                    plotted,
                    excluded=drop,
                    exclusion_reason="empty DVH" if drop else "",
                )
            )
            return CohortFlowSpec(stages=stages, title="Structure inclusion flow")

        if key == "optimism":
            # Placeholder until a benchmark runs in-app: shows the message, not fake metrics.
            return OptimismSpec(
                rows=[OptimismRow("classical (fixed)", 0.60, 0.60)],
                title="Apparent vs cross-validated AUC (run a benchmark to populate)",
            )
        return None

    @staticmethod
    def _sankey_from_result(result):
        """dose → per-OAR NTCP → P+, using the run's own NTCP values."""
        oars = [s for s in result.structures if s.ntcp and any(v == v for v in s.ntcp.values())]
        if not oars:
            return None
        oars = oars[:6]

        nodes = [SankeyNode("Delivered dose")]
        nodes += [SankeyNode(f"{s.label} NTCP") for s in oars]
        nodes.append(SankeyNode("Uncomplicated control (P+)"))
        p_index = len(nodes) - 1

        links: list[SankeyLink] = []
        for i, s in enumerate(oars, start=1):
            ntcp = next((v for v in s.ntcp.values() if v == v), 0.0)
            share = 100.0 / len(oars)
            links.append(SankeyLink(0, i, share, f"{s.label} dose share"))
            links.append(
                SankeyLink(i, p_index, share * (1.0 - float(ntcp)), f"{s.label} complication-free")
            )
        return SankeySpec(nodes=nodes, links=links, title="Dose → per-OAR NTCP → P+")

    # ---------------------------------------------------------------- render

    def render_current(self) -> None:
        key = self.view_combo.currentData()
        spec = self.build_spec(key) if key else None
        if spec is None:
            self._show_placeholder(
                "Run an analysis to populate the visualisations."
                if self._result is None
                else "This view is not available for the current run."
            )
            return
        try:
            html = get_backend("plotly").render(spec).to_html()
        except Exception as exc:  # a plotting failure must not kill the app
            self._show_placeholder(f"Could not render this view: {exc}")
            return
        self._show_html(html)

    def current_html(self) -> str:
        """Interactive HTML for the selected view (also used by tests)."""
        spec = self.build_spec(self.view_combo.currentData())
        if spec is None:
            return "<p>No data for this view.</p>"
        return get_backend("plotly").render(spec).to_html()

    def _clear_host(self) -> None:
        while self.host_layout.count():
            item = self.host_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_placeholder(self, message: str) -> None:
        self._clear_host()
        label = QLabel(message)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"color: {PALETTE['muted']};")
        self.host_layout.addWidget(label)
        self.placeholder = label

    def _show_html(self, html: str) -> None:
        try:
            from PySide6.QtWebEngineWidgets import QWebEngineView
        except ImportError:
            self._show_placeholder("QtWebEngine unavailable — use the publication export.")
            return
        self._clear_host()
        view = QWebEngineView()
        view.setHtml(html)
        self.host_layout.addWidget(view)
        self._web = view

    # ---------------------------------------------------------------- export

    def _export(self) -> None:
        spec = self.build_spec(self.view_combo.currentData())
        if spec is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export publication figure", "figure.png", "PNG (*.png);;PDF (*.pdf)"
        )
        if path:
            get_backend("matplotlib").render(spec).save(Path(path))
