"""AI tutor chat panel — bubble-style messages, segmented level control."""

from __future__ import annotations

import html as html_module

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..services.tutor import ASSISTANCE_LEVELS, LEVEL_LABELS
from . import theme


class ChatPanel(QWidget):
    """Conversation view for the AI tutor with bubble-style layout."""

    message_requested = pyqtSignal(str, str)   # (message, level)
    hint_requested    = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._provider = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Top bar ──────────────────────────────────────────────────────
        topbar = QWidget()
        topbar.setStyleSheet(
            f"background-color: {theme.SURFACE_ALT}; "
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        topbar.setFixedHeight(46)
        topbar_lay = QHBoxLayout(topbar)
        topbar_lay.setContentsMargins(12, 0, 12, 0)
        topbar_lay.setSpacing(8)

        tutor_icon = QLabel("🤖")
        tutor_icon.setStyleSheet("font-size: 16px;")
        topbar_lay.addWidget(tutor_icon)

        tutor_title = QLabel("AI Tutor")
        tutor_title.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {theme.FOREGROUND};"
        )
        topbar_lay.addWidget(tutor_title)
        topbar_lay.addStretch(1)

        # Level control
        level_lbl = QLabel("Level:")
        level_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        topbar_lay.addWidget(level_lbl)

        self.level_combo = QComboBox()
        self.level_combo.setFixedWidth(150)
        self.level_combo.setFixedHeight(28)
        for level in ASSISTANCE_LEVELS:
            self.level_combo.addItem(LEVEL_LABELS[level], level)
        self.level_combo.setToolTip(
            "Hint gives one clue with no answer.\n"
            "Guided asks leading questions one step at a time.\n"
            "Full explanation gives the worked solution.\n\n"
            "Lower levels never volunteer the answer first, but you can ask "
            "for the full explanation at any time."
        )
        self.level_combo.setCurrentIndex(1)
        topbar_lay.addWidget(self.level_combo)

        # ── Model picker ──────────────────────────────────────────────
        # Editable on purpose: the list is fetched from the provider, but a
        # provider that does not implement /models (or a key that cannot reach
        # the listing) must not stop somebody typing a model name.
        model_lbl = QLabel("Model:")
        model_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        topbar_lay.addWidget(model_lbl)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.setFixedWidth(220)
        self.model_combo.setFixedHeight(28)
        self.model_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_combo.setToolTip(
            "Which model answers this conversation.\n\n"
            "The list is fetched from your provider. You can also type any "
            "model name your key can reach - useful for a model that is not "
            "listed, or when the listing cannot be fetched."
        )
        topbar_lay.addWidget(self.model_combo)

        self.refresh_models_button = QPushButton("⟳")
        self.refresh_models_button.setObjectName("subtle")
        self.refresh_models_button.setFixedHeight(28)
        self.refresh_models_button.setFixedWidth(28)
        self.refresh_models_button.setToolTip("Fetch the model list from the provider.")
        self.refresh_models_button.clicked.connect(self.refresh_models)
        topbar_lay.addWidget(self.refresh_models_button)

        self.request_hint_button = QPushButton("💡 Hint")
        self.request_hint_button.setObjectName("subtle")
        self.request_hint_button.setFixedHeight(28)
        self.request_hint_button.setFixedWidth(70)
        self.request_hint_button.setToolTip("Ask the tutor for a clue without writing a message.")
        topbar_lay.addWidget(self.request_hint_button)

        layout.addWidget(topbar)

        # ── Privacy notice ────────────────────────────────────────────────
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setStyleSheet(
            f"background-color: {theme.WARNING_BG}; color: {theme.WARNING}; "
            f"border-bottom: 1px solid {theme.BORDER}; "
            f"font-size: 11px; padding: 6px 14px;"
        )
        self.notice.setText(
            "⚠  Your code, compiler output and messages are sent to an external AI provider when you ask. "
            "Nothing is sent otherwise."
        )
        layout.addWidget(self.notice)

        # ── Transcript ────────────────────────────────────────────────────
        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        self.transcript.setFrameShape(QFrame.Shape.NoFrame)
        self.transcript.setStyleSheet(
            f"QTextBrowser {{ background-color: {theme.BASE}; border: none; "
            f"padding: 12px; }}"
        )
        layout.addWidget(self.transcript, 1)

        # ── Input area ────────────────────────────────────────────────────
        input_container = QWidget()
        input_container.setStyleSheet(
            f"background-color: {theme.SURFACE}; "
            f"border-top: 1px solid {theme.BORDER};"
        )
        input_lay = QVBoxLayout(input_container)
        input_lay.setContentsMargins(12, 10, 12, 10)
        input_lay.setSpacing(6)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Ask a question, or describe what you expected to happen…")
        self.input.setMaximumHeight(80)
        self.input.setMinimumHeight(50)
        self.input.setTabChangesFocus(True)
        self.input.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {theme.SURFACE_ALT}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 8px; "
            f"padding: 8px 12px; color: {theme.FOREGROUND}; font-size: 13px; }}"
            f"QPlainTextEdit:focus {{ border-color: {theme.ACCENT}; }}"
        )
        input_lay.addWidget(self.input)

        # Bottom row: status + buttons
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.sending_label = QLabel()
        self.sending_label.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        bottom_row.addWidget(self.sending_label)
        bottom_row.addStretch(1)

        self.clear_button = QPushButton("Clear")
        self.clear_button.setObjectName("subtle")
        self.clear_button.setFixedHeight(32)
        self.clear_button.setFixedWidth(60)
        bottom_row.addWidget(self.clear_button)

        self.send_button = QPushButton("Send  ↑")
        self.send_button.setObjectName("primary")
        self.send_button.setFixedHeight(32)
        self.send_button.setFixedWidth(90)
        self.send_button.setEnabled(False)
        bottom_row.addWidget(self.send_button)

        input_lay.addLayout(bottom_row)
        layout.addWidget(input_container)

        # Wiring
        self.send_button.clicked.connect(self._on_send)
        send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input)
        send_shortcut.activated.connect(self._on_send)
        self.clear_button.clicked.connect(self.clear_transcript)
        self.request_hint_button.clicked.connect(self._on_hint)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)

        # Enable send when text typed
        self.input.textChanged.connect(self._on_input_changed)

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Model selection
    # ------------------------------------------------------------------
    def current_model(self) -> str:
        """The model to use for the next message, or "" to use the default.

        Returns "" rather than the configured default so that "not chosen"
        stays distinguishable from "chosen, and it happens to be the default".
        """
        return self.model_combo.currentText().strip()

    def set_model(self, model: str) -> None:
        if not model:
            return
        self._set_model_text(model)

    def _set_model_text(self, model: str) -> None:
        """Put ``model`` in the box without triggering a repopulate."""
        blocked = self.model_combo.blockSignals(True)
        index = self.model_combo.findText(model)
        if index >= 0:
            self.model_combo.setCurrentIndex(index)
        else:
            self.model_combo.setEditText(model)
        self.model_combo.blockSignals(blocked)

    def refresh_models(self, provider=None) -> int:
        """Fetch the provider's model list into the picker.

        Never raises and never blocks on failure: a provider with no /models
        endpoint, a bad key, or no network at all just leaves whatever was
        typed in place. Returns how many models were listed.
        """
        if provider is None:
            provider = getattr(self, "_provider", None)
        lister = getattr(provider, "list_models", None)
        if lister is None:
            return 0

        try:
            models = lister()
        except Exception:
            # A picker is a convenience; it must not be able to break chat.
            return 0
        if not models:
            return 0

        current = self.current_model()
        blocked = self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for model in models:
            self.model_combo.addItem(model["name"], model["id"])
        if current:
            self._set_model_text(current)
        self.model_combo.blockSignals(blocked)
        return len(models)

    def set_provider(self, provider) -> int:
        """Remember the provider so the picker can ask it for models.

        Returns how many models were listed, matching :meth:`refresh_models`
        so a caller does not have to know which half did the work.
        """
        self._provider = provider
        model = getattr(provider, "model", "")
        if model:
            self.set_model(model)
        return self.refresh_models(provider)

    def current_level(self) -> str:
        return str(self.level_combo.currentData() or "guided")

    def set_level(self, level: str) -> None:
        index = self.level_combo.findData(level)
        if index >= 0:
            self.level_combo.setCurrentIndex(index)

    def _on_level_changed(self) -> None:
        self.add_system_note(f"Assistance level set to: {self.current_level()}")

    def _on_hint(self) -> None:
        self.hint_requested.emit("")

    def _on_send(self) -> None:
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.add_learner_message(text)
        self.message_requested.emit(text, self.current_level())

    def _on_input_changed(self) -> None:
        has_text = bool(self.input.toPlainText().strip())
        self.send_button.setEnabled(has_text and self.provider_ready)

    def submit_text(self, text: str, level: str | None = None) -> None:
        self.set_level(level or self.current_level())
        self.input.setPlainText(text)
        self._on_send()

    def set_sending(self, sending: bool) -> None:
        self.send_button.setEnabled(not sending and self.provider_ready)
        self.request_hint_button.setEnabled(not sending and self.provider_ready)
        self.level_combo.setEnabled(not sending)
        self.sending_label.setText("⏳ Waiting for the tutor…" if sending else "")

    provider_ready: bool = False

    def set_provider_ready(self, ready: bool) -> None:
        self.provider_ready = ready
        self.send_button.setEnabled(ready)
        self.request_hint_button.setEnabled(ready)
        if not ready:
            self.notice.setText(
                "🔴  No AI provider configured — tutor is offline. "
                "Lessons, compiling and running still work. Open Settings to add a provider."
            )
            self.notice.setStyleSheet(
                f"background-color: {theme.ERROR_BG}; color: {theme.ERROR}; "
                f"border-bottom: 1px solid {theme.BORDER}; "
                f"font-size: 11px; padding: 6px 14px;"
            )

    def set_provider_note(self, note: str) -> None:
        self.notice.setText(
            f"🔒  Code and prompts are sent to: {note} — only when you send a message."
        )
        self.notice.setStyleSheet(
            f"background-color: {theme.INFO_BG}; color: {theme.INFO}; "
            f"border-bottom: 1px solid {theme.BORDER}; "
            f"font-size: 11px; padding: 6px 14px;"
        )

    # ------------------------------------------------------------------
    # Transcript rendering — bubble style
    # ------------------------------------------------------------------
    def clear_transcript(self) -> None:
        self.transcript.clear()

    def add_learner_message(self, text: str) -> None:
        escaped = html_module.escape(text)
        self.transcript.append(
            f"<div style='margin:8px 0; text-align:right'>"
            f"<span style='display:inline-block; background:{theme.ACCENT}; "
            f"color:{theme.ACCENT_TEXT}; border-radius:12px 12px 2px 12px; "
            f"padding:8px 14px; max-width:80%; font-size:13px; "
            f"white-space:pre-wrap'>{escaped}</span>"
            f"<div style='font-size:10px; color:{theme.PLACEHOLDER}; margin-top:3px'>You</div>"
            f"</div>"
        )
        self._scroll_to_bottom()

    def add_tutor_message(self, html: str) -> None:
        self.transcript.append(
            f"<div style='margin:8px 0'>"
            f"<div style='font-size:10px; color:{theme.PLACEHOLDER}; margin-bottom:3px'>🤖 Tutor</div>"
            f"<span style='display:inline-block; background:{theme.SURFACE_ALT}; "
            f"color:{theme.FOREGROUND}; border-radius:2px 12px 12px 12px; "
            f"border:1px solid {theme.BORDER}; "
            f"padding:10px 14px; max-width:85%; font-size:13px'>{html}</span>"
            f"</div>"
        )
        self._scroll_to_bottom()

    def add_tutor_error(self, text: str) -> None:
        escaped = html_module.escape(text)
        self.transcript.append(
            f"<div style='margin:6px 0; padding:8px 12px; "
            f"background:{theme.ERROR_BG}; border-left:3px solid {theme.ERROR}; "
            f"border-radius:4px; color:{theme.ERROR}; font-size:12px'>"
            f"⚠ {escaped}</div>"
        )
        self._scroll_to_bottom()

    def add_system_note(self, text: str) -> None:
        self.transcript.append(
            f"<div style='margin:4px 0; text-align:center'>"
            f"<span style='color:{theme.PLACEHOLDER}; font-size:11px; "
            f"font-style:italic'>{text}</span>"
            f"</div>"
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        sb = self.transcript.verticalScrollBar()
        sb.setValue(sb.maximum())