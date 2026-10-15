"""AI tutor chat panel with the three assistance levels.

The panel is responsible for being honest about the network transfer: it shows
a persistent notice that code and prompts leave the machine, and it labels the
level the tutor is currently allowed to use.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QComboBox,
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
    """Conversation view for the AI tutor."""

    #: Emitted with (message, assistance_level) when the learner sends.
    message_requested = pyqtSignal(str, str)
    #: Emitted when the learner asks for a hint without typing anything.
    hint_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.addWidget(QLabel("Assistance level:"))

        self.level_combo = QComboBox()
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
        header.addWidget(self.level_combo)
        header.addStretch(1)

        self.request_hint_button = QPushButton("Just a hint")
        self.request_hint_button.setToolTip(
            "Ask the tutor for a clue without writing a message."
        )
        header.addWidget(self.request_hint_button)
        layout.addLayout(header)

        # Always-visible transparency about what leaves the machine.
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.notice.setObjectName("warning")
        self.notice.setText(
            "Your code, compiler output and messages are sent to an external "
            "AI provider when you ask a question. Nothing is sent otherwise."
        )
        layout.addWidget(self.notice)

        self.transcript = QTextBrowser()
        self.transcript.setOpenExternalLinks(False)
        layout.addWidget(self.transcript, 1)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            "Ask a question, or describe what you expected to happen…"
        )
        self.input.setMaximumHeight(90)
        self.input.setTabChangesFocus(True)
        layout.addWidget(self.input)

        buttons = QHBoxLayout()
        self.sending_label = QLabel()
        self.sending_label.setObjectName("muted")
        buttons.addWidget(self.sending_label)
        buttons.addStretch(1)

        self.clear_button = QPushButton("Clear chat")
        buttons.addWidget(self.clear_button)

        self.send_button = QPushButton("Send")
        self.send_button.setObjectName("primary")
        self.send_button.setEnabled(False)
        buttons.addWidget(self.send_button)
        layout.addLayout(buttons)

        # Wiring. The input is multi-line, so Enter inserts a newline and
        # Ctrl+Enter (or Cmd+Enter) sends.
        self.send_button.clicked.connect(self._on_send)
        send_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input)
        send_shortcut.activated.connect(self._on_send)
        self.clear_button.clicked.connect(self.clear_transcript)
        self.request_hint_button.clicked.connect(self._on_hint)
        self.level_combo.currentIndexChanged.connect(self._on_level_changed)

    # ------------------------------------------------------------------
    # Behaviour
    # ------------------------------------------------------------------
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

    def submit_text(self, text: str, level: str | None = None) -> None:
        """Programmatic send, used by the hint button and keyboard shortcuts."""
        self.set_level(level or self.current_level())
        self.input.setPlainText(text)
        self._on_send()

    def set_sending(self, sending: bool) -> None:
        """Toggle controls while a provider call is in flight."""
        self.send_button.setEnabled(not sending and self.provider_ready)
        self.request_hint_button.setEnabled(not sending and self.provider_ready)
        self.level_combo.setEnabled(not sending)
        self.sending_label.setText("Waiting for the tutor…" if sending else "")

    #: Mirrors whether a provider is configured, so controls can be disabled.
    provider_ready: bool = False

    def set_provider_ready(self, ready: bool) -> None:
        self.provider_ready = ready
        self.send_button.setEnabled(ready)
        self.request_hint_button.setEnabled(ready)
        if not ready:
            self.notice.setText(
                "No AI provider is configured, so the tutor is offline. "
                "Lessons, compiling and running still work. Open Settings to "
                "add a provider."
            )
            self.notice.setObjectName("error")
            self.notice.style().unpolish(self.notice)
            self.notice.style().polish(self.notice)

    def set_provider_note(self, note: str) -> None:
        """Show where prompts are going, from the provider's own description."""
        self.notice.setText(
            f"Code and prompts are sent to: {note}\n"
            "This only happens when you send a message."
        )

    # ------------------------------------------------------------------
    # Transcript rendering
    # ------------------------------------------------------------------
    def clear_transcript(self) -> None:
        self.transcript.clear()

    def add_learner_message(self, text: str) -> None:
        self._append("You", text, theme.ACCENT)

    def add_tutor_message(self, html: str) -> None:
        self._append("Tutor", html, theme.SUCCESS, is_html=True)

    def add_tutor_error(self, text: str) -> None:
        self._append("Tutor (error)", text, theme.ERROR)

    def add_system_note(self, text: str) -> None:
        self._append("", f"<i>{text}</i>", theme.MUTED, is_html=True)

    def _append(self, who: str, text: str, colour: str, is_html: bool = False) -> None:
        """Append a labelled block to the transcript."""
        import html as html_module

        heading = f"<b style='color:{colour}'>{html_module.escape(who)}</b>" if who else ""
        body = text if is_html else f"<span style='white-space:pre-wrap'>{html_module.escape(text)}</span>"
        self.transcript.append(f"<div style='margin-bottom:10px'>{heading}{body}</div>")
        scrollbar = self.transcript.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())