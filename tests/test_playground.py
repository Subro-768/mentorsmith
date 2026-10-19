"""Tests for interactive playground view and multi-language projects."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from mentorsmith.core import curriculum_registry
from mentorsmith.ui.playground_view import PlaygroundView


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_playground_view_initialization(qapp: QApplication) -> None:
    view = PlaygroundView()
    assert view.language == "cpp"
    assert view.lang_combo.count() == 5
    assert len(view.editor.code()) > 0
    assert "std::cout" in view.editor.code()


def test_playground_view_language_switch(qapp: QApplication) -> None:
    view = PlaygroundView()
    view.set_language("python")
    assert view.language == "python"
    assert "print" in view.editor.code()

    view.set_language("java")
    assert view.language == "java"
    assert "public class Main" in view.editor.code()


def test_all_languages_have_capstone_projects() -> None:
    for lang in curriculum_registry.LANGUAGE_IDS:
        track = curriculum_registry.load_track(lang)
        assert track.model is not None
        assert len(track.model.projects) >= 3, f"Expected projects for {lang}"
        for pid, proj in track.model.projects.items():
            assert proj.id
            assert proj.title
            assert proj.purpose
            assert len(proj.milestones) >= 3
            assert proj.difficulty in ("beginner", "intermediate", "advanced")


# ======================================================================
# Regression: the Run button.
#
# PlaygroundView.run_code originally called adapter.run_code(), which exists
# on no adapter, and read result.compiled / result.ran, which exist on no
# result. Pressing Run raised AttributeError and left the UI stuck on
# "Running...". The three tests above never pressed it, so the suite was green
# against a completely broken feature.
#
# These tests press Run for real, for every language.
# ======================================================================
def _run(view, code: str, stdin: str = "") -> None:
    view.editor.set_code(code)
    view.stdin_input.setPlainText(stdin)
    view.run_code()


def test_run_reports_success(qapp: QApplication) -> None:
    if not curriculum_registry.known("python"):
        pytest.skip("python track missing")
    view = PlaygroundView()
    view.set_language("python")
    _run(view, 'print("hello")\n')
    assert "Success" in view.status_chip.text()
    assert "hello" in view.output_view.toPlainText()


def test_run_reports_a_compile_error(qapp: QApplication) -> None:
    if not curriculum_registry.known("cpp"):
        pytest.skip("cpp track missing")
    view = PlaygroundView()
    view.set_language("cpp")
    _run(view, "int main() { int x = ; }\n")
    assert "Compile Error" in view.status_chip.text()
    # The compiler's own diagnostic must reach the learner.
    assert "error" in view.output_view.toPlainText().lower()


def test_run_reports_a_runtime_error(qapp: QApplication) -> None:
    if not curriculum_registry.known("python"):
        pytest.skip("python track missing")
    view = PlaygroundView()
    view.set_language("python")
    _run(view, "import sys\nsys.exit(3)\n")
    assert "Runtime Error" in view.status_chip.text()
    assert "3" in view.output_view.toPlainText()


def test_run_reports_a_timeout(qapp: QApplication) -> None:
    if not curriculum_registry.known("python"):
        pytest.skip("python track missing")
    view = PlaygroundView()
    view.set_language("python")
    _run(view, "while True:\n    pass\n")
    assert "Timed out" in view.status_chip.text()


def test_run_passes_stdin(qapp: QApplication) -> None:
    if not curriculum_registry.known("python"):
        pytest.skip("python track missing")
    view = PlaygroundView()
    view.set_language("python")
    _run(view, 'x = int(input())\nprint("got", x)\n', stdin="7\n")
    assert "Success" in view.status_chip.text()
    assert "got 7" in view.output_view.toPlainText()


def test_output_is_html_escaped(qapp: QApplication) -> None:
    """A program printing markup must not be able to inject HTML into the pane."""
    if not curriculum_registry.known("python"):
        pytest.skip("python track missing")
    view = PlaygroundView()
    view.set_language("python")
    _run(view, 'print("<b>not bold</b>")\n')
    assert "<b>not bold</b>" not in view.output_view.toHtml()
    assert "not bold" in view.output_view.toPlainText()


def test_run_never_leaves_the_chip_pending(qapp: QApplication) -> None:
    """The old AttributeError left the UI stuck on "Running..." forever."""
    if not curriculum_registry.known("python"):
        pytest.skip("python track missing")
    view = PlaygroundView()
    view.set_language("python")
    for code in ('print(1)\n', "import sys; sys.exit(1)\n", "def f(:\n"):
        _run(view, code)
        assert "Running" not in view.status_chip.text(), f"stuck after: {code!r}"


def test_java_is_selectable_and_runs(qapp: QApplication) -> None:
    if not curriculum_registry.known("java"):
        pytest.skip("java track missing")
    from mentorsmith.execution import detect

    if not detect("java").available:
        pytest.skip("no java toolchain installed")
    view = PlaygroundView()
    view.set_language("java")
    _run(
        view,
        'public class Main { public static void main(String[] a) '
        '{ System.out.println("java ok"); } }\n',
    )
    assert "Success" in view.status_chip.text()
    assert "java ok" in view.output_view.toPlainText()
