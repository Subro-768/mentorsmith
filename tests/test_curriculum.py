"""Curriculum loading and lesson file format."""

from __future__ import annotations

from pathlib import Path

import pytest

from mentorsmith.core.curriculum import (
    CurriculumError,
    adjacent_lesson,
    lesson_index,
    load_lessons,
    parse_lesson,
)

# The 16 topics the handoff requires.
EXPECTED_TOPICS = [
    "program-structure",
    "variables-and-types",
    "input-output",
    "operators",
    "conditions",
    "loops",
    "functions",
    "arrays-and-strings",
    "pointers",
    "references",
    "memory-concepts",
    "structures",
    "classes-and-objects",
    "constructors-encapsulation",
    "file-handling",
    "exceptions-and-error-handling",
]


@pytest.fixture(scope="module")
def lessons():
    return load_lessons()


# ----------------------------------------------------------------------
# The shipped curriculum
# ----------------------------------------------------------------------
def test_every_lesson_file_is_shipped(lessons) -> None:
    """A lesson file with no lesson, or a lesson with no file, is a bug.

    The count is derived rather than written down: it was 16 when this test
    was made and is different now, and a hard-coded figure only ever
    reports that someone forgot to update it.
    """
    from mentorsmith.core.curriculum import lessons_dir

    files = sorted(lessons_dir("cpp").glob("*.md"))
    assert len(lessons) == len(files), (
        f"{len(lessons)} lessons loaded but {len(files)} files on disk"
    )
    assert len(lessons) >= 16, "the C++ track has shrunk"


def test_every_required_topic_is_present(lessons) -> None:
    ids = " ".join(lesson.id for lesson in lessons)
    for topic in EXPECTED_TOPICS:
        assert topic in ids, f"missing lesson for {topic}"


def test_lessons_are_in_declared_order(lessons) -> None:
    orders = [lesson.order for lesson in lessons]
    assert orders == sorted(orders)
    # Contiguous from 1, whatever the total is.
    assert orders == list(range(1, len(orders) + 1))


def test_every_lesson_has_every_required_section(lessons) -> None:
    required = (
        "objectives",
        "explanation",
        "example",
        "knowledge_checks",
        "exercise",
        "common_mistakes",
        "recap",
    )
    for lesson in lessons:
        for section in required:
            assert lesson.has_section(section), f"{lesson.id} is missing {section}"


def test_every_lesson_has_compilable_example_and_starter_code(lessons) -> None:
    for lesson in lessons:
        assert lesson.example_code.strip(), f"{lesson.id} has no example"
        assert lesson.starter_code.strip(), f"{lesson.id} has no starter code"
        assert "main" in lesson.example_code, f"{lesson.id} example has no main()"


def test_every_lesson_has_knowledge_checks_with_answers(lessons) -> None:
    for lesson in lessons:
        assert len(lesson.checks) >= 3, f"{lesson.id} has too few checks"
        for question, answer in lesson.checks:
            assert question.strip()
            assert answer.strip(), f"{lesson.id} has a check with no answer"


def test_lesson_ids_are_unique(lessons) -> None:
    ids = [lesson.id for lesson in lessons]
    assert len(ids) == len(set(ids))


def test_display_title_includes_the_order(lessons) -> None:
    assert lessons[0].display_title.startswith("1. ")
    assert lessons[0].display_title.endswith("Program Structure")


# ----------------------------------------------------------------------
# Navigation helpers
# ----------------------------------------------------------------------
def test_lesson_index_maps_id_to_position(lessons) -> None:
    index = lesson_index(lessons)
    assert index[lessons[0].id] == 0
    assert index[lessons[-1].id] == len(lessons) - 1


def test_adjacent_lesson_moves_forwards_and_backwards(lessons) -> None:
    first = lessons[0]
    assert adjacent_lesson(lessons, first.id, 1) is lessons[1]
    assert adjacent_lesson(lessons, first.id, -1) is None


def test_adjacent_lesson_stops_at_the_end(lessons) -> None:
    last = lessons[-1]
    assert adjacent_lesson(lessons, last.id, 1) is None
    assert adjacent_lesson(lessons, last.id, -1) is lessons[-2]


def test_adjacent_lesson_for_unknown_id(lessons) -> None:
    assert adjacent_lesson(lessons, "nope", 1) is None


# ----------------------------------------------------------------------
# Parsing edge cases
# ----------------------------------------------------------------------
def test_parse_lesson_reads_front_matter(tmp_path: Path) -> None:
    path = tmp_path / "x.md"
    path.write_text(
        "---\nid: custom-id\ntitle: Custom Title\norder: 7\n---\n\n"
        "## Objectives\n- one\n\n"
        "## Exercise\n```cpp starter\nint main(){}\n```\n",
        encoding="utf-8",
    )
    lesson = parse_lesson(path)
    assert lesson.id == "custom-id"
    assert lesson.title == "Custom Title"
    assert lesson.order == 7
    assert lesson.starter_code == "int main(){}"


def test_front_matter_is_optional(tmp_path: Path) -> None:
    path = tmp_path / "plain-lesson.md"
    path.write_text("## Explanation\nJust prose.\n", encoding="utf-8")
    lesson = parse_lesson(path)
    assert lesson.id == "plain-lesson"
    assert lesson.title == "Plain Lesson"
    assert lesson.has_section("explanation")


def test_non_numeric_order_does_not_crash(tmp_path: Path) -> None:
    path = tmp_path / "bad-order.md"
    path.write_text(
        "---\nid: bad-order\norder: not-a-number\n---\n\n## Recap\nx\n",
        encoding="utf-8",
    )
    assert parse_lesson(path).order == 0


def test_unknown_sections_are_preserved(tmp_path: Path) -> None:
    path = tmp_path / "extra.md"
    path.write_text("## Explanation\na\n\n## Bonus Material\nb\n", encoding="utf-8")
    assert parse_lesson(path).section("bonus_material") == "b"


def test_repeated_headings_are_concatenated(tmp_path: Path) -> None:
    path = tmp_path / "split.md"
    path.write_text("## Explanation\nfirst\n\n## Explanation\nsecond\n", encoding="utf-8")
    body = parse_lesson(path).section("explanation")
    assert "first" in body and "second" in body


def test_load_lessons_raises_on_missing_directory(tmp_path: Path) -> None:
    with pytest.raises(CurriculumError):
        load_lessons(tmp_path / "does-not-exist")


def test_load_lessons_raises_on_empty_directory(tmp_path: Path) -> None:
    with pytest.raises(CurriculumError):
        load_lessons(tmp_path)