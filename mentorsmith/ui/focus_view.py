"""The Focus page: a timer, a guard, and the apps you chose to stop.

The page does three things while a session runs:

* it goes **full screen and stays on top**, so the other windows are not
  what you are looking at. This is the part that works on every display
  server, and it is the part that actually stops the pull;
* it **counts down** in the middle of the screen, so you know how long is
  left without opening anything;
* it **inhibits the screen lock and suspend**, so the session is not cut
  short by the machine.

It also closes the applications you tick, and says plainly when the display
server will not allow that - on Wayland it will not, and pretending
otherwise would be a lie.

Nothing here traps you: the End button is always on screen, Escape ends the
session, and the timer ending ends it by itself.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..services.focus import Distraction, FocusMode, format_duration
from . import theme


class FocusView(QWidget):
    """Pick a duration, pick the distractions, and start."""

    #: Emitted when a session starts or ends, so the window can adapt.
    session_changed = pyqtSignal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.focus = FocusMode()
        self._distractions: list[Distraction] = []
        self._build_ui()
        self.refresh_distractions()

        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

        # Escape always ends a session. A focus mode you cannot escape is
        # a trap, not a focus mode.
        self._escape = QShortcut(QKeySequence("Esc"), self)
        self._escape.activated.connect(self.end_session)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        title = QLabel("Focus")
        title.setObjectName("title")
        root.addWidget(title)

        # ── The idle state ────────────────────────────────────────────
        self.idle_panel = QWidget()
        idle = QVBoxLayout(self.idle_panel)
        idle.setContentsMargins(0, 0, 0, 0)
        idle.setSpacing(12)

        intro = QLabel(
            "Set a length, and the focus window takes over the screen so the "
            "other windows are not what you are looking at. The screen will "
            "not blank and the machine will not sleep while it runs."
        )
        intro.setWordWrap(True)
        intro.setObjectName("muted")
        idle.addWidget(intro)

        length_row = QHBoxLayout()
        length_label = QLabel("Session length:")
        length_label.setObjectName("muted")
        length_row.addWidget(length_label)
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 480)
        self.minutes_spin.setValue(45)
        self.minutes_spin.setSuffix(" minutes")
        self.minutes_spin.setFixedWidth(150)
        length_row.addWidget(self.minutes_spin)
        length_row.addStretch(1)
        idle.addLayout(length_row)

        # ── The distractions ──────────────────────────────────────────
        self.distraction_box = QGroupBox("Running applications to stop")
        distraction_layout = QVBoxLayout(self.distraction_box)
        self.capability_label = QLabel("")
        self.capability_label.setWordWrap(True)
        self.capability_label.setObjectName("muted")
        distraction_layout.addWidget(self.capability_label)

        self.distraction_list = QListWidget()
        self.distraction_list.setMaximumHeight(180)
        distraction_layout.addWidget(self.distraction_list)

        self.refresh_button = QPushButton("↺  Look again")
        self.refresh_button.setObjectName("subtle")
        self.refresh_button.setFixedHeight(30)
        self.refresh_button.clicked.connect(self.refresh_distractions)
        distraction_layout.addWidget(self.refresh_button)
        idle.addWidget(self.distraction_box)

        self.start_button = QPushButton("Start focus session")
        self.start_button.setObjectName("primary")
        self.start_button.setFixedHeight(40)
        self.start_button.clicked.connect(self.start_session)
        idle.addWidget(self.start_button)

        root.addWidget(self.idle_panel)

        # ── The running state: the guard ─────────────────────────────
        self.guard_panel = QFrame()
        guard = QVBoxLayout(self.guard_panel)
        guard.setContentsMargins(40, 40, 40, 40)
        guard.setSpacing(18)
        guard.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.clock_label = QLabel("00:00")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.clock_label.setStyleSheet(
            f"font-size: 92px; font-weight: 300; color: {theme.FOREGROUND};"
        )
        guard.addWidget(self.clock_label)

        self.guard_message = QLabel("")
        self.guard_message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.guard_message.setWordWrap(True)
        self.guard_message.setStyleSheet(f"color: {theme.MUTED}; font-size: 14px;")
        guard.addWidget(self.guard_message)

        self.guard_limits = QLabel("")
        self.guard_limits.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.guard_limits.setWordWrap(True)
        self.guard_limits.setStyleSheet(f"color: {theme.WARNING}; font-size: 12px;")
        guard.addWidget(self.guard_limits)

        self.end_button = QPushButton("End the session")
        self.end_button.setObjectName("subtle")
        self.end_button.setFixedHeight(40)
        self.end_button.clicked.connect(self.end_session)
        guard.addWidget(self.end_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.guard_panel.setVisible(False)
        root.addWidget(self.guard_panel, 1)

    # ------------------------------------------------------------------
    # Finding distractions
    # ------------------------------------------------------------------
    def refresh_distractions(self) -> None:
        """Look at what is running and list what looks distracting."""
        self._distractions = self.focus.list_distractions()
        self.distraction_list.clear()

        for item in self._distractions:
            label = item.label
            if item.title:
                label = f"{label} — {item.title}"
            entry = QListWidgetItem(label)
            entry.setFlags(entry.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            entry.setCheckState(Qt.CheckState.Unchecked)
            entry.setData(Qt.ItemDataRole.UserRole, item.key)
            self.distraction_list.addItem(entry)

        server = self.focus.display_server()
        if server == "wayland":
            self.capability_label.setText(
                "This display server (Wayland) does not let one application see "
                "or close another's windows, so what is listed here is found "
                "from the process table by name rather than from the window "
                "list. The full-screen guard and the screen lock are handled "
                "either way."
            )
        elif self.focus.window_list_available():
            self.capability_label.setText(
                "These are the open windows that look like distractions. "
                "Tick the ones you want closed when the session starts."
            )
        else:
            self.capability_label.setText(
                "The open windows cannot be listed on this display server, so "
                "this list is whatever was recognised by process name. The "
                "full-screen guard still applies."
            )

        if not self._distractions:
            self.distraction_box.setEnabled(False)
            self.capability_label.setText(
                self.capability_label.text()
                + "  Nothing recognisable is running at the moment - which is "
                "good news."
            )

    def _selected(self) -> list[Distraction]:
        chosen: list[Distraction] = []
        for row in range(self.distraction_list.count()):
            entry = self.distraction_list.item(row)
            if entry.checkState() != Qt.CheckState.Checked:
                continue
            key = entry.data(Qt.ItemDataRole.UserRole)
            for item in self._distractions:
                if item.key == key:
                    chosen.append(item)
        return chosen

    # ------------------------------------------------------------------
    # The session
    # ------------------------------------------------------------------
    def start_session(self) -> None:
        """Start, and go full screen."""
        minutes = self.minutes_spin.value()
        chosen = self._selected()
        session = self.focus.start(minutes, chosen)

        closed = ", ".join(session.closed) if session.closed else ""
        message = f"{format_duration(minutes)} of focus."
        if closed:
            message += f"  Closed: {closed}."
        self.guard_message.setText(message)

        limits = list(session.limits)
        if not session.idle_inhibited:
            limits.append("The screen lock was not inhibited.")
        self.guard_limits.setText("  ".join(limits))

        self.idle_panel.setVisible(False)
        self.guard_panel.setVisible(True)
        self._timer.start()
        self._on_tick()

        # The guard: full screen, and above the other windows.
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self.session_changed.emit(True)

    def end_session(self) -> None:
        """End it, and give the screen back."""
        session = self.focus.end()
        self._timer.stop()
        self.guard_panel.setVisible(False)
        self.idle_panel.setVisible(True)
        self.showNormal()
        if session and session.closed:
            # Say what was closed, so it can be reopened.
            QMessageBox.information(
                self, "Focus session ended",
                f"The session is over.\n\nClosed when it started: "
                f"{', '.join(session.closed)}.",
            )
        self.session_changed.emit(False)

    def _on_tick(self) -> None:
        """Once a second: update the clock, and finish on time."""
        session = self.focus.session
        if session is None:
            self._timer.stop()
            return
        if session.finished:
            self._timer.stop()
            self.focus.end()
            self.guard_panel.setVisible(False)
            self.idle_panel.setVisible(True)
            self.showNormal()
            self.session_changed.emit(False)
            return
        self.clock_label.setText(session.clock())

    # ------------------------------------------------------------------
    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        """Do not trap the learner in the full-screen guard."""
        super().leaveEvent(event)
