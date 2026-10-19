"""Smoke tests for the Phase 5 Developer page.

These construct the real widget offscreen and drive the real slots. They do not
mock git or the audit: the point is that pressing the button does what the
label says, and in particular that pressing "Preview commit" writes nothing.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from mentorsmith.core.db import Database  # noqa: E402
from mentorsmith.ui.developer_view import DeveloperView  # noqa: E402
from mentorsmith.ui.main_window import (  # noqa: E402
    PAGE_DEVELOPER,
    MainWindow,
)

GIT_AVAILABLE = subprocess.run(
    ["git", "--version"], capture_output=True, shell=False
).returncode == 0


@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def database(tmp_path: Path) -> Database:
    db = Database(str(tmp_path / "dev.db"))
    db.connect()
    yield db
    db.close()


@pytest.fixture()
def view(qt_app, database: Database) -> DeveloperView:
    widget = DeveloperView(database)
    yield widget
    widget.close()


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    for args in (
        ["init", "-q", "-b", "main"],
        ["config", "user.email", "t@localhost"],
        ["config", "user.name", "T"],
    ):
        subprocess.run(["git", *args], cwd=root, capture_output=True, check=True)
    (root / "main.py").write_text("print('hi')\n")
    subprocess.run(["git", "add", "main.py"], cwd=root, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=root, capture_output=True, check=True)
    return root


# ======================================================================
class TestConstruction:
    def test_the_page_builds(qt_app, view: DeveloperView) -> None:
        assert view.tabs.count() == 6

    def test_every_phase_five_tool_has_a_tab(self, view: DeveloperView) -> None:
        labels = [view.tabs.tabText(i) for i in range(view.tabs.count())]
        assert labels == [
            "Files", "Git", "Code review", "Test ideas",
            "Security audit", "Workspaces",
        ]

    def test_the_commit_button_starts_disabled(self, view: DeveloperView) -> None:
        assert not view.commit_button.isEnabled(), (
            "the write button must not be live until a preview has been shown"
        )

    def test_the_button_admits_it_only_commits_staged(self, view) -> None:
        assert "staged" in view.commit_button.toolTip().lower()

    def test_source_files_are_listed(self, qt_app, view, tmp_path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        view.path_edit.setText(str(tmp_path))
        view._on_use_folder()
        assert view.file_list.count() >= 1

    def test_build_output_is_not_listed(self, qt_app, view, tmp_path) -> None:
        build = tmp_path / "build"
        build.mkdir()
        (build / "generated.py").write_text("x = 1\n")
        view.path_edit.setText(str(tmp_path))
        view._on_use_folder()
        assert view.file_list.count() == 0, "build output must not be reviewable"

    def test_a_missing_folder_is_reported_not_crashed(self, qt_app, view, tmp_path) -> None:
        view.path_edit.setText(str(tmp_path / "nope"))
        view._on_use_folder()
        assert "Not a folder" in view.file_count_label.text()


class TestGitTab:
    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_a_repository_is_detected(self, qt_app, view, git_repo: Path) -> None:
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        assert view.repo is not None
        assert "branch" in view.git_status_label.text()

    def test_a_plain_folder_says_so(self, qt_app, view, tmp_path: Path) -> None:
        view.path_edit.setText(str(tmp_path))
        view._on_use_folder()
        assert "Not a git repository" in view.git_status_label.text()
        assert not view.stage_button.isEnabled()

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_modified_files_appear(self, qt_app, view, git_repo: Path) -> None:
        (git_repo / "main.py").write_text("print('changed')\n")
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        assert view.git_status_view.count() == 1
        assert "main.py" in view.git_status_view.item(0).text()

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_recent_commits_are_shown(self, qt_app, view, git_repo: Path) -> None:
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        assert "initial" in view.git_log_view.toHtml()

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_preview_commits_nothing(self, qt_app, view, git_repo: Path) -> None:
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        before = len(view.repo.log())
        view.commit_message.setText("should not happen")
        view._on_propose_commit()
        assert len(view.repo.log()) == before
        preview = view.commit_preview.toPlainText()
        assert "Nothing" in preview, "the preview must state nothing would be committed"

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_preview_with_nothing_staged_does_not_enable_the_button(
        self, qt_app, view, git_repo: Path
    ) -> None:
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        view.commit_message.setText("nothing staged")
        view._on_propose_commit()
        assert not view.commit_button.isEnabled()

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_preview_after_staging_enables_the_button(
        self, qt_app, view, git_repo: Path
    ) -> None:
        (git_repo / "new.py").write_text("x = 1\n")
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        view._on_stage()
        view.commit_message.setText("add new.py")
        view._on_propose_commit()
        assert view.commit_button.isEnabled()
        assert "new.py" in view.commit_preview.toPlainText()

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_staging_alone_does_not_commit(self, qt_app, view, git_repo: Path) -> None:
        (git_repo / "new.py").write_text("x = 1\n")
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        before = len(view.repo.log())
        view._on_stage()
        assert len(view.repo.log()) == before

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_an_empty_message_produces_no_preview(self, qt_app, view, git_repo) -> None:
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        view.commit_message.setText("   ")
        view._on_propose_commit()
        assert not view.commit_button.isEnabled()

    @pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")
    def test_staging_a_clean_tree_does_not_commit(self, qt_app, view, git_repo) -> None:
        view.path_edit.setText(str(git_repo))
        view._on_use_folder()
        before = len(view.repo.log())
        view._on_stage()
        assert len(view.repo.log()) == before


class TestReviewTab:
    def test_reviewing_nothing_is_reported(self, qt_app, view) -> None:
        view._on_review()
        assert not view.review_view.toHtml().count("CONFIRMED —")

    def test_findings_are_labelled_by_origin(self, qt_app, view, tmp_path) -> None:
        path = tmp_path / "bad.py"
        path.write_text("import os\ny = eval(user_input)\n")
        view.path_edit.setText(str(tmp_path))
        view._on_use_folder()
        view.file_list.setCurrentRow(0)
        view._on_review()
        html = view.review_view.toHtml()
        assert "HEURISTIC" in html
        assert "Verify:" in html, "an unproven finding must say how to check it"

    def test_a_confirmed_finding_is_labelled_confirmed(self, qt_app, view, tmp_path) -> None:
        path = tmp_path / "broken.py"
        path.write_text("def f(:\n    pass\n")
        view.path_edit.setText(str(tmp_path))
        view._on_use_folder()
        view.file_list.setCurrentRow(0)
        view._on_review()
        assert "CONFIRMED" in view.review_view.toHtml()

    def test_clean_code_produces_no_defects(self, qt_app, view, tmp_path) -> None:
        """Clean code may still earn a suggestion, but never a confirmed defect."""
        path = tmp_path / "clean.py"
        path.write_text("def add(a, b):\n    return a + b\n")
        view.path_edit.setText(str(tmp_path))
        view._on_use_folder()
        view.file_list.setCurrentRow(0)
        view._on_review()
        html = view.review_view.toHtml()
        assert "CONFIRMED \u2014" not in html
        assert "HEURISTIC \u2014" not in html
        # The missing-test note is a suggestion, and is expected to appear.
        assert "SUGGESTIONS" in html

    def test_without_a_provider_no_ai_review_is_claimed(self, qt_app, view, tmp_path, monkeypatch) -> None:
        path = tmp_path / "x.py"
        path.write_text("y = eval(a)\n")
        view.path_edit.setText(str(tmp_path))
        view._on_use_folder()
        view.file_list.setCurrentRow(0)
        monkeypatch.setattr(view, "_settings", lambda: None)
        view._on_ai_review()
        # Falls back to the deterministic pass rather than pretending.
        assert "eval" in view.review_view.toHtml()


class TestAuditTab:
    def test_the_audit_runs_and_states_limits(self, qt_app, view) -> None:
        view._on_audit()
        html = view.audit_view.toHtml()
        assert "Proves:" in html
        assert "Does not prove:" in html

    def test_the_audit_never_claims_security(self, qt_app, view) -> None:
        view._on_audit()
        assert "secure</" not in view.audit_view.toHtml().lower()

    def test_the_verdict_is_shown(self, qt_app, view) -> None:
        view._on_audit()
        assert "NOT a security boundary" in view.audit_view.toHtml()


class TestWorkspaceTab:
    def test_creating_a_workspace(self, qt_app, view, monkeypatch, tmp_path) -> None:
        from mentorsmith.core.workspaces import WorkspaceManager

        monkeypatch.setattr(
            view, "workspaces", WorkspaceManager(tmp_path / "ws")
        )
        view.workspace_name.setText("my game")
        view._on_create_workspace()
        assert view.workspace_list.count() == 1
        assert view.workspace_list.item(0).text() == "my-game"

    def test_an_empty_name_is_refused(self, qt_app, view, monkeypatch, tmp_path) -> None:
        from mentorsmith.core.workspaces import WorkspaceManager

        monkeypatch.setattr(
            view, "workspaces", WorkspaceManager(tmp_path / "ws")
        )
        view.workspace_name.setText("  ")
        view._on_create_workspace()
        assert view.workspace_list.count() == 0

    def test_a_traversal_name_is_refused(self, qt_app, view, monkeypatch, tmp_path) -> None:
        from mentorsmith.core.workspaces import WorkspaceManager

        root = tmp_path / "ws"
        monkeypatch.setattr(view, "workspaces", WorkspaceManager(root))
        view.workspace_name.setText("../../escape")
        view._on_create_workspace()
        assert not (tmp_path / "escape").exists()


class TestMainWindowIntegration:
    def test_the_developer_page_is_registered(self, qt_app, database) -> None:
        window = MainWindow(database)
        assert window.stack.widget(PAGE_DEVELOPER) is window.developer_view
        window.close()

    def test_navigating_to_it_works(self, qt_app, database) -> None:
        window = MainWindow(database)
        window.show_page(PAGE_DEVELOPER)
        assert window.stack.currentIndex() == PAGE_DEVELOPER
        window.close()

    def test_the_app_still_builds_with_seven_pages(self, qt_app, database) -> None:
        window = MainWindow(database)
        assert window.stack.count() >= 7
        window.close()