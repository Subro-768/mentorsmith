#!/usr/bin/env python3
"""Set the answer key for the exam-prep question bank.

The papers do not print an answer key, so the bank cannot be graded without
one. This script writes one, and records **where each answer came from**,
because an answer written by an assistant is not an official key and must
not be presented as one.

    python3 tools/set_answers.py --show            # list unanswered questions
    python3 tools/set_answers.py --apply answers.json
    python3 tools/set_answers.py --report           # what is still unanswered

The answers file is a JSON object mapping question id to answer text::

    {"21css101j-pps--question-bank-with-mcqs--u1--q1": "Dennis Ritchie"}

For a multiple-choice question the answer must be one of the question's
options. Anything else is refused, because a key that does not match the
options cannot be marked.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mentorsmith.core.exam import (  # noqa: E402
    MCQ,
    load_questions,
    normalise_text,
    save_questions,
)

#: Where an answer came from, and what that means.
SOURCES = {
    "assistant": (
        "Answered from the C language definition and the supplied "
        "references. Not an official answer key."
    ),
    "book": (
        "Answered from the supplied C textbook. Not an official answer key."
    ),
    "official": "Taken from an official answer key.",
}


def show(questions, start: int, count: int, unanswered_only: bool) -> None:
    shown = 0
    for index, question in enumerate(questions):
        if unanswered_only and question.answer.strip():
            continue
        if index < start:
            continue
        if shown >= count:
            break
        shown += 1
        print(f"--- [{index}] {question.id}")
        print(f"    U{question.unit}  {question.source_file}  "
              f"Q{question.source_question_number}  p.{question.source_page}")
        print(f"    {question.question_text}")
        for i, option in enumerate(question.options):
            print(f"      ({chr(ord('a') + i)}) {option}")
        print()


def apply_answers(answers: dict, source: str) -> tuple[int, int]:
    """Write the answers in. Returns ``(applied, refused)``.

    A key may be a question id, or the **index** shown by ``--show``. The
    index form is much easier to type without a mistake, and a mistyped
    answer is the one thing that cannot be caught afterwards.
    """
    questions = load_questions()
    by_id = {q.id: q for q in questions}
    applied = 0
    refused = 0
    for key, answer in answers.items():
        if isinstance(key, int) or (isinstance(key, str) and key.isdigit()):
            index = int(key)
            if not 0 <= index < len(questions):
                print(f"  no question at index {index}", file=sys.stderr)
                refused += 1
                continue
            question = questions[index]
        else:
            question = by_id.get(key)
        if question is None:
            print(f"  unknown question: {key}", file=sys.stderr)
            refused += 1
            continue
        question_id = question.id
        if question is None:
            print(f"  unknown question: {question_id}", file=sys.stderr)
            refused += 1
            continue
        text = str(answer).strip()
        if text.startswith("="):
            # Stored literally. Used for a key the paper prints as a bare
            # option label, where the paper's own lettering is the answer.
            question.answer = text[1:].strip()
            question.answer_source = source
            applied += 1
            continue
        if question.question_type == MCQ and question.options:
            # A single letter is the option's label, which is far easier to
            # type than the option's text and cannot drift out of step with
            # it.
            label = text.strip().strip("()").lower()
            if len(label) == 1 and label in "abcdefghijklmnopqrstuvwxyz":
                position = ord(label) - ord("a")
                if position < len(question.options):
                    text = question.options[position]
            wanted = normalise_text(text)
            if not any(normalise_text(o) == wanted for o in question.options):
                print(
                    f"  refused: the answer for {question_id} is not one of "
                    f"its options",
                    file=sys.stderr,
                )
                refused += 1
                continue
        question.answer = text
        question.answer_source = source
        applied += 1
    save_questions(questions)
    return applied, refused


def report(questions) -> None:
    total = len(questions)
    answered = [q for q in questions if q.answer.strip()]
    print(f"  questions          : {total}")
    print(f"  with an answer     : {len(answered)}")
    print(f"  still unanswered   : {total - len(answered)}")
    graded = [q for q in answered if q.question_type == MCQ and q.answer_matches_an_option]
    if answered:
        print(f"  gradable as MCQs   : {len(graded)}")
    by_source: dict[str, int] = {}
    for question in answered:
        key = question.answer_source or "(none)"
        by_source[key] = by_source.get(key, 0) + 1
    for key, count in sorted(by_source.items()):
        print(f"    from {key}: {count}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--show", action="store_true", help="List questions.")
    parser.add_argument("--apply", metavar="FILE", help="Apply an answers file.")
    parser.add_argument("--report", action="store_true", help="What is missing.")
    parser.add_argument("--start", type=int, default=0, help="Where to start.")
    parser.add_argument("--count", type=int, default=30, help="How many to show.")
    parser.add_argument(
        "--only-unanswered", action="store_true",
        help="With --show, skip questions that already have an answer.",
    )
    parser.add_argument(
        "--source", default="assistant", choices=sorted(SOURCES),
        help="Where the answers came from.",
    )
    args = parser.parse_args()

    questions = load_questions()

    if args.apply:
        path = Path(args.apply)
        raw = json.loads(path.read_text(encoding="utf-8"))
        answers = raw.get("answers", raw)
        applied, refused = apply_answers(answers, args.source)
        print(f"  applied {applied} answer(s); {refused} refused.")
        for key, value in SOURCES.items():
            print(f"    {key}: {value}")
        return 0 if refused == 0 else 1

    if args.report:
        report(questions)
        return 0

    show(questions, args.start, args.count, args.only_unanswered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
