"""
AI assistant panel (v2 Phase 5 · Slice B).

ADVANCED-only, opt-in chat panel over :mod:`rbgyanx.ai`. Explains model outputs and drafts
notes/code; it makes no clinical recommendations.

Safety flow (see ``docs/PHASE5_AI_PANEL_DESIGN.md``):
  * gated by :class:`~rbgyanx.services.ui_policy.UiPolicy` — BASIC/clinic never sees it;
  * a persistent on-screen data-safety notice;
  * every send runs the PHI guard and shows what would leave the machine; the user confirms
    each send (the dialog names the provider and flags remote transmission). The guard WARNS,
    it does not block (owner policy);
  * nothing is written to disk or logged — the transcript lives in memory for the session only.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rbgyanx.ai import (
    PROVIDERS,
    AiConfig,
    LLMClient,
    LLMMessage,
    build_system_prompt,
    scan_for_phi,
    summarise_run,
)
from rbgyanx.qtapp.branding import PALETTE
from rbgyanx.services.ui_policy import UiFeature, UiPolicy

__all__ = ["AiPanelScreen"]

_SAFETY_NOTICE = (
    "⚠ Research assistant (ADVANCED). It explains outputs — it does not make clinical decisions. "
    "Text you send is transmitted to the selected provider; remote providers (Claude, Kimi) send "
    "it over the internet. Nothing is saved on this machine. Prefer the Local provider for "
    "anything patient-identifiable."
)


class _AskWorker(QThread):
    """Runs one blocking LLM exchange off the UI thread."""

    done = Signal(object)  # LLMResponse
    failed = Signal(str)

    def __init__(self, client: LLMClient, messages: list[LLMMessage]) -> None:
        super().__init__()
        self._client = client
        self._messages = messages

    def run(self) -> None:  # pragma: no cover - exercised via the live UI
        try:
            self.done.emit(self._client.complete(self._messages))
        except Exception as exc:
            self.failed.emit(str(exc))


class AiPanelScreen(QWidget):
    """Chat panel for the ADVANCED research assistant."""

    def __init__(
        self,
        policy: UiPolicy | None = None,
        parent: QWidget | None = None,
        transport=None,
    ) -> None:
        super().__init__(parent)
        self.policy = policy or UiPolicy.basic()
        self._result = None
        self._history: list[LLMMessage] = []  # in-memory only; never persisted
        self._transport = transport  # injectable; real HTTP transport built lazily otherwise
        self._worker: _AskWorker | None = None

        root = QVBoxLayout(self)

        self.notice = QLabel(_SAFETY_NOTICE)
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet(
            f"background: {PALETTE['surface']}; color: {PALETTE['text']};"
            f" border-left: 4px solid {PALETTE['warn']}; padding: 8px; border-radius: 4px;"
        )
        root.addWidget(self.notice)

        bar = QHBoxLayout()
        self.provider_combo = QComboBox()
        for key, prov in PROVIDERS.items():
            self.provider_combo.addItem(prov.label, key)
        self.provider_combo.currentIndexChanged.connect(lambda _=0: self._refresh_status())
        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("model (blank = provider default)")
        bar.addWidget(QLabel("Provider:"))
        bar.addWidget(self.provider_combo)
        bar.addWidget(QLabel("Model:"))
        bar.addWidget(self.model_edit, 1)
        root.addLayout(bar)

        from PySide6.QtWidgets import QCheckBox

        self.attach_context = QCheckBox("Attach the current run's aggregate summary")
        self.attach_context.setChecked(True)
        root.addWidget(self.attach_context)

        self.status = QLabel()
        self.status.setStyleSheet(f"color: {PALETTE['muted']};")
        root.addWidget(self.status)

        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText("The conversation appears here (not saved).")
        root.addWidget(self.transcript, 1)

        entry = QHBoxLayout()
        self.input_edit = QLineEdit()
        self.input_edit.setPlaceholderText("Ask about an NTCP value, draft a QA note…")
        self.input_edit.returnPressed.connect(self._on_send)
        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send)
        entry.addWidget(self.input_edit, 1)
        entry.addWidget(self.send_btn)
        root.addLayout(entry)

        self.apply_policy(self.policy)

    # ------------------------------------------------------------------ policy

    def apply_policy(self, policy: UiPolicy) -> None:
        self.policy = policy
        allowed = policy.allows(UiFeature.AI_PANEL)
        for w in (
            self.provider_combo,
            self.model_edit,
            self.attach_context,
            self.input_edit,
            self.send_btn,
        ):
            w.setEnabled(allowed)
        if not allowed:
            self.status.setText("The AI assistant is available in ADVANCED mode only.")
        else:
            self._refresh_status()

    @property
    def is_enabled(self) -> bool:
        return self.policy.allows(UiFeature.AI_PANEL)

    # -------------------------------------------------------------------- data

    def set_result(self, result) -> None:
        self._result = result

    def current_provider(self) -> str:
        return self.provider_combo.currentData() or "local"

    def current_config(self) -> AiConfig:
        model = self.model_edit.text().strip() or None
        return AiConfig.from_env(self.current_provider(), model=model)

    def _refresh_status(self) -> None:
        cfg = self.current_config()
        if not cfg.is_remote:
            self.status.setText("Local endpoint — nothing leaves this machine.")
        elif cfg.is_ready:
            self.status.setText(
                f"Remote ({cfg.preset.label}) — key found. Sends leave this machine."
            )
        else:
            env_names = " or ".join(cfg.preset.api_key_env)
            self.status.setText(f"Remote ({cfg.preset.label}) — set {env_names} to enable.")

    # ---------------------------------------------------------------- messages

    def build_messages(self, user_text: str) -> list[LLMMessage]:
        """System prompt (+ optional aggregate context) + history + this turn."""
        messages: list[LLMMessage] = [LLMMessage("system", build_system_prompt())]
        if self.attach_context.isChecked() and self._result is not None:
            summary = summarise_run(self._result)
            if summary:
                messages.append(LLMMessage("system", summary))
        messages.extend(self._history)
        messages.append(LLMMessage("user", user_text))
        return messages

    def outgoing_preview(self, user_text: str):
        """What would leave the machine (system prompts excluded) + PHI findings."""
        messages = self.build_messages(user_text)
        text = "\n".join(m.content for m in messages if m.role != "system")
        return text, scan_for_phi(text)

    def run_exchange(self, user_text: str, transport=None):
        """Synchronous core: build → complete → record. Used by the worker and by tests.

        No file/network side effects beyond the transport itself; history is in-memory only.
        """
        messages = self.build_messages(user_text)
        client = LLMClient(self.current_config(), transport=transport or self._make_transport())
        response = client.complete(messages)
        self._history.append(LLMMessage("user", user_text))
        self._history.append(LLMMessage("assistant", response.text))
        return response

    def _make_transport(self):
        if self._transport is not None:
            return self._transport
        from rbgyanx.ai.http_transport import HttpTransport

        return HttpTransport()

    # ------------------------------------------------------------------ send UI

    def _on_send(self) -> None:
        if not self.is_enabled:
            return
        user_text = self.input_edit.text().strip()
        if not user_text:
            return
        cfg = self.current_config()
        if not cfg.is_ready:
            QMessageBox.warning(self, "Not configured", self.status.text())
            return
        preview, findings = self.outgoing_preview(user_text)
        if not self._confirm_send(cfg, preview, findings):
            return
        self._dispatch(user_text)

    def _confirm_send(self, cfg: AiConfig, preview: str, findings) -> bool:
        where = (
            f"the REMOTE provider {cfg.preset.label} — this leaves your machine over the internet"
            if cfg.is_remote
            else f"the LOCAL endpoint {cfg.preset.label} — this stays on your machine"
        )
        warn = ""
        if findings:
            cats = ", ".join(sorted({f.category for f in findings}))
            warn = (
                f"\n\n⚠ The PHI guard flagged possible identifiers ({cats}). "
                "Review before sending — this is a warning, not a block."
            )
        box = QMessageBox(self)
        box.setIcon(
            QMessageBox.Icon.Warning if (cfg.is_remote or findings) else QMessageBox.Icon.Question
        )
        box.setWindowTitle("Confirm send")
        box.setText(f"Send this text to {where}?{warn}")
        box.setDetailedText(preview)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _dispatch(self, user_text: str) -> None:  # pragma: no cover - live threaded path
        self._append("You", user_text)
        self.input_edit.clear()
        self.send_btn.setEnabled(False)
        client = LLMClient(self.current_config(), transport=self._make_transport())
        messages = self.build_messages(user_text)
        self._worker = _AskWorker(client, messages)
        self._worker.done.connect(lambda r: self._on_reply(user_text, r))
        self._worker.failed.connect(self._on_fail)
        self._worker.start()

    def _on_reply(self, user_text: str, response) -> None:  # pragma: no cover - live path
        self._history.append(LLMMessage("user", user_text))
        self._history.append(LLMMessage("assistant", response.text))
        if response.had_phi_warning:
            self._append("System", "(PHI guard warned on the last message — nothing was saved.)")
        self._append("rbGyanX", response.text)
        self.send_btn.setEnabled(True)

    def _on_fail(self, message: str) -> None:  # pragma: no cover - live path
        self._append("System", f"Request failed: {message}")
        self.send_btn.setEnabled(True)

    def _append(self, who: str, text: str) -> None:
        self.transcript.appendPlainText(f"{who}: {text}\n")
