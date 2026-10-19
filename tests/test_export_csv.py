"""Export the learner's data as CSV (feature #15).

The learning curve lives in the app's database, which is also where the
app's own state lives. If the learner wants to keep it, chart it or move it
somewhere else, they should be able to take it with them.

The tests here hold the export to two things:

* it writes **what the app holds**, without re-interpreting it - a row that
  says "correct" is a row the database says is correct;
* it says what the columns mean, because a CSV with unexplained column
  names is data the learner cannot use without reverse-engineering it.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from mentorsmith.core.db import Database
from mentorsmith.services.export import (
    ATTEMPT_COLUMNS,
    CONCEPT_COLUMNS,
    collect_datasets,
    export_summary,
    export_to_folder,
    write_csv,
    write_readme,
)


@pytest.fixture()
def database():
    db = Database(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture()
def model():
    from mentorsmith.core.curriculum_registry import load_track

    return load_track("cpp").model


def _attempt(db, **kwargs):
    payload = {
        "lesson_id": "09-pointers",
        "exercise_id": "ex-1",
        "source": "s",
        "compiled_ok": True,
        "ran_ok": True,
        "exercise_type": "predict-output",
        "concept_id": "pointers",
        "correct": True,
        "hints_used": 0,
        "language": "cpp",
    }
    payload.update(kwargs)
    return db.record_exercise_attempt(**payload)


class TestCollecting:
    def test_an_empty_database_gives_empty_datasets(
        self, database, model
    ) -> None:
        datasets = collect_datasets(database, model, "cpp")
        assert set(datasets) == {"attempts", "concepts", "lessons", "reviews"}
        assert datasets["attempts"] == []

    def test_attempts_come_out_oldest_first(self, database, model) -> None:
        _attempt(database, exercise_id="first")
        _attempt(database, exercise_id="second")
        rows = collect_datasets(database, model, "cpp")["attempts"]
        assert [r["exercise_id"] for r in rows] == ["first", "second"]

    def test_a_correct_attempt_is_marked_correct(self, database, model) -> None:
        _attempt(database, correct=True)
        row = collect_datasets(database, model, "cpp")["attempts"][0]
        assert row["correct"] == 1
        assert row["independent"] == 1

    def test_a_wrong_attempt_is_marked_wrong(self, database, model) -> None:
        _attempt(database, correct=False, hints_used=2)
        row = collect_datasets(database, model, "cpp")["attempts"][0]
        assert row["correct"] == 0
        assert row["hints_used"] == 2
        assert row["independent"] == 0

    def test_the_error_category_is_kept(self, database, model) -> None:
        _attempt(database, correct=False, error_category="missing_semicolon")
        row = collect_datasets(database, model, "cpp")["attempts"][0]
        assert row["error_category"] == "missing_semicolon"

    def test_attempts_from_another_language_are_left_out(
        self, database, model
    ) -> None:
        _attempt(database, language="python")
        rows = collect_datasets(database, model, "cpp")["attempts"]
        assert rows == []

    def test_every_concept_in_the_track_is_listed(self, database, model) -> None:
        rows = collect_datasets(database, model, "cpp")["concepts"]
        assert len(rows) == len(model.concepts)

    def test_a_concept_with_no_attempts_is_not_started(self, database, model) -> None:
        rows = {
            r["concept_id"]: r
            for r in collect_datasets(database, model, "cpp")["concepts"]
        }
        assert rows["pointers"]["label"] == "not_started"
        assert rows["pointers"]["attempts"] == 0

    def test_an_assessment_supplies_the_label(self, database, model) -> None:
        class Assessment:
            label = "developing"
            score = 0.42

        rows = {
            r["concept_id"]: r
            for r in collect_datasets(
                database, model, "cpp", {"pointers": Assessment()}
            )["concepts"]
        }
        assert rows["pointers"]["label"] == "developing"
        assert rows["pointers"]["score"] == 0.42

    def test_the_counts_are_the_measurement(self, database, model) -> None:
        _attempt(database, concept_id="pointers", correct=True)
        _attempt(database, concept_id="pointers", correct=False, hints_used=1)
        rows = {
            r["concept_id"]: r
            for r in collect_datasets(database, model, "cpp")["concepts"]
        }
        assert rows["pointers"]["attempts"] == 2
        assert rows["pointers"]["correct"] == 1
        assert rows["pointers"]["hints_used"] == 1


class TestWriting:
    def test_a_csv_has_a_header_and_the_rows(self, tmp_path) -> None:
        path = write_csv(tmp_path / "x.csv", ("a", "b"), [{"a": 1, "b": 2}])
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "a,b"
        assert lines[1] == "1,2"

    def test_a_missing_field_becomes_empty_not_a_crash(self, tmp_path) -> None:
        path = write_csv(tmp_path / "x.csv", ("a", "b"), [{"a": 1}])
        assert path.read_text(encoding="utf-8").splitlines()[1] == "1,"

    def test_the_readme_explains_the_files(self, tmp_path) -> None:
        path = write_readme(
            tmp_path / "README.txt", "cpp", {"attempts": 3, "concepts": 18}
        )
        text = path.read_text(encoding="utf-8")
        assert "attempts.csv" in text
        assert "3 row(s)" in text
        assert "cpp" in text
        assert "graded_by" in text, "the columns are not explained"

    def test_the_export_writes_every_file(self, database, model, tmp_path) -> None:
        _attempt(database)
        folder = tmp_path / "out"
        files = export_to_folder(database, model, folder, "cpp")
        names = {f.name for f in files}
        assert names == {
            "attempts.csv", "concepts.csv", "lessons.csv", "reviews.csv", "README.txt"
        }
        assert (folder / "attempts.csv").exists()

    def test_the_export_creates_the_folder(self, database, model, tmp_path) -> None:
        folder = tmp_path / "does" / "not" / "exist"
        export_to_folder(database, model, folder, "cpp")
        assert folder.is_dir()

    def test_the_exported_attempts_are_readable(self, database, model, tmp_path) -> None:
        _attempt(database, exercise_id="ex-9")
        folder = tmp_path / "out"
        export_to_folder(database, model, folder, "cpp")
        with (folder / "attempts.csv").open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 1
        assert rows[0]["exercise_id"] == "ex-9"
        assert list(rows[0].keys()) == list(ATTEMPT_COLUMNS)

    def test_the_concept_columns_are_stable(self, database, model, tmp_path) -> None:
        folder = tmp_path / "out"
        export_to_folder(database, model, folder, "cpp")
        with (folder / "concepts.csv").open(encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            assert reader.fieldnames == list(CONCEPT_COLUMNS)

    def test_nothing_is_written_outside_the_folder(
        self, database, model, tmp_path
    ) -> None:
        _attempt(database)
        folder = tmp_path / "out"
        export_to_folder(database, model, folder, "cpp")
        assert sorted(p.name for p in folder.iterdir()) == [
            "README.txt", "attempts.csv", "concepts.csv", "lessons.csv", "reviews.csv"
        ]

    def test_the_summary_counts_every_dataset(self, database, model) -> None:
        datasets = collect_datasets(database, model, "cpp")
        summary = export_summary(datasets)
        assert "attempts" in summary
        assert "concepts" in summary


class TestTheButton:
    @pytest.fixture(scope="module")
    def qapp(self):
        from PyQt6.QtWidgets import QApplication

        existing = QApplication.instance()
        app = existing or QApplication([])
        yield app

    @pytest.fixture()
    def view(self, qapp, database, model, tmp_path):
        from mentorsmith.ui.dashboard import ProgressView

        widget = ProgressView()
        widget.refresh(database, [], model=model, language="cpp", assessments={})
        yield widget
        widget.deleteLater()

    def test_the_button_exists(self, view) -> None:
        assert view.export_button.text().endswith("Export CSV")

    def test_it_explains_itself(self, view) -> None:
        assert "CSV" in view.export_button.toolTip()

    def test_the_export_context_is_held(self, view, database, model) -> None:
        assert view._database is database
        assert view._model is model
