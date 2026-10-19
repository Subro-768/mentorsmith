"""A "review today" card, and the "you got this wrong N times" badge.

Feature #7 and #11 on the list. The spaced-repetition scheduler already
computed which concepts looked weak or stale, and the dashboard already
listed them - but as a flat list of paragraphs, with no count, no reason to
look at the first one rather than the fifth, and nothing saying how many
times a concept had actually been got wrong.

Two things are being fixed:

* the card leads with a sentence saying what is worth doing today, and has
  a button that opens the lesson;
* each item carries a badge with the number of wrong attempts, because a
  concept failed four times is a different problem from one that is merely
  stale.
"""

from __future__ import annotations

import pytest

from mentorsmith.core.revision import ReviewItem


def _item(**kwargs) -> ReviewItem:
    base = {
        "concept_id": "pointers",
        "title": "Pointers",
        "reason": "Recommended because the first attempt was wrong.",
        "evidence": [],
        "urgency": 1.0,
    }
    base.update(kwargs)
    return ReviewItem(**base)


class TestTheWrongBadge:
    def test_no_wrong_attempts_means_no_badge(self) -> None:
        assert _item(wrong=0).wrong_badge == ""

    def test_one_wrong_attempt_reads_naturally(self) -> None:
        assert _item(wrong=1).wrong_badge == "wrong once"

    def test_several_wrong_attempts_are_counted(self) -> None:
        assert _item(wrong=4).wrong_badge == "wrong 4 times"

    def test_it_is_carried_in_the_serialised_form(self) -> None:
        data = _item(attempts=5, wrong=3).to_dict()
        assert data["wrong"] == 3
        assert data["attempts"] == 5


class TestTheReviewCounts:
    def test_a_fresh_report_has_nothing_due(self) -> None:
        from mentorsmith.services.insights import DashboardReport

        report = DashboardReport()
        assert report.review_due == 0
        assert report.review_wrong == 0
        assert "Nothing is flagged" in report.review_today_line()

    def test_it_counts_concepts_not_attempts(self) -> None:
        """One concept failed four times is one thing to revisit."""
        from mentorsmith.services.insights import DashboardReport

        report = DashboardReport()
        report.reviews = [_item(attempts=4, wrong=4)]
        report.review_due = len(report.reviews)
        report.review_wrong = sum(i.wrong for i in report.reviews)
        assert report.review_due == 1
        assert report.review_wrong == 4
        assert "1 concept" in report.review_today_line()

    def test_it_pluralises(self) -> None:
        from mentorsmith.services.insights import DashboardReport

        report = DashboardReport()
        report.review_due = 3
        report.review_wrong = 7
        line = report.review_today_line()
        assert "3 concepts" in line
        assert "7 wrong attempt" in line

    def test_it_does_not_claim_mastery(self) -> None:
        """An empty queue must not read as "you know everything"."""
        from mentorsmith.services.insights import DashboardReport

        line = DashboardReport().review_today_line()
        assert "not the same as" in line

    def test_the_counts_are_in_the_serialised_form(self) -> None:
        from mentorsmith.services.insights import DashboardReport

        report = DashboardReport()
        report.review_due = 2
        report.review_wrong = 5
        data = report.to_dict()
        assert data["review_due"] == 2
        assert data["review_wrong"] == 5


class TestTheCard:
    @pytest.fixture(scope="module")
    def qapp(self):
        from PyQt6.QtWidgets import QApplication

        existing = QApplication.instance()
        app = existing or QApplication([])
        yield app

    @pytest.fixture()
    def panel(self, qapp):
        from mentorsmith.ui.dashboard import InsightsPanel

        widget = InsightsPanel()
        yield widget
        widget.deleteLater()

    def _report(self, reviews):
        from mentorsmith.services.insights import DashboardReport

        report = DashboardReport()
        report.reviews = reviews
        report.review_due = len(reviews)
        report.review_wrong = sum(i.wrong for i in reviews)
        return report

    def test_the_headline_says_what_is_due(self, panel) -> None:
        panel.set_report(self._report([_item(wrong=2)]))
        assert "1 concept" in panel.review_headline.text()

    def test_the_badge_is_shown(self, panel) -> None:
        panel.set_report(self._report([_item(wrong=3)]))
        assert "wrong 3 times" in panel.review_view.toPlainText()

    def test_no_badge_when_nothing_was_wrong(self, panel) -> None:
        """The reason text may say "the first attempt was wrong" - that is
        the reason, not the badge. The badge is the counted one."""
        panel.set_report(self._report([_item(wrong=0)]))
        text = panel.review_view.toPlainText()
        assert "wrong once" not in text
        assert "wrong 0 times" not in text

    def test_the_button_is_off_when_there_is_nothing_to_do(self, panel) -> None:
        panel.set_report(self._report([]))
        assert panel.review_button.isEnabled() is False

    def test_the_button_is_on_when_there_is(self, panel) -> None:
        panel.set_report(self._report([_item(wrong=1)]))
        assert panel.review_button.isEnabled() is True

    def test_pressing_it_asks_for_the_lesson(self, panel) -> None:
        seen: list[str] = []
        panel.review_lesson_requested.connect(seen.append)

        class Concept:
            lesson_id = "09-pointers"

        class Model:
            def get(self, concept_id: str):
                return Concept() if concept_id == "pointers" else None

        panel.set_report(self._report([_item(concept_id="pointers")]), Model())
        panel.review_button.click()
        assert seen == ["09-pointers"]

    def test_pressing_it_with_no_model_does_nothing(self, panel) -> None:
        seen: list[str] = []
        panel.review_lesson_requested.connect(seen.append)
        panel.set_report(self._report([_item(concept_id="pointers")]))
        panel.review_button.click()
        assert seen == []
