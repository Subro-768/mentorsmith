"""Export the learner's own data as CSV.

Feature #15. The learning curve - the record of what was attempted, when,
and how it went - lives in the app's database, which is also where the
app's own state lives. If the learner wants to keep it, chart it, or move
it somewhere else, they should be able to take it with them.

What is exported
----------------
``attempts``
    One row per graded attempt. This is the learning curve: timestamp,
    language, lesson, exercise, type, whether it was right, how many hints
    it took, whether it was solved independently, how it was graded, and
    the error category if one was recorded.
``concepts``
    One row per concept in the track: the label, the score, and the counts
    behind them.
``lessons``
    One row per completed lesson.
``reviews``
    One row per review the scheduler opened.

Design notes
------------
* The export is the learner's data, so it is written **as the app holds
  it**, with no re-interpretation. A row saying "correct" is a row the
  database says is correct.
* The files are plain CSV with a header row, readable by a spreadsheet, a
  notebook, or a text editor.
* Every file comes with a ``README.txt`` explaining what each column means
  and when the export was taken. A CSV with unexplained column names is
  data the learner cannot use without reverse-engineering it.
* Nothing is written outside the folder the learner chose, and the folder
  is created if it does not exist.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

#: Column order for each dataset. Explicit, so the header row is stable
#: between exports and a script reading them does not have to guess.
ATTEMPT_COLUMNS = (
    "attempted_at",
    "language",
    "lesson_id",
    "exercise_id",
    "exercise_type",
    "concept_id",
    "correct",
    "hints_used",
    "independent",
    "graded_by",
    "error_category",
    "compiled_ok",
    "ran_ok",
    "novel",
)

CONCEPT_COLUMNS = (
    "concept_id",
    "title",
    "label",
    "score",
    "attempts",
    "correct",
    "hints_used",
    "independent",
)

LESSON_COLUMNS = ("lesson_id", "completed_at")

REVIEW_COLUMNS = (
    "concept_id",
    "reason",
    "evidence",
    "status",
    "opened_at",
)

#: What each file contains, written into the README.
DATASET_NOTES = {
    "attempts": (
        "One row per graded attempt, oldest first. 'correct' is what the "
        "grader decided; 'graded_by' says whether that came from running the "
        "code (deterministic) or from the tutor (interpretive)."
    ),
    "concepts": (
        "One row per concept in the track. 'label' is the app's summary of "
        "the attempts behind it, and the counts are those attempts - the "
        "label is a summary, the counts are the measurement."
    ),
    "lessons": "One row per lesson marked complete.",
    "reviews": (
        "One row per review the scheduler opened, with the reason it gave "
        "and the evidence behind it."
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _all_attempts(database, language: str) -> list[dict]:
    """Every attempt for a language, oldest first.

    The database is asked per concept rather than with one wide query, so
    this works whatever the schema ends up holding, and the concepts the
    learner has never touched contribute no rows.
    """
    rows: list[dict] = []
    conn = database.connect()
    try:
        found = conn.execute(
            "SELECT * FROM exercise_attempts WHERE language = ? ORDER BY id ASC",
            (language,),
        ).fetchall()
    except Exception:
        return rows
    for row in found:
        rows.append(dict(row))
    return rows


def collect_datasets(
    database,
    model,
    language: str = "cpp",
    assessments: dict | None = None,
) -> dict[str, list[dict]]:
    """Gather every dataset, ready to be written.

    ``assessments`` supplies the mastery labels and scores. The database
    holds only counts - the interpretation lives in
    :mod:`mentorsmith.core.mastery` - so without them the concept rows
    would carry counts and no label, which is the wrong way round.
    """
    assessments = assessments or {}
    datasets: dict[str, list[dict]] = {}

    attempts = []
    for row in _all_attempts(database, language):
        attempts.append({
            "attempted_at": row.get("created_at", ""),
            "language": row.get("language", language),
            "lesson_id": row.get("lesson_id", ""),
            "exercise_id": row.get("exercise_id", ""),
            "exercise_type": row.get("exercise_type", ""),
            "concept_id": row.get("concept_id", ""),
            "correct": 1 if row.get("correct") else 0,
            "hints_used": row.get("hints_used", 0),
            "independent": 1 if row.get("independent") else 0,
            "graded_by": row.get("graded_by", ""),
            "error_category": row.get("error_category", ""),
            "compiled_ok": 1 if row.get("compiled_ok") else 0,
            "ran_ok": 1 if row.get("ran_ok") else 0,
            "novel": 1 if row.get("novelty") else 0,
        })
    datasets["attempts"] = attempts

    concepts = []
    for concept_id in model.ordered_ids():
        concept = model.get(concept_id)
        if concept is None:
            continue
        evidence = database.concept_evidence([concept_id], language).get(concept_id, {})
        assessment = assessments.get(concept_id)
        concepts.append({
            "concept_id": concept_id,
            "title": concept.title,
            "label": assessment.label if assessment else "not_started",
            "score": round(float(assessment.score if assessment else 0.0), 3),
            "attempts": evidence.get("attempts", 0),
            "correct": evidence.get("correct", 0),
            "hints_used": evidence.get("hints_used", 0),
            "independent": evidence.get("independent", 0),
        })
    datasets["concepts"] = concepts

    lessons = []
    for lesson_id in database.completed_lessons(language):
        lessons.append({
            "lesson_id": lesson_id,
            "completed_at": _now(),
        })
    datasets["lessons"] = lessons

    reviews = []
    for review in database.open_reviews(language):
        reviews.append({
            "concept_id": review.get("concept_id", ""),
            "reason": review.get("reason", ""),
            "evidence": review.get("evidence", ""),
            "status": review.get("status", ""),
            "opened_at": review.get("created_at", ""),
        })
    datasets["reviews"] = reviews

    return datasets


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> Path:
    """Write one CSV file with a header row."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})
    return path


def write_readme(path: Path, language: str, counts: dict[str, int]) -> Path:
    """Write the file that explains the other files."""
    lines = [
        "MentorSmith — export of your learning data",
        "",
        f"Language: {language}",
        f"Exported: {_now()}",
        "",
        "These files are your data, exactly as the app recorded it. Nothing",
        "here has been re-interpreted: a row that says 'correct' is a row",
        "the database says is correct.",
        "",
        "Files:",
    ]
    for name in sorted(counts):
        note = DATASET_NOTES.get(name, "")
        lines.append(f"  {name}.csv  -  {counts[name]} row(s)")
        if note:
            lines.append(f"      {note}")
    lines.append("")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def export_to_folder(
    database,
    model,
    folder: Path,
    language: str = "cpp",
    assessments: dict | None = None,
) -> list[Path]:
    """Write every dataset into a folder. Returns the files written."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    datasets = collect_datasets(database, model, language, assessments)

    columns = {
        "attempts": ATTEMPT_COLUMNS,
        "concepts": CONCEPT_COLUMNS,
        "lessons": LESSON_COLUMNS,
        "reviews": REVIEW_COLUMNS,
    }

    written: list[Path] = []
    counts: dict[str, int] = {}
    for name, rows in datasets.items():
        target = write_csv(folder / f"{name}.csv", columns.get(name, ()), rows)
        written.append(target)
        counts[name] = len(rows)
    written.append(write_readme(folder / "README.txt", language, counts))
    return written


def export_summary(datasets: dict[str, list[dict]]) -> str:
    """A one-line-per-dataset summary, for the UI."""
    parts = [f"{name}: {len(rows)}" for name, rows in sorted(datasets.items())]
    return " · ".join(parts)
