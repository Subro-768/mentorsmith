"""Settings dialog for the AI provider and the toolchain.

Deliberately contains **no field for the API key**. Keys are read from an
environment variable so they never reach the settings file, the database or a
screenshot of this dialog.
"""

from __future__ import annotations

import html
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..providers.detect import detect_provider
from ..config import (
    clear_api_key,
    is_truthy,
    load_api_key,
    load_settings,
    save_api_key,
    save_settings,
    secrets_path,
)
from ..providers.openai_compat import OpenAICompatibleProvider
from . import theme

DEFAULT_KEY_ENV = "MENTORSMITH_API_KEY"

#: Known providers, so the base URL does not have to be remembered. The model
#: is deliberately left blank: the model list is fetched from the endpoint
#: itself rather than hardcoded here, because a hardcoded list goes stale
#: silently and cannot know what a given key may actually reach.
PRESETS = [
    ("OpenRouter", "https://openrouter.ai/api/v1"),
    ("OpenAI", "https://api.openai.com/v1"),
    ("Groq", "https://api.groq.com/openai/v1"),
    ("Ollama (local)", "http://localhost:11434/v1"),
    ("LM Studio (local)", "http://localhost:1234/v1"),
]


class SettingsDialog(QDialog):
    """Edit provider endpoint, model, timeout and sandbox preference."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = load_settings()
        self.setWindowTitle("MentorSmith settings")
        self._build_ui()
        self._load()
        self._fit_to_screen()

    def _fit_to_screen(self) -> None:
        """Size the dialog to the screen and make sure it can be resized.

        The content grew - a provider dropdown, a Detect button, key status and
        a candidate-button row - and with no size management the dialog simply
        grew past the bottom of the display. Save and Cancel were below the fold
        and there was no way to reach them short of killing the process.
        """
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        if available is None:
            self.resize(680, 720)
            return

        # Aim for a comfortable default, then never exceed what fits.
        width = min(720, max(620, available.width() - 120))
        height = min(880, available.height() - 80)
        self.resize(width, height)
        self.setMinimumSize(560, 320)

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QDialog {{ background-color: {theme.SURFACE}; }}"
        )
        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.setContentsMargins(16, 16, 16, 12)

        # Everything between here and the button box lives inside a scroll
        # area. The Save/Cancel row deliberately does *not*: a dialog whose
        # only way to save is to scroll to the bottom is a dialog that looks
        # broken on a short screen.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        content.setStyleSheet(f"background-color: {theme.SURFACE};")
        layout = QVBoxLayout(content)
        layout.setSpacing(16)
        layout.setContentsMargins(4, 4, 8, 4)

        # ── Title ────────────────────────────────────────────────────────
        title = QLabel("Settings")
        title.setObjectName("title")
        layout.addWidget(title)

        # ── AI provider ──────────────────────────────────────────────────
        provider_box = QGroupBox("AI Provider")
        provider_form = QFormLayout(provider_box)
        provider_form.setSpacing(10)
        provider_form.setContentsMargins(12, 16, 12, 12)
        provider_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Custom…", None)
        for name, url in PRESETS:
            self.preset_combo.addItem(name, url)
        self.preset_combo.setFixedHeight(34)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        provider_form.addRow("Provider:", self.preset_combo)

        self.base_url_edit = QLineEdit()
        self.base_url_edit.setPlaceholderText("https://your-provider.example/v1")
        self.base_url_edit.setFixedHeight(34)
        provider_form.addRow("Base URL:", self.base_url_edit)

        self.model_edit = QLineEdit()
        self.model_edit.setPlaceholderText("the exact model name your account can use")
        self.model_edit.setFixedHeight(34)
        provider_form.addRow("Model:", self.model_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 600)
        self.timeout_spin.setSuffix(" s")
        self.timeout_spin.setFixedHeight(34)
        provider_form.addRow("Request timeout:", self.timeout_spin)

        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_edit.setPlaceholderText("paste your key here")
        self.key_edit.setFixedHeight(34)
        self.key_edit.setText(load_api_key())
        # Live feedback. Previously the status line was only computed when the
        # dialog opened, so typing a key left a red "No key." sitting directly
        # above a green "Detected OpenRouter" - two contradictory statements
        # about the same field, both visible at once.
        self.key_edit.textChanged.connect(self._on_key_text_changed)
        provider_form.addRow("API key:", self.key_edit)

        self.detect_button = QPushButton("Detect")
        self.detect_button.setFixedHeight(28)
        self.detect_button.setToolTip(
            "Identify the provider from the key's prefix and fill in the "
            "endpoint.\n\nThis inspects the key locally and sends it nowhere. "
            "A prefix shared by several providers is reported rather than "
            "guessed, because guessing wrong would send the key to the wrong "
            "company."
        )
        self.detect_button.clicked.connect(self._on_detect)

        self.show_key_check = QCheckBox("Show")
        self.show_key_check.toggled.connect(self._on_toggle_show_key)
        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_row.addWidget(self.key_edit, 1)
        key_row.addWidget(self.detect_button)
        key_row.addWidget(self.show_key_check)
        key_widget = QWidget()
        key_widget.setLayout(key_row)
        provider_form.addRow("", key_widget)

        self.key_status = QLabel()
        self.key_status.setWordWrap(True)
        provider_form.addRow("", self.key_status)

        self.detect_status = QLabel()
        self.detect_status.setWordWrap(True)
        provider_form.addRow("", self.detect_status)
        self.detect_choices = QWidget()
        self.detect_choice_layout = QHBoxLayout()
        self.detect_choice_layout.setSpacing(6)
        self.detect_choice_layout.setContentsMargins(0, 0, 0, 0)
        self.detect_choices.setLayout(self.detect_choice_layout)
        provider_form.addRow("", self.detect_choices)

        self.forget_key_button = QPushButton("Forget stored key")
        self.forget_key_button.setFixedHeight(28)
        self.forget_key_button.setToolTip(
            f"Delete {secrets_path().name}. "
            f"The ${DEFAULT_KEY_ENV} environment variable is unaffected."
        )
        self.forget_key_button.clicked.connect(self._on_forget_key)
        forget_row = QHBoxLayout()
        forget_row.addWidget(self.forget_key_button)
        forget_row.addStretch(1)
        forget_widget = QWidget()
        forget_widget.setLayout(forget_row)
        provider_form.addRow("", forget_widget)

        layout.addWidget(provider_box)

        # ── Toolchain ─────────────────────────────────────────────────────
        toolchain_box = QGroupBox("C++ Toolchain")
        toolchain_layout = QVBoxLayout(toolchain_box)
        toolchain_layout.setContentsMargins(12, 16, 12, 12)
        toolchain_layout.setSpacing(8)

        self.sandbox_check = QCheckBox(
            "Run learner code inside a bubblewrap sandbox when available"
        )
        self.sandbox_check.setToolTip(
            "Adds a private mount namespace, no network and a read-only view of "
            "the system. Off by default because it can break code that expects "
            "host access. Resource limits apply either way."
        )
        toolchain_layout.addWidget(self.sandbox_check)

        self.sandbox_detail = QLabel()
        self.sandbox_detail.setWordWrap(True)
        self.sandbox_detail.setObjectName("muted")
        toolchain_layout.addWidget(self.sandbox_detail)

        self.compiler_detail = QLabel()
        self.compiler_detail.setWordWrap(True)
        self.compiler_detail.setObjectName("muted")
        toolchain_layout.addWidget(self.compiler_detail)

        layout.addWidget(toolchain_box)

        # ── Privacy ───────────────────────────────────────────────────────
        privacy_box = QGroupBox("Privacy — What Leaves This Machine")
        privacy_layout = QVBoxLayout(privacy_box)
        privacy_layout.setContentsMargins(12, 16, 12, 12)
        privacy_layout.setSpacing(8)

        privacy_text = QLabel(
            "When you send a message to the tutor, the following is sent to your "
            "configured provider:<ul>"
            "<li>the lesson title and objectives</li>"
            "<li>the code currently in the editor</li>"
            "<li>the compiler and runtime output on screen</li>"
            "<li>your message</li>"
            "</ul>"
            "Nothing is sent unless you send a message. Setting the environment "
            "variable <code>MENTORSMITH_OFFLINE=1</code> blocks all AI calls."
        )
        privacy_text.setWordWrap(True)
        privacy_text.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        privacy_layout.addWidget(privacy_text)

        offline_row = QHBoxLayout()
        self.offline_check = QCheckBox("Block all AI calls for this run")
        offline_row.addWidget(self.offline_check)
        offline_note = QLabel(
            "Takes effect immediately without a restart."
        )
        offline_note.setObjectName("muted")
        offline_note.setWordWrap(True)
        offline_row.addWidget(offline_note, 1)
        privacy_layout.addLayout(offline_row)

        layout.addWidget(privacy_box)

        # ── Appearance / Theme ──────────────────────────────────────────
        appearance_box = QGroupBox("Appearance")
        appearance_form = QFormLayout(appearance_box)
        appearance_form.setSpacing(10)
        appearance_form.setContentsMargins(12, 16, 12, 12)
        appearance_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.theme_combo = QComboBox()
        self.theme_combo.setFixedHeight(34)
        for theme_id, theme_label in theme.THEMES.items():
            self.theme_combo.addItem(theme_label, theme_id)
        appearance_form.addRow("Color theme:", self.theme_combo)

        theme_note = QLabel(
            "Theme is applied immediately after clicking Save. "
            "It persists across restarts."
        )
        theme_note.setObjectName("muted")
        theme_note.setWordWrap(True)
        appearance_form.addRow("", theme_note)

        layout.addWidget(appearance_box)

        # ── Test output ────────────────────────────────────────────────
        self.test_output = QPlainTextEdit()
        self.test_output.setReadOnly(True)
        self.test_output.setPlaceholderText("Output from a test request appears here.")
        self.test_output.setMaximumHeight(100)
        self.test_output.setStyleSheet(
            f"QPlainTextEdit {{ background: {theme.BASE}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 8px; font-family: monospace; font-size: 12px; padding: 8px; }}"
        )
        layout.addWidget(self.test_output)

        # ── Buttons ───────────────────────────────────────────────────────
        buttons = QHBoxLayout()
        self.test_button = QPushButton("⚡ Test connection")
        self.test_button.setFixedHeight(36)
        buttons.addWidget(self.test_button)
        buttons.addStretch(1)

        box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        # Style Save as primary
        save_btn = box.button(QDialogButtonBox.StandardButton.Save)
        if save_btn:
            save_btn.setObjectName("primary")
            save_btn.setFixedHeight(36)
        cancel_btn = box.button(QDialogButtonBox.StandardButton.Cancel)
        if cancel_btn:
            cancel_btn.setFixedHeight(36)
        buttons.addWidget(box)

        # Seal the scroll area, then pin the buttons below it so they stay on
        # screen no matter how tall the form gets.
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        outer.addLayout(buttons)

        box.accepted.connect(self._on_save)
        box.rejected.connect(self.reject)
        self.test_button.clicked.connect(self._on_test)

    # ------------------------------------------------------------------
    def _load(self) -> None:
        saved_url = self.settings.get("provider_base_url", "")
        self.base_url_edit.setText(saved_url)
        # Reflect a saved URL that matches a preset, so reopening Settings does
        # not show "Custom…" for a provider that has a preset.
        matched = self.preset_combo.findData(saved_url) if saved_url else 0
        self.preset_combo.setCurrentIndex(matched if matched > 0 else 0)
        self.model_edit.setText(self.settings.get("provider_model", ""))
        self.timeout_spin.setValue(int(self.settings.get("provider_timeout", 60) or 60))
        self.sandbox_check.setChecked(bool(self.settings.get("sandbox_enabled", False)))
        self.offline_check.setChecked(is_truthy(os.environ.get("MENTORSMITH_OFFLINE", "")))
        # Select current theme
        saved_theme = self.settings.get("theme", "dark_orange")
        idx = self.theme_combo.findData(saved_theme)
        if idx >= 0:
            self.theme_combo.setCurrentIndex(idx)
        self._refresh_key_status()
        self._refresh_sandbox_detail()

    def _on_preset_changed(self, index: int) -> None:
        """Fill in the base URL when a known provider is picked.

        Only overwrites the model when picking "Custom…", so switching between
        two hosted providers does not throw away a model name that is still
        perfectly valid.
        """
        url = self.preset_combo.itemData(index)
        if not url:
            return
        if self.base_url_edit.text().strip() != url:
            self.base_url_edit.setText(url)

    # ------------------------------------------------------------------
    # Provider detection from the key
    # ------------------------------------------------------------------
    def _on_detect(self) -> None:
        """Fill in the endpoint from the key's prefix, where that is safe."""
        detection = detect_provider(self.key_edit.text())
        self._clear_detect_choices()

        if detection.confidence == "certain":
            url, model = detection.base_url, detection.suggested_model
            self.base_url_edit.setText(url)
            self._select_preset(url)
            # Only fill the model if the user has not already chosen one.
            if model and not self.model_edit.text().strip():
                self.model_edit.setText(model)
            self.detect_status.setText(
                f"<span style='color:{theme.SUCCESS}'>"
                f"Detected {html.escape(detection.provider)}.</span><br>"
                f"{html.escape(detection.reason)}<br>"
                f"Endpoint set. Fetch the model list with the ⟳ button in the "
                f"chat to see everything your key can reach."
            )
            return

        if detection.unsupported:
            self.detect_status.setText(
                f"<span style='color:{theme.WARNING}'>"
                f"Looks like an {html.escape(detection.provider)} key.</span><br>"
                f"{html.escape(detection.reason)}<br>"
                + "<br>".join(html.escape(n) for n in detection.notes)
            )
            return

        if detection.confidence == "ambiguous":
            self.detect_status.setText(
                f"<span style='color:{theme.WARNING}'>"
                f"That prefix is not unique.</span><br>"
                f"{html.escape(detection.reason)}<br>"
                f"Choose one, or type the endpoint yourself:"
            )
            for name in detection.candidates:
                button = QPushButton(name)
                button.setFixedHeight(26)
                button.clicked.connect(
                    lambda _checked=False, n=name: self._apply_detected(n)
                )
                self.detect_choice_layout.addWidget(button)
            self.detect_choice_layout.addStretch(1)
            return

        self.detect_status.setText(
            f"<span style='color:{theme.MUTED}'>"
            f"{html.escape(detection.reason)}</span><br>"
            "Pick a provider from the dropdown above, or type the endpoint."
        )

    def _apply_detected(self, provider_name: str) -> None:
        """Set the endpoint for a provider the user chose by name."""
        from ..providers import detect as detector

        for _prefix, options in detector._SHARED_PREFIXES:
            for name, url in options:
                if name == provider_name and url:
                    self.base_url_edit.setText(url)
                    self._select_preset(url)
                    self.detect_status.setText(
                        f"<span style='color:{theme.SUCCESS}'>"
                        f"Endpoint set to {html.escape(name)}.</span> "
                        "If the key turns out to be for someone else, change it "
                        "here before sending anything."
                    )
                    return
        self.detect_status.setText(
            f"{html.escape(provider_name)} is not reachable through the "
            "OpenAI-compatible endpoint this app uses."
        )

    def _select_preset(self, url: str) -> None:
        index = self.preset_combo.findData(url)
        if index > 0:
            self.preset_combo.setCurrentIndex(index)

    def _clear_detect_choices(self) -> None:
        """Empty the candidate-button row.

        The stretch is dropped too; leaving it would push a later row of
        buttons to the far right of the dialog.
        """
        while self.detect_choice_layout.count():
            item = self.detect_choice_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _on_key_text_changed(self, text: str) -> None:
        """Keep the status honest about what is actually typed right now.

        Three sources exist - typed-and-saved, typed-but-unsaved, and the
        environment variable - and the line has to distinguish them, or "I
        pasted a key and the app says there is none" becomes undebuggable.
        """
        typed = text.strip()
        stored = load_api_key()
        env = bool(os.environ.get(DEFAULT_KEY_ENV, "").strip())

        if typed and typed == stored:
            body = (
                f"<span style='color:{theme.SUCCESS}'>Key saved.</span> "
                f"Owner-only in <code>{secrets_path().name}</code>."
            )
        elif typed and env:
            body = (
                f"<span style='color:{theme.WARNING}'>Typed, not saved yet</span> "
                f"— press Save to store it. ${DEFAULT_KEY_ENV} is also set and "
                f"is currently being used."
            )
        elif typed:
            body = (
                f"<span style='color:{theme.WARNING}'>Typed, not saved yet</span> "
                f"— press Save to store it. <code>Detect</code> will work "
                f"before saving."
            )
        elif stored:
            body = (
                f"<span style='color:{theme.SUCCESS}'>A key is saved in "
                f"<code>{secrets_path().name}</code>.</span>"
            )
        elif env:
            body = (
                f"<span style='color:{theme.SUCCESS}'>Using ${DEFAULT_KEY_ENV} "
                f"from your shell.</span> Nothing is stored on disk."
            )
        else:
            body = (
                f"<span style='color:{theme.ERROR}'>No key.</span> Paste one "
                f"above and press Save, or keep it out of the app and export "
                f"<code>{DEFAULT_KEY_ENV}</code> in your shell."
            )
        self.key_status.setText(body)

    def _on_toggle_show_key(self, on: bool) -> None:
        self.key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password
        )

    def _on_forget_key(self) -> None:
        clear_api_key()
        # Clearing the field fires textChanged, which refreshes the line.
        self.key_edit.clear()

    def _refresh_key_status(self) -> None:
        """Recompute the status line from the field as it stands now.

        Deliberately delegates rather than reimplementing: two versions of the
        same message is how the dialog ended up showing a stale red "No key."
        next to a green "Detected OpenRouter".
        """
        self._on_key_text_changed(self.key_edit.text())

    def _refresh_sandbox_detail(self) -> None:
        import shutil

        if shutil.which("bwrap"):
            self.sandbox_detail.setText(
                "bubblewrap (bwrap) is installed, so this option will work."
            )
        else:
            self.sandbox_detail.setText(
                f"<span style='color:{theme.ERROR}'>bubblewrap is not installed, "
                "so this option cannot take effect.</span> Install it with:<br>"
                "<code>sudo dnf install bubblewrap</code>"
            )

    # ------------------------------------------------------------------
    def _on_test(self) -> None:
        """Make one real, minimal request so the user learns if it really works."""
        from ..providers.base import CompletionRequest, ProviderError

        base_url = self.base_url_edit.text().strip()
        model = self.model_edit.text().strip()

        if not base_url or not model:
            self.test_output.setPlainText(
                "Enter both a base URL and a model name first."
            )
            return

        provider = OpenAICompatibleProvider(
            base_url=base_url,
            model=model,
            timeout=self.timeout_spin.value(),
        )
        self.test_button.setEnabled(False)
        self.test_output.setPlainText(
            f"Sending one minimal request to {base_url} "
            "(this does consume a small amount of quota)…"
        )
        QApplication_processEvents()

        try:
            response = provider.complete(
                CompletionRequest(
                    system="You are a connectivity test. Reply with exactly: ok",
                    user="Reply with exactly: ok",
                    max_tokens=10,
                    temperature=0.0,
                )
            )
        except ProviderError as exc:
            self.test_output.setPlainText(f"FAILED\n\n{exc}")
        except Exception as exc:  # pragma: no cover - defensive
            self.test_output.setPlainText(f"FAILED\n\nUnexpected error: {exc}")
        else:
            self.test_output.setPlainText(
                f"SUCCESS\n\nEndpoint: {base_url}\n"
                f"Model reported: {response.model}\n"
                f"Reply: {response.text[:200]}"
            )
        finally:
            self.test_button.setEnabled(True)

    def _on_save(self) -> None:
        self.settings["provider_base_url"] = self.base_url_edit.text().strip()
        self.settings["provider_model"] = self.model_edit.text().strip()
        self.settings["provider_timeout"] = self.timeout_spin.value()
        # An unchanged field must not wipe a stored key: the box is populated
        # on load, but if it was ever rendered masked-empty this would delete it.
        typed = self.key_edit.text().strip()
        if typed != load_api_key():
            save_api_key(typed)
        self.settings["sandbox_enabled"] = self.sandbox_check.isChecked()
        # Persist selected theme
        selected_theme = self.theme_combo.currentData()
        if selected_theme:
            self.settings["theme"] = selected_theme
        save_settings(self.settings)

        if self.offline_check.isChecked():
            os.environ["MENTORSMITH_OFFLINE"] = "1"
        else:
            os.environ.pop("MENTORSMITH_OFFLINE", None)

        self.accept()


def QApplication_processEvents() -> None:
    """Let Qt repaint while a blocking request is in flight.

    The test request is synchronous, so without this the dialog would appear
    frozen for up to the timeout.
    """
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            app.processEvents()
    except Exception:  # pragma: no cover - never let a repaint break the test
        pass