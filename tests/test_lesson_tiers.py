"""Progression tiers: Foundation -> Core -> Advanced.

The target learner is a first-semester computer-science student who wants to
reach advanced fluency in a language. That is a progression, not a flat list,
and before this the curriculum had no difficulty concept at all - every lesson
was simply ordered.

Two rules, both tested here:

* A lesson may declare ``tier:`` in its front matter, and that wins.
* A lesson that does not is placed by position, and the placement is only ever
  a default. It must never produce a tier the UI would present as though the
  author had chosen it.
"""

from __future__ import annotations

import pytest

from mentorsmith.core.curriculum import (
    TIER_ORDER,
    TIERS,
    Lesson,
    tier_for_order,
    tier_index,
)
from mentorsmith.core.curriculum_registry import LANGUAGE_IDS, load_all


class TestTierVocabulary:
    def test_there_are_three_tiers(self) -> None:
        assert TIER_ORDER == ("foundation", "core", "advanced")

    def test_every_tier_is_labelled_and_described(self) -> None:
        for name, entry in TIERS.items():
            assert entry["label"], f"{name} has no label"
            assert entry["blurb"], f"{name} has no description"
            assert isinstance(entry["index"], int)

    def test_unknown_tiers_sort_last(self) -> None:
        assert tier_index("nonsense") >= len(TIER_ORDER)

    def test_known_tiers_sort_in_order(self) -> None:
        assert [tier_index(t) for t in TIER_ORDER] == list(range(len(TIER_ORDER)))


class TestInference:
    @pytest.mark.parametrize(
        "order, expected",
        [
            (1, "foundation"),
            (3, "foundation"),
            (9, "foundation"),
            (10, "core"),
            (15, "core"),
            (16, "advanced"),
            (19, "advanced"),
        ],
    )
    def test_position_places_a_lesson(self, order: int, expected: str) -> None:
        """A 19-lesson track.

        The boundaries land at fraction 0.45 and 0.80, which for 19 lessons
        puts the changeovers at order 10 and order 16. Stated as facts rather
        than guessed, after two versions of this parameter list were wrong.
        """
        assert tier_for_order(order, 19) == expected

    def test_a_single_lesson_track_is_foundation(self) -> None:
        assert tier_for_order(1, 1) == "foundation"

    def test_an_empty_track_is_foundation(self) -> None:
        assert tier_for_order(1, 0) == "foundation"

    def test_inference_is_monotonic(self) -> None:
        """A later lesson is never placed in an earlier tier."""
        ranks = [tier_index(tier_for_order(o, 20)) for o in range(1, 21)]
        assert ranks == sorted(ranks), f"tiers go backwards: {ranks}"


class TestLessonTier:
    def test_a_lesson_defaults_to_foundation(self) -> None:
        assert Lesson(id="x", title="X", order=1).tier == "foundation"

    def test_labels_come_from_the_vocabulary(self) -> None:
        lesson = Lesson(id="x", title="X", order=1, tier="core")
        assert lesson.tier_label == "Core"
        assert lesson.tier_blurb

    def test_an_unknown_tier_does_not_crash_the_label(self) -> None:
        lesson = Lesson(id="x", title="X", order=1, tier="nonsense")
        assert lesson.tier_label == "nonsense"
        assert lesson.tier_blurb == ""


class TestRealCurriculum:
    @pytest.fixture(scope="class")
    def tracks(self):
        return load_all()

    @pytest.mark.parametrize("language", LANGUAGE_IDS)
    def test_every_lesson_has_a_valid_tier(self, tracks, language: str) -> None:
        for lesson in tracks[language].lessons:
            assert lesson.tier in TIERS, (
                f"{language}/{lesson.id} has tier {lesson.tier!r}"
            )

    @pytest.mark.parametrize("language", LANGUAGE_IDS)
    def test_every_track_starts_at_the_beginning(self, tracks, language: str) -> None:
        """Whatever else is true, lesson 1 must be Foundation.

        A learner starting a track has to start at the bottom of it, so this is
        the one structural property that cannot be inferred away.
        """
        lessons = tracks[language].lessons
        assert lessons[0].tier == "foundation", (
            f"{language} opens with {lessons[0].tier!r}: {lessons[0].title}"
        )

    @pytest.mark.parametrize("language", LANGUAGE_IDS)
    def test_tiers_never_go_backwards(self, tracks, language: str) -> None:
        lessons = tracks[language].lessons
        ranks = [l.tier_rank for l in lessons]
        assert ranks == sorted(ranks), (
            f"{language}: {[l.title for l in lessons]}"
        )

    def test_declared_tiers_are_honoured(self) -> None:
        """A declared tier beats the positional guess."""
        tracks = load_all()
        python = tracks["python"].lessons
        classes = next(l for l in python if l.id == "08-classes")
        assert classes.tier == "core", (
            "08-classes declares tier: core but loaded as "
            f"{classes.tier!r}"
        )

    def test_classes_are_not_called_advanced(self) -> None:
        """Objects are first-year material; calling them advanced sets the
        wrong expectation before anyone has written a line."""
        for language in ("python", "cpp", "java"):
            for lesson in load_all()[language].lessons:
                if "class" in lesson.title.lower() or "object" in lesson.title.lower():
                    assert lesson.tier in ("foundation", "core"), (
                        f"{language}/{lesson.id} '{lesson.title}' is "
                        f"{lesson.tier}"
                    )
