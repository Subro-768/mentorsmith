"""Settings dialog for the AI provider and the toolchain.

Deliberately contains **no field for the API key**. Keys are read from an
environment variable so they never reach the settings file, the database or a
screenshot of this dialog.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import is_truthy, load_settings, save_settings
from ..providers.openai_compat import OpenAICompatibleProvider
from . import theme

DEFAULT_KEY_ENV = "MENTORSMITH_API_KEY"


class SettingsDialog(QDialog):
    """Edit provider endpoint, model, timeout and sandbox preference."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = load_settings()
        self.setWindowTitle("MentorSmith settings")
        self.setMinimumWidth(620)
        self._build_ui()
        self._load()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"QDialog {{ background-color: {theme.SURFACE}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 16)

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

        key_label = QLabel(
            f"Read from the environment variable "
            f"<code>{DEFAULT_KEY_ENV}</code> at request time. "
            "It is never saved by the app."
        )
        key_label.setWordWrap(True)
        key_label.setObjectName("muted")
        provider_form.addRow("API key:", key_label)

        self.key_status = QLabel()
        self.key_status.setWordWrap(True)
        provider_form.addRow("", self.key_status)

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
        layout.addLayout(buttons)

        box.accepted.connect(self._on_save)
        box.rejected.connect(self.reject)
        self.test_button.clicked.connect(self._on_test)

    # ------------------------------------------------------------------
    def _load(self) -> None:
        self.base_url_edit.setText(self.settings.get("provider_base_url", ""))
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

    def _refresh_key_status(self) -> None:
        has_key = bool(os.environ.get(DEFAULT_KEY_ENV, "").strip())
        if has_key:
            self.key_status.setText(
                f"<span style='color:{theme.SUCCESS}'>A key is present in "
                f"${DEFAULT_KEY_ENV} for this session.</span>"
            )
        else:
            self.key_status.setText(
                f"<span style='color:{theme.ERROR}'>No key found in "
                f"${DEFAULT_KEY_ENV}.</span><br>Export one in your terminal, for "
                f"example:<br><code>export {DEFAULT_KEY_ENV}=your-key-here</code>"
            )

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