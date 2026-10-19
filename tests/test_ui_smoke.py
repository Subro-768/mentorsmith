"""Headless smoke tests for the Qt UI.

These run on Qt's ``offscreen`` platform, so no display is needed. They prove
the widgets construct, the lesson view loads real lesson content, and that a
compile/run result is persisted — they do not assert on visual appearance.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Must be set before PyQt is imported anywhere in the process.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mentorsmith.compiler.toolchain import Toolchain  # noqa: E402
from mentorsmith.core.curriculum import load_lessons  # noqa: E402
from mentorsmith.core.db import Database  # noqa: E402
from mentorsmith.services.insights import build_report  # noqa: E402

pytest.importorskip("PyQt6", reason="PyQt6 is not installed")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from mentorsmith.ui.dashboard import DashboardView, ProgressView  # noqa: E402
from mentorsmith.ui.lesson_view import LessonView  # noqa: E402
from mentorsmith.ui.main_window import (  # noqa: E402
    PAGE_LESSON,
    MainWindow,
)


@pytest.fixture(scope="session")
def qt_app():
    """One QApplication for the whole session, as Qt requires."""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def window(qt_app, tmp_path: Path, monkeypatch):
    """A fully built main window backed by a throwaway database."""
    # Keep settings and work directory inside the test's temp area.
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    from mentorsmith import config

    monkeypatch.setattr(config, "data_dir", lambda: _ensure(tmp_path / "data"))
    monkeypatch.setattr(config, "db_path", lambda: _ensure(tmp_path / "data") / "p.db")
    monkeypatch.setattr(config, "work_dir", lambda: _ensure(tmp_path / "data") / "work")

    window = MainWindow(database=Database(str(tmp_path / "test.db")))
    yield window
    window.toolchain.stop()
    window.close()
    window.deleteLater()


def _ensure(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------
def test_main_window_constructs(window) -> None:
    # Page count is asserted loosely: Phase 2 added practice, insights and
    # project pages, and the count should not be a brittle equality test.
    assert window.stack.count() >= 6
    assert window.windowTitle().startswith("MentorSmith")


def test_all_sixteen_lessons_are_registered(window) -> None:
    assert len(window.lessons) == 16
    assert window.dashboard.lesson_list.count() == 16


def test_dashboard_starts_with_nothing_complete(window) -> None:
    assert window.database.completed_lessons() == []
    assert window.dashboard.progress_bar.value() == 0


def test_toolchain_is_attached_to_the_lesson_view(window) -> None:
    """Phase 4 replaced the C++-only Toolchain with per-language adapters."""
    from mentorsmith.execution.base import LanguageAdapter

    assert isinstance(window.lesson_view.toolchain, LanguageAdapter)
    assert window.lesson_view.toolchain.language_id == window.language


def test_language_switch_reloads_the_track(window) -> None:
    """Switching language must change lessons and scope progress."""
    assert window.language == "cpp"
    cpp_ids = {lesson.id for lesson in window.lessons}

    window.switch_language("python")
    assert window.language == "python"
    python_ids = {lesson.id for lesson in window.lessons}
    assert python_ids != cpp_ids
    assert window.toolchain.language_id == "python"


def test_progress_is_tracked_per_language(window) -> None:
    """A C++ completion must not appear as a Python completion."""
    window.database.mark_lesson_complete("01-program-structure", "cpp")
    assert window.database.is_lesson_complete("01-program-structure", "cpp")
    assert not window.database.is_lesson_complete("01-program-structure", "python")


# ----------------------------------------------------------------------
# Lesson loading
# ----------------------------------------------------------------------
def test_opening_a_lesson_loads_content(window) -> None:
    lesson = window.lessons[0]
    window.open_lesson(lesson.id)

    assert window.lesson_view.lesson is not None
    assert window.lesson_view.lesson.id == lesson.id
    assert window.stack.currentIndex() == PAGE_LESSON
    assert lesson.title in window.lesson_view.title_label.text()
    assert window.lesson_view.editor.code().strip()


def test_editor_is_prefilled_with_starter_code(window) -> None:
    window.open_lesson(window.lessons[0].id)
    assert window.lesson_view.editor.code() == window.lessons[0].starter_code


def test_navigation_buttons_respect_the_ends(window) -> None:
    window.open_lesson(window.lessons[0].id)
    assert not window.lesson_view.prev_button.isEnabled()
    assert window.lesson_view.next_button.isEnabled()

    window.open_lesson(window.lessons[-1].id)
    assert window.lesson_view.prev_button.isEnabled()
    assert not window.lesson_view.next_button.isEnabled()


def test_opening_unknown_lesson_is_a_no_op(window) -> None:
    before = window.current_lesson_id
    window.open_lesson("no-such-lesson")
    assert window.current_lesson_id == before


def test_knowledge_checks_render_for_every_lesson(window) -> None:
    for lesson in window.lessons:
        window.open_lesson(lesson.id)
        assert window.lesson_view.check_widgets, f"{lesson.id} rendered no checks"
        assert len(window.lesson_view.check_widgets) == len(lesson.checks)


# ----------------------------------------------------------------------
# Persistence through the UI
# ----------------------------------------------------------------------
def test_marking_complete_persists(window) -> None:
    lesson = window.lessons[0]
    window.open_lesson(lesson.id)
    window.lesson_view.on_complete_clicked()

    assert window.database.is_lesson_complete(lesson.id)
    assert lesson.id in window.database.completed_lessons()
    # Phase 1 lesson completion does not make a concept "strong": lesson
    # progress is deliberately not counted as evidence of understanding.
    progress = window.database.get_concept_progress("program-structure")
    assert progress is None or progress["label"] != "strong"


def test_completion_survives_a_window_restart(qt_app, tmp_path: Path) -> None:
    """The 'progress persists after restart' acceptance item."""
    from mentorsmith import config

    data = _ensure(tmp_path / "shared")
    original = config.data_dir
    config.data_dir = lambda: data
    try:
        db_path = data / "restart.db"

        first = MainWindow(database=Database(str(db_path)))
        lesson_id = first.lessons[3].id
        first.open_lesson(lesson_id)
        first.lesson_view.on_complete_clicked()
        first.database.record_exercise_attempt(
            lesson_id, lesson_id, compiled_ok=True, ran_ok=True, result="ran, exit 0"
        )
        first.close()

        second = MainWindow(database=Database(str(db_path)))
        assert second.database.is_lesson_complete(lesson_id)
        assert second.database.attempt_count(lesson_id, lesson_id) == 1
        second.close()
    finally:
        config.data_dir = original


def test_attempt_is_recorded_when_a_run_finishes(window) -> None:
    lesson = window.lessons[0]
    window.open_lesson(lesson.id)

    from mentorsmith.compiler.toolchain import CommandResult

    compile_result = CommandResult(ok=True, stdout="", stderr="", exit_code=0)
    run_result = CommandResult(ok=True, stdout="ok\n", exit_code=0)
    window.lesson_view._on_compile_finished(compile_result, run_result)

    attempts = window.database.exercise_attempts(lesson.id)
    assert len(attempts) == 1
    assert attempts[0]["compiled_ok"] == 1
    assert attempts[0]["ran_ok"] == 1


def test_failed_compile_is_recorded_as_a_failure(window) -> None:
    lesson = window.lessons[0]
    window.open_lesson(lesson.id)

    from mentorsmith.compiler.toolchain import CommandResult

    compile_result = CommandResult(
        ok=False, stderr="error: expected ';'", exit_code=1, error="Compilation failed."
    )
    window.lesson_view._on_compile_finished(compile_result, None)

    attempts = window.database.exercise_attempts(lesson.id)
    assert len(attempts) == 1
    assert attempts[0]["compiled_ok"] == 0
    assert attempts[0]["result"] == "compile failed"


# ----------------------------------------------------------------------
# Offline behaviour
# ----------------------------------------------------------------------
def test_chat_is_disabled_with_no_provider(window, monkeypatch) -> None:
    monkeypatch.setenv("MENTORSMITH_API_KEY", "")
    window._refresh_provider_status()
    chat = window.lesson_view.chat()
    assert not chat.send_button.isEnabled()


def test_asking_the_tutor_offline_explains_itself(window, monkeypatch) -> None:
    monkeypatch.setenv("MENTORSMITH_API_KEY", "")
    monkeypatch.delenv("MENTORSMITH_OFFLINE", raising=False)
    window.open_lesson(window.lessons[0].id)
    window._refresh_provider_status()

    window.lesson_view._on_ask_tutor()
    transcript = window.lesson_view.chat().transcript.toPlainText()
    assert "MENTORSMITH_API_KEY" in transcript


def test_offline_flag_blocks_tutor_calls(window, monkeypatch) -> None:
    monkeypatch.setenv("MENTORSMITH_OFFLINE", "1")
    window.open_lesson(window.lessons[0].id)
    window._refresh_provider_status()

    window.lesson_view._on_tutor_message("hello", "guided")
    transcript = window.lesson_view.chat().transcript.toPlainText()
    assert "MENTORSMITH_OFFLINE" in transcript


# ----------------------------------------------------------------------
# Standalone widgets
# ----------------------------------------------------------------------
def test_dashboard_renders_progress(qt_app) -> None:
    lessons = load_lessons()
    view = DashboardView()
    view.set_lessons(lessons)
    view.refresh(completed={lessons[0].id, lessons[1].id})

    # 2 of 16 is 12.5%, which Python's round() resolves to 12.
    assert view.progress_bar.value() == 12
    assert "2 of 16" in view.progress_label.text()


def test_dashboard_shows_an_empty_activity_message(qt_app) -> None:
    view = DashboardView()
    view.set_activity([])
    assert "Nothing recorded yet" in view.activity_view.toPlainText()


def test_progress_view_renders(qt_app) -> None:
    view = ProgressView()
    view.set_lessons(load_lessons())
    view.refresh(Database(":memory:"), [])
    assert "0 of 16" in view.summary.text()


# ----------------------------------------------------------------------
# Phase 2: practice, insights and projects
# ----------------------------------------------------------------------
def test_phase2_pages_exist(window) -> None:
    from mentorsmith.ui.main_window import (
        PAGE_DEVELOPER,
        PAGE_INSIGHTS,
        PAGE_PRACTICE,
        PAGE_PROJECTS,
    )

    # Eight pages with Analytics added.
    assert window.stack.count() >= 7
    assert window.stack.widget(PAGE_PRACTICE) is not None
    assert window.stack.widget(PAGE_INSIGHTS) is not None
    assert window.stack.widget(PAGE_PROJECTS) is not None
    assert window.stack.widget(PAGE_DEVELOPER) is not None


def test_practice_view_auto_selects_the_top_recommendation(window) -> None:
    """The screen opens ready to work on the best suggestion."""
    assert window.practice_view.recommendation_list.count() > 0
    assert window.practice_view.session is not None
    assert window.practice_view.session.exercise is not None


def test_recommendations_are_listed_with_reasons(window) -> None:
    """Phase 2 requires a suggested activity *with its reason*."""
    assert window.practice_view.recommendation_list.count() > 0
    first = window.practice_view.recommendation_list.item(0)
    assert first.toolTip(), "a recommendation arrived without a reason"


def test_insights_explains_its_next_activity(window) -> None:
    window.refresh_insights()
    assert window.insights.next_reason.text()
    assert "graded attempts" in window.insights.next_reason.text().lower() or \
           "prerequisites" in window.insights.next_reason.text().lower()


def test_insights_states_what_is_not_evidence(window) -> None:
    window.refresh_insights()
    assert "not counted" in window.insights.disclaimer.text().lower()


def test_loading_a_practice_exercise_configures_the_editor(window) -> None:
    exercise = window.bank.get("types-fix-division")
    window.practice_view.load_exercise(exercise)
    assert window.practice_view.session is not None
    assert window.practice_view.editor.code().strip()
    assert "compiling and running" in window.practice_view.grade_label.text()


def test_interpretive_exercise_uses_the_answer_box(window) -> None:
    exercise = window.bank.get("types-explain-division")
    window.practice_view.load_exercise(exercise)
    assert window.practice_view.tabs.currentWidget() is window.practice_view.answer_edit
    assert "opinion" in window.practice_view.grade_label.text().lower()


def test_solve_without_ai_disables_hints_in_the_ui(window) -> None:
    exercise = window.bank.get("io-solve-no-ai")
    window.practice_view.load_exercise(exercise)
    assert not window.practice_view.hint_button.isEnabled()
    assert "disabled" in window.practice_view.hint_button.text().lower()


def test_projects_are_proposed_with_rationale(window) -> None:
    window.refresh_insights()
    assert window.projects_view.project_list.count() > 0
    first = window.projects_view.project_list.item(0)
    assert first.toolTip()


def test_graded_attempt_updates_the_report(window) -> None:
    """History must actually change what the dashboard recommends."""
    from mentorsmith.services.practice import PracticeSession

    exercise = window.bank.get("types-fix-division")
    before = window.database.total_attempts() if hasattr(
        window.database, "total_attempts"
    ) else 0
    session = PracticeSession(
        database=window.database, toolchain=window.toolchain, exercise=exercise
    )
    session.submit("#include <iostream>\nint main(){ return 0; }\n")
    after = build_report(window.database, window.model, window.bank)
    assert after.total_attempts > before
    assert after.recommendations


# ----------------------------------------------------------------------
# Editor and markdown rendering
# ----------------------------------------------------------------------
def test_markdown_converter_handles_fenced_code() -> None:
    from mentorsmith.ui.code_editor import markdown_to_html

    html = markdown_to_html("## Example\n```cpp\nint main(){}\n```")
    assert "<h2>" in html
    assert "int main(){}" in html
    assert "<pre" in html


def test_markdown_converter_escapes_html() -> None:
    from mentorsmith.ui.code_editor import markdown_to_html

    html = markdown_to_html("Use <script>alert(1)</script> carefully")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_editor_emits_its_text(qt_app) -> None:
    from mentorsmith.ui.code_editor import CodeEditor

    seen: list[str] = []
    editor = CodeEditor()
    editor.text_changed.connect(seen.append)
    editor.set_code("int main(){}")
    assert seen and seen[-1] == "int main(){}"
    assert editor.code() == "int main(){}"