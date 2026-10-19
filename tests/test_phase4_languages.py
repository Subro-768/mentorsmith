"""Phase 4: multi-language execution adapters, curriculum and isolation."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mentorsmith.compiler.toolchain import Toolchain
from mentorsmith.core import comparisons
from mentorsmith.core import curriculum_registry as registry
from mentorsmith.core.db import Database
from mentorsmith.execution import adapter, detect, detect_all
from mentorsmith.execution.base import LanguageAdapter, ToolMissingError

LANGUAGES = ("cpp", "python", "java", "c", "javascript")


@pytest.fixture()
def work(tmp_path: Path) -> Path:
    path = tmp_path / "work"
    path.mkdir(parents=True, exist_ok=True)
    return path


def make(language: str, work: Path) -> LanguageAdapter:
    return adapter(language, work, sandbox=False)


# ======================================================================
# Registry
# ======================================================================
def test_four_languages_are_registered() -> None:
    assert registry.LANGUAGE_IDS == LANGUAGES


def test_every_language_has_a_label() -> None:
    for language in LANGUAGES:
        assert registry.display_name(language)


def test_unknown_language_is_rejected() -> None:
    assert not registry.known("cobol")
    with pytest.raises(registry.CurriculumError, match="Unknown language"):
        registry.load_track("cobol")


# ======================================================================
# Tool detection
# ======================================================================
def test_detection_reports_availability() -> None:
    for language in LANGUAGES:
        info = detect(language)
        assert info.language == language
        assert info.install_hint, f"{language} has no install hint"


def test_detect_all_covers_every_language() -> None:
    assert set(detect_all()) == set(LANGUAGES)


def test_missing_tool_raises_a_helpful_error(work: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "mentorsmith.execution.base.find_tool", lambda _candidates: None
    )
    instance = make("python", work)
    with pytest.raises(ToolMissingError) as excinfo:
        _ = instance.tool_path
    message = str(excinfo.value)
    assert "python3" in message
    assert "dnf install" in message
    # The message must never claim MentorSmith installed anything.
    assert "does not install software" in message


def test_available_languages_report_their_tool() -> None:
    for language in LANGUAGES:
        if detect(language).available:
            assert detect(language).tool_path


# ======================================================================
# Per-language kinds and filenames
# ======================================================================
def test_compiled_and_interpreted_are_distinguished(work: Path) -> None:
    assert make("cpp", work).kind == "compiled"
    assert make("c", work).kind == "compiled"
    assert make("python", work).kind == "interpreted"
    assert make("javascript", work).kind == "interpreted"


def test_each_language_uses_its_own_extension(work: Path) -> None:
    assert make("cpp", work).extension == ".cpp"
    assert make("c", work).extension == ".c"
    assert make("python", work).extension == ".py"
    assert make("javascript", work).extension == ".mjs"


def test_c_is_forced_into_c_mode(work: Path) -> None:
    """-x c stops a .c file being compiled as C++."""
    argv = make("c", work).compile_argv(
        work / "main.c", work / "program"
    )
    assert "-x" in argv and "c" in argv


def test_cpp_uses_the_cxx_standard(work: Path) -> None:
    argv = make("cpp", work).compile_argv(work / "main.cpp", work / "program")
    assert "-std=c++17" in argv
    assert "-Wall" in argv


# ======================================================================
# Real execution, one language at a time
# ======================================================================
HELLO = {
    "cpp": '#include <iostream>\nint main(){ std::cout << "ok\\n"; return 0; }\n',
    "python": 'print("ok")\n',
    "java": 'public class Main { public static void main(String[] args) { System.out.println("ok"); } }\n',
    "c": '#include <stdio.h>\nint main(void){ printf("ok\\n"); return 0; }\n',
    "javascript": 'console.log("ok");\n',
}


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_language_runs_hello(language: str, work: Path) -> None:
    if not detect(language).available:
        pytest.skip(f"{language} toolchain not installed")
    instance = make(language, work / language)
    build, run = instance.run(HELLO[language])
    assert build.ok, build.stderr
    assert run is not None, f"{language} produced no run result"
    assert run.ok, run.stderr
    assert run.stdout.strip() == "ok"


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_language_reports_failures(language: str, work: Path) -> None:
    if not detect(language).available:
        pytest.skip(f"{language} toolchain not installed")
    instance = make(language, work / ("bad" + language))
    broken = {
        "cpp": "int main() { int x = ; }\n",
        "python": 'print("unterminated\n',
        "java": "public class Main { public static void main(String[] args) { int x = ; } }\n",
        "c": "int main(void) { return zzz; }\n",
        "javascript": "const x = ;\n",
    }[language]
    build, run = instance.run(broken)
    if instance.kind == "compiled":
        assert not build.ok
        assert run is None, "code that failed to compile must not be run"
        assert build.first_error_line
    else:
        assert run is not None and not run.ok
        assert run.stderr.strip(), "an interpreted failure must say something"


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_language_enforces_the_timeout(language: str, work: Path) -> None:
    if not detect(language).available:
        pytest.skip(f"{language} toolchain not installed")
    instance = make(language, work / ("loop" + language))
    instance.run_timeout = 2
    spin = {
        "cpp": "int main(){ for(;;){} }\n",
        "python": "while True:\n    pass\n",
        "java": "public class Main { public static void main(String[] args) { for(;;){} } }\n",
        "c": "int main(void){ for(;;){} return 0; }\n",
        "javascript": "while (true) {}\n",
    }[language]
    _build, run = instance.run(spin)
    assert run is not None
    assert run.timed_out, f"{language} did not stop a runaway program"
    assert "runtime limit" in run.error


def test_python_runs_in_isolated_mode(work: Path) -> None:
    """Env vars must not change interpreter behaviour for untrusted code."""
    if not detect("python").available:
        pytest.skip("python3 not installed")
    instance = make("python", work)
    build, run = instance.run(
        'import os\nprint("isolated" if "PYTHONSTARTUP" not in os.environ else "leak")\n'
    )
    assert run is not None and run.ok, run.stderr


def test_javascript_blocks_eval(work: Path) -> None:
    if not detect("javascript").available:
        pytest.skip("node not installed")
    instance = make("javascript", work)
    _build, run = instance.run(
        'try { eval("1"); console.log("eval allowed"); }\n'
        'catch (e) { console.log("eval blocked"); }\n'
    )
    assert run is not None and run.ok, run.stderr
    assert "eval blocked" in run.stdout


def test_javascript_handles_a_bounded_heap(work: Path) -> None:
    """V8 reserves huge virtual space; the real heap limit must still bite."""
    if not detect("javascript").available:
        pytest.skip("node not installed")
    instance = make("javascript", work)
    assert instance.memory_limit_bytes > (1 << 30), "needs headroom for V8"
    assert "--max-old-space-size" in " ".join(
        instance.run_argv(work / "x.mjs", work / "program")
    )


def test_stdin_reaches_interpreted_languages(work: Path) -> None:
    if not detect("python").available:
        pytest.skip("python3 not installed")
    instance = make("python", work)
    _build, run = instance.run('print("got", input())\n', stdin_data="hello\n")
    assert run is not None and run.ok
    assert "got hello" in run.stdout


# ======================================================================
# Sandbox honesty
# ======================================================================
def test_interpreted_languages_admit_there_is_no_sandbox(work: Path) -> None:
    for language in ("python", "javascript"):
        active, note = make(language, work).sandbox_status()
        assert not active
        assert "no compiled binary" in note.lower()


def test_compiled_sandbox_status_is_honest_when_off(work: Path) -> None:
    active, note = make("cpp", work).sandbox_status()
    assert not active
    assert "Sandbox OFF" in note


@pytest.mark.skipif(not shutil.which("bwrap"), reason="bubblewrap not installed")
def test_sandbox_actually_isolates_c(work: Path) -> None:
    if not detect("c").available:
        pytest.skip("gcc not installed")
    instance = make("c", work)
    instance.sandbox = True
    if not instance.sandbox_status()[0]:
        pytest.skip("sandbox unavailable on this host")
    source = (
        "#include <stdio.h>\n"
        "int main(void) {\n"
        '  FILE *f = fopen("/home/subro/Documents", "r");\n'
        '  printf("read:%s\\n", f ? "VISIBLE" : "blocked");\n'
        "  return 0;\n}\n"
    )
    _build, run = instance.run(source)
    assert run is not None and run.ok, run.stderr
    assert "read:blocked" in run.stdout


# ======================================================================
# Backwards compatibility with the Phase 1 toolchain
# ======================================================================
def test_phase1_toolchain_still_works(tmp_path: Path) -> None:
    toolchain = Toolchain(work_dir=tmp_path / "cpp", sandbox=False)
    info = toolchain.detect()
    assert info.available
    assert info.name in {"g++", "clang++", "c++"}
    build, run = toolchain.run(HELLO["cpp"])
    assert build.ok and run is not None and run.ok


def test_phase1_sandbox_status_shape_is_preserved(tmp_path: Path) -> None:
    toolchain = Toolchain(work_dir=tmp_path / "cpp", sandbox=False)
    active, note = toolchain.sandbox_status()
    assert active is False and "Sandbox OFF" in note


def test_phase1_compile_failure_shape_is_preserved(tmp_path: Path) -> None:
    toolchain = Toolchain(work_dir=tmp_path / "cpp")
    result = toolchain.compile("int main() { int x = ; }\n")
    assert not result.ok
    assert result.exit_code != 0
    assert "main.cpp" in result.stderr


# ======================================================================
# Curriculum per language
# ======================================================================
@pytest.mark.parametrize("language", LANGUAGES)
def test_every_language_loads_a_track(language: str) -> None:
    track = registry.load_track(language)
    assert track.lessons, f"{language} has no lessons"
    assert track.model is not None and track.model.concepts
    assert track.bank is not None and track.bank.exercises


@pytest.mark.parametrize("language", LANGUAGES)
def test_lessons_are_complete(language: str) -> None:
    track = registry.load_track(language)
    required = (
        "objectives", "explanation", "example",
        "knowledge_checks", "exercise", "common_mistakes", "recap",
    )
    for lesson in track.lessons:
        for section in required:
            assert lesson.has_section(section), f"{language}/{lesson.id} missing {section}"
        assert lesson.example_code.strip(), f"{language}/{lesson.id} has no example"
        assert lesson.starter_code.strip(), f"{language}/{lesson.id} has no starter"


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_concept_has_an_exercise(language: str) -> None:
    track = registry.load_track(language)
    uncovered = set(track.model.concepts) - track.bank.concepts_covered()
    assert not uncovered, f"{language} concepts without exercises: {sorted(uncovered)}"


@pytest.mark.parametrize("language", LANGUAGES)
def test_prerequisite_graph_is_valid(language: str) -> None:
    track = registry.load_track(language)
    assert track.model.find_cycle() is None
    ordered = track.model.ordered_ids()
    position = {cid: i for i, cid in enumerate(ordered)}
    for concept in track.model.concepts.values():
        for prerequisite in concept.prerequisites:
            assert position[prerequisite] < position[concept.id]


def test_cpp_curriculum_is_preserved() -> None:
    """Phase 4 must not reduce the existing C++ track."""
    track = registry.load_track("cpp")
    assert len(track.lessons) == 16
    assert len(track.model.concepts) >= 18
    assert len(track.bank.exercises) >= 53


def test_all_eight_exercise_types_exist_across_the_tracks() -> None:
    from mentorsmith.core.exercises import EXERCISE_TYPES

    present: set[str] = set()
    for language in LANGUAGES:
        present |= set(registry.load_track(language).bank.types_present())
    assert present == set(EXERCISE_TYPES)


# ======================================================================
# Progress isolation between languages
# ======================================================================
def test_lesson_completion_is_per_language(database: Database) -> None:
    database.mark_lesson_complete("01-program-structure", "cpp")
    assert database.is_lesson_complete("01-program-structure", "cpp")
    assert not database.is_lesson_complete("01-program-structure", "python")


def test_attempts_are_per_language(database: Database) -> None:
    database.record_exercise_attempt("l", "e", concept_id="types",
                                     language="cpp", correct=True)
    assert len(database.attempts_for_concept("types", "cpp")) == 1
    assert database.attempts_for_concept("types", "python") == []


def test_evidence_is_scoped_per_language(database: Database) -> None:
    database.record_exercise_attempt("l", "e", concept_id="types",
                                     language="cpp", correct=True)
    database.record_exercise_attempt("l", "e2", concept_id="types",
                                     language="python", correct=False)
    assert database.concept_evidence(["types"], "cpp")["types"]["correct"] == 1
    assert database.concept_evidence(["types"], "python")["types"]["correct"] == 0


def test_mastery_does_not_transfer_between_languages(database: Database) -> None:
    """Being strong at C++ pointers says nothing about C pointers."""
    from mentorsmith.core.mastery import assess_many

    for index in range(3):
        database.record_exercise_attempt("09-pointers", f"e{index}",
                                         concept_id="pointers",
                                         language="cpp", correct=True,
                                         hints_used=0)
    cpp = assess_many(database.concept_evidence(["pointers"], "cpp"))
    c_evidence = database.concept_evidence(["c-pointers"], "c")
    assert cpp["pointers"].is_mastered
    assert c_evidence["c-pointers"]["attempts"] == 0


def test_same_lesson_id_in_two_languages_is_two_achievements(database: Database) -> None:
    database.mark_lesson_complete("01-program-structure", "cpp")
    database.mark_lesson_complete("01-program-structure", "c")
    assert database.completed_lessons("cpp")
    assert database.completed_lessons("c")
    assert database.completed_lessons("python") == []


# ======================================================================
# Cross-language comparisons
# ======================================================================
def test_comparisons_cover_the_required_pairs() -> None:
    assert comparisons.for_language_pair("c", "python")
    assert comparisons.for_language_pair("c", "cpp")
    assert comparisons.for_language_pair("cpp", "python")
    assert comparisons.for_language_pair("cpp", "javascript")


def test_comparisons_are_order_independent() -> None:
    assert (
        comparisons.for_language_pair("python", "c")
        == comparisons.for_language_pair("c", "python")
    )


def test_every_comparison_explains_the_difference() -> None:
    for comparison in comparisons.searchable():
        assert comparison.same, comparison.id
        assert comparison.different, f"{comparison.id} claims things are the same"
        assert len(comparison.snippets) == 2
        assert comparison.question.endswith("?")


def test_comparison_mentions_the_real_division_difference() -> None:
    item = comparisons.by_concept("division")[0]
    text = " ".join(item.different)
    assert "3" in text and "3.5" in text
    assert "//" in text, "must mention Python's floor division"


def test_every_language_appears_in_a_comparison() -> None:
    for language in LANGUAGES:
        assert comparisons.for_language(language), f"{language} has no comparison"