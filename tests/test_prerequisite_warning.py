"""Warn when a lesson is opened without its prerequisites met (feature #13).

The concept model carries a prerequisite graph, and the dashboard already
showed a concept's missing prerequisites in a table. Nothing connected that
to the *lesson*: a learner could open "Pointers" with no idea what an
address was, and the app said nothing.

The warning is a heads-up, not a lock. Two deliberate choices:

* it fires for prerequisites that have not been **started**, not merely
  ones that are not mastered - a learner who has had a go at pointers and
  got them wrong is in a much better position than one who never met them,
  and a warning that fires for both teaches people to ignore it;
* it does not stop the lesson opening, because the fastest way to meet a
  prerequisite is often to run into it.
"""

from __future__ import annotations

import pytest

from mentorsmith.services.insights import (
    PrerequisiteGap,
    lesson_prerequisite_gaps,
)


class _Concept:
    def __init__(self, concept_id: str, lesson_id: str, prerequisites: list[str]):
        self.id = concept_id
        self.lesson_id = lesson_id
        self.title = concept_id.title()
        self.prerequisites = prerequisites


class _Model:
    """A tiny stand-in with the two methods the helper uses."""

    def __init__(self, concepts: dict[str, _Concept]):
        self.concepts = concepts

    def concepts_for_lesson(self, lesson_id: str) -> list[str]:
        return [c.id for c in self.concepts.values() if c.lesson_id == lesson_id]

    def get(self, concept_id: str):
        return self.concepts.get(concept_id)


class _Assessment:
    def __init__(self, label: str):
        self.label = label


class TestFindingTheGaps:
    def test_a_lesson_with_no_prerequisites_has_no_gaps(self) -> None:
        model = _Model({"basics": _Concept("basics", "01-basics", [])})
        assert lesson_prerequisite_gaps(model, {}, "01-basics") == []

    def test_an_unstarted_prerequisite_is_a_gap(self) -> None:
        model = _Model({
            "basics": _Concept("basics", "01-basics", []),
            "pointers": _Concept("pointers", "09-pointers", ["basics"]),
        })
        gaps = lesson_prerequisite_gaps(model, {}, "09-pointers")
        assert [g.concept_id for g in gaps] == ["basics"]
        assert gaps[0].label == "not_started"

    def test_a_started_prerequisite_is_not_a_gap(self) -> None:
        model = _Model({
            "basics": _Concept("basics", "01-basics", []),
            "pointers": _Concept("pointers", "09-pointers", ["basics"]),
        })
        gaps = lesson_prerequisite_gaps(
            model, {"basics": _Assessment("developing")}, "09-pointers"
        )
        assert gaps == []

    def test_a_prerequisite_that_was_got_wrong_is_not_a_gap(self) -> None:
        """Started and got wrong is a different state from never started."""
        model = _Model({
            "basics": _Concept("basics", "01-basics", []),
            "pointers": _Concept("pointers", "09-pointers", ["basics"]),
        })
        gaps = lesson_prerequisite_gaps(
            model, {"basics": _Assessment("needs_review")}, "09-pointers"
        )
        assert gaps == []

    def test_the_gap_names_the_lesson_that_teaches_it(self) -> None:
        model = _Model({
            "basics": _Concept("basics", "01-basics", []),
            "pointers": _Concept("pointers", "09-pointers", ["basics"]),
        })
        gaps = lesson_prerequisite_gaps(model, {}, "09-pointers")
        assert gaps[0].lesson_id == "01-basics"

    def test_several_gaps_are_all_reported(self) -> None:
        model = _Model({
            "a": _Concept("a", "01-a", []),
            "b": _Concept("b", "02-b", []),
            "c": _Concept("c", "03-c", ["a", "b"]),
        })
        gaps = lesson_prerequisite_gaps(model, {}, "03-c")
        assert {g.concept_id for g in gaps} == {"a", "b"}

    def test_a_lesson_with_no_concept_has_no_gaps(self) -> None:
        model = _Model({"basics": _Concept("basics", "01-basics", [])})
        assert lesson_prerequisite_gaps(model, {}, "99-nothing") == []

    def test_it_serialises(self) -> None:
        gap = PrerequisiteGap(
            concept_id="basics", title="Basics", label="not_started",
            lesson_id="01-basics",
        )
        data = gap.to_dict()
        assert data["concept_id"] == "basics"
        assert data["lesson_id"] == "01-basics"


class TestTheBanner:
    @pytest.fixture(scope="module")
    def qapp(self):
        from PyQt6.QtWidgets import QApplication

        existing = QApplication.instance()
        app = existing or QApplication([])
        yield app

    @pytest.fixture()
    def view(self, qapp):
        from mentorsmith.compiler.toolchain import Toolchain
        from mentorsmith.ui.lesson_view import LessonView

        widget = LessonView(Toolchain())
        yield widget
        widget.deleteLater()

    def _lesson(self):
        from mentorsmith.core.curriculum import Lesson

        return Lesson(id="09-pointers", title="Pointers", order=9, language="cpp")

    def test_no_banner_when_there_are_no_gaps(self, view) -> None:
        view.set_lesson(self._lesson(), has_previous=True, has_next=True)
        assert view.prereq_banner is None

    def test_a_banner_appears_when_there_are(self, view) -> None:
        view.set_lesson(
            self._lesson(),
            has_previous=True,
            has_next=True,
            prerequisites=[PrerequisiteGap("basics", "Basics", "not_started", "01-basics")],
        )
        assert view.prereq_banner is not None
        assert "Basics" in view.prereq_banner.text()

    def test_the_banner_says_it_is_not_a_block(self, view) -> None:
        view.set_lesson(
            self._lesson(),
            has_previous=True,
            has_next=True,
            prerequisites=[PrerequisiteGap("basics", "Basics", "not_started", "01-basics")],
        )
        text = view.prereq_banner.text()
        assert "Going ahead is fine" in text

    def test_the_banner_goes_away_for_the_next_lesson(self, view) -> None:
        view.set_lesson(
            self._lesson(),
            has_previous=True,
            has_next=True,
            prerequisites=[PrerequisiteGap("basics", "Basics", "not_started", "01-basics")],
        )
        view.set_lesson(self._lesson(), has_previous=True, has_next=True)
        assert view.prereq_banner.isVisibleTo(view) is False

    def test_a_plain_string_also_works(self, view) -> None:
        """The banner does not care where the gap came from."""
        view.set_lesson(
            self._lesson(),
            has_previous=True,
            has_next=True,
            prerequisites=["Basics"],
        )
        assert "Basics" in view.prereq_banner.text()
