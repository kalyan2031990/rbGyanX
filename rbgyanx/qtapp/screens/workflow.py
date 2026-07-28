"""
Workflow & Settings screen (v2 Phase 4 · Slice 4).

Qt counterpart of the Tkinter left panel: global settings plus the six-step pipeline with
per-step status. A **view** only — step gating comes from
:class:`~rbgyanx.services.pipeline_state.PipelineExecutionState` (the same object the Tkinter
app uses) and feature visibility from :class:`~rbgyanx.services.ui_policy.UiPolicy`.

Nothing here decides policy locally, so BASIC/ADVANCED cannot drift between screens.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rbgyanx.qtapp.branding import PALETTE
from rbgyanx.services.pipeline_state import PipelineExecutionState
from rbgyanx.services.ui_policy import UiFeature, UiPolicy

__all__ = ["WorkflowScreen", "STEPS"]

#: The pipeline, mirroring the Tkinter step panel (label, state attribute).
STEPS: list[tuple[str, str]] = [
    ("Step 1 — DVH preprocessing", "step1_complete"),
    ("Step 2 — Dose metrics & plots", "step2_complete"),
    ("Step 3 — TCP analysis", "tcp_step3_complete"),
    ("Step 3 — NTCP analysis", "ntcp_step3_complete"),
    ("Step 4 — Uncertainty & consensus", "step4_complete"),
    ("Step 5 — Reports & QA", "step5_complete"),
    ("Step 6 — TCP/NTCP integration", "step6_complete"),
]

_STATUS_STYLE = {
    "done": f"color: {PALETTE['ok']}; font-weight: 600;",
    "pending": f"color: {PALETTE['muted']};",
    "blocked": f"color: {PALETTE['warn']};",
}


class WorkflowScreen(QWidget):
    """Global settings + the step list with live status."""

    run_requested = Signal()

    def __init__(self, policy: UiPolicy | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.policy = policy or UiPolicy.basic()
        self.state = PipelineExecutionState()
        self._step_labels: dict[str, QLabel] = {}

        root = QVBoxLayout(self)
        root.addWidget(self._build_settings())
        root.addWidget(self._build_steps())
        root.addStretch(1)
        self.apply_policy(self.policy)
        self.refresh_status()

    # ---------------------------------------------------------------- settings

    def _build_settings(self) -> QGroupBox:
        box = QGroupBox("Global settings")
        form = QFormLayout(box)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["NTCP", "TCP", "BOTH"])
        form.addRow("Analysis mode:", self.mode_combo)

        self.site_combo = QComboBox()
        self.site_combo.addItems(["HN", "PROSTATE", "LUNG", "BREAST", "BRAIN", "LIVER", "PELVIS"])
        form.addRow("Cancer site:", self.site_combo)

        self.source_combo = QComboBox()
        self.source_combo.addItems(["dvh_txt", "dicom"])
        form.addRow("Input source:", self.source_combo)

        self.input_edit, input_row = self._path_row("Folder of DVH text exports…")
        form.addRow("DVH input:", input_row)

        self.output_edit, output_row = self._path_row("Where results are written…")
        form.addRow("Output directory:", output_row)

        self.clinical_edit, clinical_row = self._path_row("Optional clinical CSV/XLSX…", file=True)
        form.addRow("Clinical data:", clinical_row)

        self.ml_check = QCheckBox("Enable ML models (requires clinical data)")
        form.addRow("", self.ml_check)

        self.mode_banner = QLabel()
        self.mode_banner.setAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("", self.mode_banner)
        return box

    def _path_row(self, placeholder: str, *, file: bool = False) -> tuple[QLineEdit, QWidget]:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        button = QPushButton("Browse…")
        button.setProperty("variant", "secondary")
        button.clicked.connect(lambda: self._browse(edit, file))
        row.addWidget(edit, 1)
        row.addWidget(button)
        return edit, holder

    def _browse(self, edit: QLineEdit, is_file: bool) -> None:
        if is_file:
            path, _ = QFileDialog.getOpenFileName(self, "Select file")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select folder")
        if path:
            edit.setText(path)

    # ------------------------------------------------------------------- steps

    def _build_steps(self) -> QGroupBox:
        box = QGroupBox("Pipeline")
        layout = QVBoxLayout(box)
        for label, attr in STEPS:
            row = QHBoxLayout()
            name = QLabel(label)
            status = QLabel()
            status.setAlignment(Qt.AlignmentFlag.AlignRight)
            self._step_labels[attr] = status
            row.addWidget(name, 1)
            row.addWidget(status)
            layout.addLayout(row)

        self.run_all_btn = QPushButton("Run all steps")
        self.run_all_btn.clicked.connect(self.run_requested.emit)
        layout.addWidget(self.run_all_btn)
        return box

    def refresh_status(self) -> None:
        """Repaint step status from the shared pipeline state."""
        for _label, attr in STEPS:
            done = bool(getattr(self.state, attr, False))
            widget = self._step_labels[attr]
            if attr == "step6_complete" and not self.state.can_run_step6() and not done:
                widget.setText("blocked — needs TCP and NTCP")
                widget.setStyleSheet(_STATUS_STYLE["blocked"])
                continue
            widget.setText("complete" if done else "not started")
            widget.setStyleSheet(_STATUS_STYLE["done" if done else "pending"])

    # ------------------------------------------------------------------ policy

    def apply_policy(self, policy: UiPolicy) -> None:
        """Show/hide research controls. The ONLY place this screen consults mode."""
        self.policy = policy
        self.ml_check.setVisible(policy.allows(UiFeature.ML_TOGGLE))
        self.source_combo.setEnabled(policy.allows(UiFeature.INPUT_SOURCE_CHOICE))
        if not policy.allows(UiFeature.INPUT_SOURCE_CHOICE):
            self.source_combo.setCurrentText("dvh_txt")  # clinic-safe path
        self.mode_banner.setText(f"<b>{policy.name}</b> — {policy.banner().split('— ')[-1]}")

    # ------------------------------------------------------------------ values

    def to_request_kwargs(self) -> dict:
        """Widget values as plain data for ``RunRequest`` (no toolkit types leak out)."""
        return {
            "analysis_mode": self.mode_combo.currentText(),
            "input_path": Path(self.input_edit.text()) if self.input_edit.text() else None,
            "output_dir": Path(self.output_edit.text()) if self.output_edit.text() else None,
            "clinical_file": (
                Path(self.clinical_edit.text()) if self.clinical_edit.text() else None
            ),
            "input_source": self.source_combo.currentText(),
            "enable_ml": self.ml_check.isChecked(),
            "basic_mode": not self.policy.is_advanced,
        }
