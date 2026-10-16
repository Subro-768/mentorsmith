"""Developer tools in the UI: audit, git, review, test generation, workspaces.

Phase 5 asks for these to be reviewable and approval-gated, and that has to be
visible in the interface, not just in the module docstrings. Three rules shape
this page:

* **Nothing destructive has a button.** There is no "discard changes", no
  "push", no "reset". The absence is deliberate: a capability that cannot be
  mis-clicked is safer than one behind a confirmation dialog.
* **A commit is a two-step action.** The first press produces a preview of
  exactly what would be recorded; only then is *Create commit* enabled. The
  button that writes says so.
* **Audit findings are grouped by how they were established**, and a finding
  that is only a suggestion is never presented as a bug.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.db import Database
from ..core.workspaces import WorkspaceError, WorkspaceManager
from ..services import review as review_mod
from ..services import testgen as testgen_mod
from ..services.git_tools import GitError, GitRepository, NotARepository
from ..services.security_audit import run_audit
from ..providers.base import CompletionRequest
from ..providers.openai_compat import build_provider

_HTML = (
    "<style>"
    "body{font-family:system-ui,sans-serif;font-size:11pt;}"
    "h3{margin-bottom:2px;}"
    "code{background:#2d2d30;padding:1px 4px;border-radius:3px;}"
    "</style>"
)


def _plain(text: str) -> str:
    """Escape untrusted content for the HTML panels."""
    import html as html_module

    return html_module.escape(text or "")


class PromptWorker(QThread):
    """Sends one raw system+user prompt off the GUI thread.

    Deliberately not `TutorWorker`: that builds the tutor's assistance-level
    prompts and parses structured markers, which is the wrong shape for code
    review and test generation. This asks the raw question and returns the
    text, which the caller then parses with a strict parser.
    """

    replied = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, settings: dict, system: str, user: str,
                 *, max_tokens: int = 2000) -> None:
        super().__init__()
        self.settings = settings
        self.system = system
        self.user = user
        self.max_tokens = max_tokens

    def run(self) -> None:  # noqa: D102 - QThread API
        try:
            provider = build_provider(self.settings)
            response = provider.complete(
                CompletionRequest(
                    system=self.system,
                    user=self.user,
                    max_tokens=self.max_tokens,
                    temperature=0.2,
                )
            )
            self.replied.emit(response.text)
        except Exception as exc:
            self.failed.emit(str(exc))


class DeveloperView(QWidget):
    """The Phase 5 tools."""

    status_message = pyqtSignal(str)

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self.workspaces = WorkspaceManager(Path.home() / ".local/share/mentorsmith/workspaces")
        self.repo: GitRepository | None = None
        self.proposal = None
        self._worker: PromptWorker | None = None
        self._build_ui()
        self._build_tabs()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Developer tools")
        title.setObjectName("title")
        root.addWidget(title)

        intro = QLabel(
            "Everything on this page runs against the project you choose. "
            "Read-only actions are safe; anything that writes shows you exactly "
            "what it will do before you approve it. There are deliberately no "
            "buttons for discarding changes or pushing to a remote."
        )
        intro.setObjectName("subtitle")
        intro.setWordWrap(True)
        root.addWidget(intro)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText(
            "/path/to/a/project or git repository"
        )
        self.path_edit.setText(str(Path.cwd()))
        root.addWidget(self.path_edit)

        row = QHBoxLayout()
        self.use_button = QPushButton("Use this folder")
        self.use_button.clicked.connect(self._on_use_folder)
        row.addWidget(self.use_button)

        self.review_button = QPushButton("Review selected files")
        self.review_button.clicked.connect(self._on_review)
        row.addWidget(self.review_button)

        self.audit_button = QPushButton("Run security audit")
        self.audit_button.clicked.connect(self._on_audit)
        row.addWidget(self.audit_button)
        row.addStretch(1)
        root.addLayout(row)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_files_tab(), "Files")
        self.tabs.addTab(self._build_git_tab(), "Git")
        self.tabs.addTab(self._build_review_tab(), "Code review")
        self.tabs.addTab(self._build_testgen_tab(), "Test ideas")
        self.tabs.addTab(self._build_audit_tab(), "Security audit")
        self.tabs.addTab(self._build_workspace_tab(), "Workspaces")
        root.addWidget(self.tabs, 1)

        self._on_use_folder()

    # ------------------------------------------------------------------
    def _build_tabs(self) -> None:
        """Hook up signals that need widgets to exist."""
        self.propose_button.clicked.connect(self._on_propose_commit)
        self.commit_button.clicked.connect(self._on_create_commit)
        self.commit_button.setEnabled(False)
        self.stage_button.clicked.connect(self._on_stage)
        self.ai_review_button.clicked.connect(self._on_ai_review)
        self.propose_tests_button.clicked.connect(self._on_propose_tests)

    # -- files ----------------------------------------------------------
    def _build_files_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel(
            "Files under the selected folder, for review and test generation."
        ))
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.itemSelectionChanged.connect(self._update_counts)
        layout.addWidget(self.file_list)

        self.file_count_label = QLabel()
        self.file_count_label.setObjectName("muted")
        layout.addWidget(self.file_count_label)
        return page

    # -- git ------------------------------------------------------------
    def _build_git_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.git_status_label = QLabel()
        self.git_status_label.setObjectName("subtitle")
        self.git_status_label.setWordWrap(True)
        layout.addWidget(self.git_status_label)

        splitter = QSplitter(Qt.Orientation.Vertical)

        upper = QWidget()
        upper_layout = QVBoxLayout(upper)
        upper_layout.addWidget(QLabel("Changed files"))
        self.git_status_view = QListWidget()
        upper_layout.addWidget(self.git_status_view)

        row = QHBoxLayout()
        self.stage_button = QPushButton("Stage selected")
        row.addWidget(self.stage_button)
        row.addStretch(1)
        upper_layout.addLayout(row)
        splitter.addWidget(upper)

        lower = QWidget()
        lower_layout = QVBoxLayout(lower)
        lower_layout.addWidget(QLabel("Recent commits"))
        self.git_log_view = QTextBrowser()
        lower_layout.addWidget(self.git_log_view)
        splitter.addWidget(lower)
        layout.addWidget(splitter, 1)

        commit_row = QHBoxLayout()
        self.commit_message = QLineEdit()
        self.commit_message.setPlaceholderText("Commit message")
        commit_row.addWidget(self.commit_message, 1)
        self.propose_button = QPushButton("Preview commit")
        commit_row.addWidget(self.propose_button)
        self.commit_button = QPushButton("Create commit")
        commit_button = self.commit_button
        commit_button.setToolTip(
            "Only enabled after a preview, and only commits what was staged."
        )
        commit_row.addWidget(commit_button)
        layout.addLayout(commit_row)

        self.commit_preview = QTextBrowser()
        self.commit_preview.setMaximumHeight(180)
        layout.addWidget(self.commit_preview)
        return page

    # -- review ---------------------------------------------------------
    def _build_review_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        row = QHBoxLayout()
        row.addWidget(QLabel("Findings are labelled by how they were established."))
        row.addStretch(1)
        self.ai_review_button = QPushButton("Ask the tutor for a review")
        row.addWidget(self.ai_review_button)
        layout.addLayout(row)

        self.review_view = QTextBrowser()
        self.review_view.setHtml(
            f"{_HTML}<p>Select files and press <b>Review selected files</b>."
            "<p>Findings from a compiler or a test are marked <b>CONFIRMED</b>. "
            "Pattern matches are <b>HEURISTIC</b> and need reading. Anything the "
            "tutor suggests is <b>SUGGESTION</b> and is not a bug until you "
            "verify it.</p>"
        )
        layout.addWidget(self.review_view, 1)
        return page

    # -- test generation ------------------------------------------------
    def _build_testgen_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel(
            "Select a file above, then propose tests. Nothing runs until you "
            "choose to run it, and a passing generated suite proves only that "
            "those specific cases behave as written."
        ))

        row = QHBoxLayout()
        row.addWidget(QLabel("Language:"))
        self.test_language = QComboBox()
        self.test_language.addItem("Python", "python")
        self.test_language.addItem("C++", "cpp")
        row.addWidget(self.test_language)
        self.propose_tests_button = QPushButton("Propose tests")
        row.addWidget(self.propose_tests_button)
        row.addStretch(1)
        layout.addLayout(row)

        self.test_view = QTextBrowser()
        layout.addWidget(self.test_view, 1)
        return page

    # -- audit ----------------------------------------------------------
    def _build_audit_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel(
            "Runs real code on this machine and reports what it observed. A "
            "check that cannot run here is shown as SKIPPED, never as passed."
        ))

        box = QGroupBox("Containment")
        box_layout = QVBoxLayout(box)
        self.audit_view = QTextBrowser()
        box_layout.addWidget(self.audit_view)
        layout.addWidget(box, 1)
        return page

    # -- workspaces -----------------------------------------------------
    def _build_workspace_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        layout.addWidget(QLabel(
            "Each learning project gets its own directory under your data "
            "folder. Project files are never written into the TutorSmith source "
            "tree, and a path that points outside the workspace is refused."
        ))

        row = QHBoxLayout()
        self.workspace_name = QLineEdit()
        self.workspace_name.setPlaceholderText("new project name")
        row.addWidget(self.workspace_name, 1)
        create = QPushButton("Create workspace")
        create.clicked.connect(self._on_create_workspace)
        row.addWidget(create)
        layout.addLayout(row)

        layout.addWidget(QLabel("Existing workspaces"))
        self.workspace_list = QListWidget()
        layout.addWidget(self.workspace_list, 1)

        detail = QHBoxLayout()
        self.save_source_button = QPushButton("Save editor contents here")
        self.save_source_button.clicked.connect(self._on_save_to_workspace)
        detail.addWidget(self.save_source_button)
        layout.addLayout(detail)

        self.workspace_detail = QTextBrowser()
        self.workspace_detail.setMaximumHeight(200)
        layout.addWidget(self.workspace_detail)

        self._refresh_workspaces()
        return page

    def _settings(self) -> dict | None:
        """Provider settings, or ``None`` when the tutor is not configured."""
        from ..config import load_settings

        try:
            settings = load_settings()
        except Exception:
            return None
        if not settings.get("base_url") or not settings.get("model"):
            return None
        return settings

    # ==================================================================
    # Actions
    # ==================================================================
    def _on_use_folder(self) -> None:
        raw = self.path_edit.text().strip()
        path = Path(raw).expanduser() if raw else Path.cwd()

        self.file_list.clear()
        if not path.is_dir():
            self.file_count_label.setText(f"Not a folder: {path}")
            return

        sources = [
            p for p in sorted(path.rglob("*"))
            if p.is_file()
            and p.suffix in (".py", ".cpp", ".cc", ".cxx", ".h", ".hpp", ".c")
            and ".git" not in p.parts
            and "build" not in p.parts
            and "__pycache__" not in p.parts
        ][:200]

        for item in sources:
            entry = QListWidgetItem(str(item.relative_to(path)))
            entry.setData(Qt.ItemDataRole.UserRole, str(item))
            entry.setToolTip(str(item))
            self.file_list.addItem(entry)

        self._update_counts()

        found = GitRepository(path).discover()
        self.repo = found
        self._refresh_git()
        self.status_message.emit(f"{len(sources)} source file(s) under {path}")

    def _selected_files(self) -> list[Path]:
        return [
            Path(item.data(Qt.ItemDataRole.UserRole))
            for item in self.file_list.selectedItems()
        ]

    def _update_counts(self) -> None:
        self.file_count_label.setText(
            f"{self.file_list.count()} file(s), "
            f"{len(self._selected_files())} selected"
        )

    # -- git ------------------------------------------------------------
    def _refresh_git(self) -> None:
        self.git_status_view.clear()
        self.git_log_view.clear()

        if self.repo is None:
            self.git_status_label.setText(
                "Not a git repository. Nothing here is version-controlled, which "
                "is fine; the rest of the tools still work."
            )
            self.stage_button.setEnabled(False)
            return

        self.stage_button.setEnabled(True)
        try:
            info = self.repo.info()
            self.git_status_label.setText(info.describe())
        except GitError as error:
            self.git_status_label.setText(str(error))
            return

        try:
            for status in self.repo.status():
                entry = QListWidgetItem(status.describe())
                entry.setData(Qt.ItemDataRole.UserRole, status.path)
                self.git_status_view.addItem(entry)
        except GitError as error:
            self.git_status_label.setText(str(error))

        try:
            commits = self.repo.log(10)
            rows = "".join(
                f"<li><code>{_plain(c.sha)}</code> {_plain(c.subject)} "
                f"<span style='color:#9D9D9D'>— {c.author}, {c.relative_time}</span></li>"
                for c in commits
            )
            self.git_log_view.setHtml(
                f"{_HTML}<ul>{rows or '<li>No commits yet.</li>'}</ul>"
            )
        except GitError:
            pass

        self.commit_button.setEnabled(False)

    def _on_stage(self) -> None:
        if self.repo is None:
            return
        paths = [
            self.git_status_view.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.git_status_view.count())
        ]
        if not paths:
            self.status_message.emit("Nothing to stage.")
            return
        try:
            self.repo.stage(paths)
        except GitError as error:
            self.status_message.emit(str(error))
            return
        self._refresh_git()
        self.status_message.emit(f"Staged {len(paths)} path(s). Nothing committed yet.")

    def _on_propose_commit(self) -> None:
        if self.repo is None:
            self.status_message.emit("Select a git repository folder first.")
            return
        message = self.commit_message.text().strip()
        if not message:
            self.status_message.emit("Enter a commit message first.")
            return
        try:
            self.proposal = self.repo.propose_commit(message)
        except GitError as error:
            self.status_message.emit(str(error))
            return

        self.commit_preview.setPlainText(self.proposal.preview())
        self.commit_button.setEnabled(bool(self.proposal.staged_paths))

    def _on_create_commit(self) -> None:
        if self.proposal is None:
            return
        staged = self.proposal.staged_paths
        if not staged:
            self.status_message.emit("Nothing is staged, so there is nothing to commit.")
            return

        # Second, explicit confirmation. The preview was shown a moment ago, but
        # a commit is a write and gets its own confirmation.
        confirmed = QMessageBox.question(
            self,
            "Create this commit?",
            f"{len(staged)} file(s) will be recorded:\n\n"
            + "\n".join(staged[:12])
            + ("\n..." if len(staged) > 12 else "")
            + f"\n\nMessage:\n{self.proposal.message}",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            self.status_message.emit("Commit cancelled. Nothing was written.")
            return

        try:
            sha = self.proposal.execute(confirmed=True)
        except GitError as error:
            self.status_message.emit(str(error))
            return

        self.commit_message.clear()
        self.proposal = None
        self._refresh_git()
        self.status_message.emit(f"Committed {sha[:10]}. Nothing was pushed.")

    # -- review ---------------------------------------------------------
    def _on_review(self) -> None:
        files = self._selected_files()
        if not files:
            self.status_message.emit("Select at least one file to review.")
            return

        root = Path(self.path_edit.text().strip() or ".")
        report = review_mod.static_review(files, relative_to=root)
        self._render_report(report, ai_used=False)

    def _on_ai_review(self) -> None:
        files = self._selected_files()
        if not files:
            self.status_message.emit("Select at least one file to review.")
            return

        root = Path(self.path_edit.text().strip() or ".")
        static = review_mod.static_review(files, relative_to=root)
        self._render_report(static, ai_used=False)

        settings = self._settings()
        if settings is None:
            self.status_message.emit(
                "No AI provider configured, so only the deterministic checks ran. "
                "Those are the confirmed ones."
            )
            return

        self.status_message.emit("Asking the provider for a review…")
        prompt = review_mod.build_review_prompt(files, relative_to=root)
        self._worker = PromptWorker(
            settings, review_mod._REVIEW_SYSTEM, prompt, max_tokens=2000
        )
        self._worker.replied.connect(lambda text: self._on_ai_review_done(text, static))
        self._worker.failed.connect(
            lambda message: self.status_message.emit(f"Review failed: {message}")
        )
        self._worker.start()

    def _on_ai_review_done(self, text: str, static) -> None:
        ai_findings = review_mod.parse_review_response(text)
        merged = review_mod.merge_reports(static, ai_findings)
        self._render_report(merged, ai_used=True)

    def _render_report(self, report, *, ai_used: bool) -> None:
        counts = report.counts()
        parts = [
            f"{_HTML}",
            f"<h3>{_plain(report.summary())}</h3>",
        ]
        if ai_used:
            parts.append(
                "<p><b>Suggestions from the tutor are unproven.</b> They were "
                "not compiled or run. Confirm each one before changing code.</p>"
            )

        for origin in (
            review_mod.Origin.CONFIRMED,
            review_mod.Origin.HEURISTIC,
            review_mod.Origin.SPECULATIVE,
        ):
            items = [f for f in report.sorted_findings() if f.origin is origin]
            if not items:
                continue
            heading = {
                review_mod.Origin.CONFIRMED: "CONFIRMED — a tool reported these",
                review_mod.Origin.HEURISTIC: "HEURISTIC — real signal, needs reading",
                review_mod.Origin.SPECULATIVE: "SUGGESTIONS — unproven",
            }[origin]
            parts.append(f"<h3>{heading}</h3>")
            for finding in items:
                parts.append(
                    f"<p><b>{_plain(finding.location)}</b> — "
                    f"{_plain(finding.title)}"
                    f"<br><span style='color:#9D9D9D'>{_plain(finding.explanation)}</span>"
                )
                if finding.suggested_fix:
                    parts.append(f"<p><b>Suggested:</b> {_plain(finding.suggested_fix)}</p>")
                if origin is not review_mod.Origin.CONFIRMED:
                    parts.append(
                        f"<p><b>Verify:</b> {_plain(finding.verification)}</p>"
                    )
        if not report.findings:
            parts.append("<p>Nothing to report.</p>")

        self.review_view.setHtml("".join(parts))
        self.status_message.emit(report.summary())

    # -- test generation ------------------------------------------------
    def _on_propose_tests(self) -> None:
        files = self._selected_files()
        if not files:
            self.status_message.emit("Select a file to generate tests for.")
            return

        settings = self._settings()

        if settings is None:
            # No provider: fall back to the deterministic checks rather than
            # pretending tests were generated.
            self.test_view.setHtml(
                f"{_HTML}<p>No AI provider is configured, so no tests can be "
                "proposed.</p><p>Configure one in Settings to use this. The "
                "proposed tests are always reviewed by you before anything runs "
                "— nothing is executed automatically.</p>"
            )
            self.status_message.emit("Test generation needs a configured provider.")
            return

        language = testgen_mod.Language(self.test_language.currentData())
        source = "\n\n".join(
            f"# {p.name}\n{p.read_text(encoding='utf-8')}" for p in files[:3]
            if p.is_file()
        )
        prompt = testgen_mod.build_testgen_prompt(source, language=language)

        self.status_message.emit("Proposing tests…")
        self._worker = PromptWorker(
            settings, testgen_mod._GEN_SYSTEM, prompt, max_tokens=2500
        )
        self._worker.replied.connect(self._on_tests_done)
        self._worker.failed.connect(
            lambda message: self.status_message.emit(f"Test generation failed: {message}")
        )
        self._worker.start()

    def _on_tests_done(self, text: str) -> None:
        report = testgen_mod.parse_testgen_response(
            text, language=testgen_mod.Language(self.test_language.currentData())
        )
        blocks = [f"{_HTML}", f"<h3>{_plain(report.summary())}</h3>"]
        blocks.append(
            "<p><b>Nothing below has been run.</b> Review each case before "
            "executing any of it.</p>"
        )
        for test in report.unexecuted:
            blocks.append(
                f"<h4>PROPOSED — {_plain(test.kind.label)}: {_plain(test.name)}</h4>"
                f"<p>{_plain(test.rationale)}</p>"
                f"<pre>{_plain(test.source)}</pre>"
            )
        if report.errors:
            blocks.append("<p><b>Notes:</b></p><ul>")
            blocks += [f"<li>{_plain(e)}</li>" for e in report.errors]
            blocks.append("</ul>")
        self.test_view.setHtml("".join(blocks))
        self.status_message.emit(
            f"{len(report.unexecuted)} proposed test(s), none executed."
        )

    # -- audit ----------------------------------------------------------
    def _on_audit(self) -> None:
        self.status_message.emit("Running the security audit…")
        report = run_audit()
        blocks = [
            f"{_HTML}",
            f"<h3>{_plain(report.verdict)}</h3>",
            f"<p style='color:#9D9D9D'>{_plain(report.platform)} · "
            f"{_plain(report.ran_at)}</p>",
        ]
        for check in report.checks:
            colour = {
                "passed": "#6A9955",
                "failed": "#F14C4C",
                "skipped": "#D7BA7D",
            }[check.status.value]
            blocks.append(
                f"<h3 style='color:{colour}'>{check.status.value.upper()} — "
                f"{_plain(check.name)}</h3>"
                f"<p><b>Proves:</b> {_plain(check.proves)}<br>"
                f"<b>Does not prove:</b> {_plain(check.does_not_prove)}</p>"
            )
            if check.detail:
                blocks.append(f"<p>{_plain(check.detail)}</p>")
        self.audit_view.setHtml("".join(blocks))
        self.status_message.emit(report.verdict)

    # -- workspaces -----------------------------------------------------
    def _refresh_workspaces(self) -> None:
        self.workspace_list.clear()
        for project_id in self.workspaces.list_ids():
            self.workspace_list.addItem(project_id)
        self.workspace_list.currentItemChanged.connect(
            lambda *_: self._show_workspace()
        )

    def _current_workspace(self):
        item = self.workspace_list.currentItem()
        if item is None:
            return None
        return self.workspaces.get(item.text())

    def _on_create_workspace(self) -> None:
        name = self.workspace_name.text().strip()
        if not name:
            self.status_message.emit("Enter a project name first.")
            return
        try:
            workspace = self.workspaces.create(name)
        except WorkspaceError as error:
            self.status_message.emit(str(error))
            return
        self.workspace_name.clear()
        self._refresh_workspaces()
        self.status_message.emit(f"Workspace created at {workspace.layout.root}")

    def _on_save_to_workspace(self) -> None:
        workspace = self._current_workspace()
        if workspace is None:
            self.status_message.emit("Select a workspace first.")
            return
        window = self.window()
        editor = getattr(window, "lesson_view", None)
        editor = getattr(editor, "editor", None) if editor else None
        if editor is None:
            self.status_message.emit("No editor content available to save.")
            return
        try:
            path = workspace.write_source("main.py", editor.code())
        except WorkspaceError as error:
            self.status_message.emit(str(error))
            return
        self.status_message.emit(f"Saved to {path}")
        self._show_workspace()

    def _show_workspace(self) -> None:
        workspace = self._current_workspace()
        if workspace is None:
            self.workspace_detail.clear()
            return
        files = workspace.list_files()
        rows = "".join(f"<li><code>{_plain(f)}</code></li>" for f in files)
        self.workspace_detail.setHtml(
            f"{_HTML}<p><b>{_plain(workspace.project_id)}</b><br>"
            f"{_plain(str(workspace.layout.root))}</p><ul>{rows or '<li>Empty.</li>'}</ul>"
        )