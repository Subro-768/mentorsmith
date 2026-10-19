#!/usr/bin/env python3
"""Import exam papers into the local question bank.

What this does
--------------
Walks a folder of papers, extracts candidate questions from each, and
writes them into the app's **local** question bank. The text is copied
verbatim; nothing is tidied up, reworded or "corrected", because a student
comparing the app with the paper must find the same question.

What this deliberately does not do
----------------------------------
* It does not verify anything. Every imported question is written with
  ``verification_status = PENDING_REVIEW``, and the UI says so. A question
  becomes a *verified* past question only when a human has read it against
  the paper and confirmed the wording, the answer and the marks.
* It does not invent an answer key. If the paper does not print one, the
  question has no answer and is listed in the review report as needing
  one. An answer guessed from a pattern is worse than no answer.
* It does not put the questions in the repository. Past papers are the
  learner's own material; the bank lives in the app's data directory.

Usage
-----
    python3 tools/import_exam_papers.py --folder "examprep for srm ktr/pps/pyqs and questions and theory"
    python3 tools/import_exam_papers.py --folder ... --dry-run
    python3 tools/import_exam_papers.py --report
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mentorsmith.core.exam import (  # noqa: E402
    MCQ,
    OFFICIAL_SAMPLE,
    PENDING_REVIEW,
    VERIFIED_PYQ,
    ExamQuestion,
    load_questions,
    merge_questions,
    review_report,
)

#: Running headers and footers that appear on every page of a paper and are
#: not part of any question.
BOILERPLATE = (
    "srm institute of science and technology",
    "faculty of engineering and technology",
    "school of computing",
    "department of computer science",
    "college of engineering and technology",
    "course code and title",
    "program offered",
    "max.marks",
    "year/sem",
    "duration",
    "course learning",
    "clo-",
    "part-a:",
    "part a (",
    "answer all",
    "reg. no",
)

#: A question number at the start of a line: "1", "1.", "12)", "(3)".
QUESTION_START = re.compile(r"^\s{0,8}(\d{1,3})\s*[\.\)]\s+(.*)$")
#: The same, in the papers that put the number in its own column with no
#: punctuation after it - "  1     Every C program consists of ...". A gap of
#: two or more spaces is what marks it as a column, not a sentence.
QUESTION_START_COLUMN = re.compile(r"^\s{0,8}(\d{1,3})\s{2,}(\S.*)$")
#: An option line: "(a) text", "a) text", "A. text", "(iv) text".
#:
#: The indent allowance is generous because the papers set their option
#: column deep - a question with a code block pushes its options further
#: right - and a too-tight pattern silently loses the options, which loses
#: the question.
OPTION_LINE = re.compile(r"^\s{0,18}\(?([a-dA-DivxIV]{1,4})[\.\)]\s+(\S.*)$")
#: An option label *inside* a line. The question banks set their options in
#: two columns, so one line can hold "A. Bjarne Stroustrup   B. Dennis
#: Ritchie" and both have to be recovered.
OPTION_INSIDE = re.compile(r"(?:^|\s{2,})\(?([a-dA-D])\s*[\.\)]\s+")
#: The CO / PLO tags the banks print beside a question.
COVERAGE_TAG = re.compile(r"\[(CLO|PLO|BL)[^\]]*\]", re.IGNORECASE)
#: A unit heading.
UNIT_HEADING = re.compile(r"^\s*(unit)\s*[-–\s]*([0-9ivx]{1,3})\b", re.IGNORECASE)

#: Characters that show up when a scan has been through bad OCR. Used to
#: flag a page whose text cannot be trusted.
OCR_NOISE = re.compile(r"[^ -~\n\t]")

#: A word of four or more letters.
LONG_WORD = re.compile(r"[A-Za-z]{4,}")


def looks_like_a_question(text: str) -> bool:
    """Whether a piece of text reads like a question rather than like noise.

    Bad OCR produces text that is all ASCII but is not words: "24. 23.
    22.21.", "1h 2i 3j 4k", "CxprcNsion oevaluates". Character-level noise
    detection cannot see that, because every character is printable.

    What separates them is that real questions contain ordinary words, and
    ordinary words are mostly lower case. So the test is: at least two
    words of four letters or more, and those words mostly lower case.
    """
    words = LONG_WORD.findall(text)
    if len(words) < 2:
        return False
    for word in words:
        # An acronym is fine. A capital in the *middle* of a mixed-case
        # word is the signature of a bad scan: "CxprcNsion" for
        # "Expression".
        if word.isupper():
            continue
        if any(ch.isupper() for ch in word[2:]):
            return False
    letters = "".join(words)
    if not letters:
        return False
    return sum(1 for ch in letters if ch.islower()) / len(letters) > 0.6


def _pdftotext_pages(pdf: Path) -> list[str]:
    """Text of each page, laid out so columns keep their alignment.

    ``pdftotext`` is preferred because it handles the digital-text papers
    well. ``pypdf`` is the fallback. Whichever is used, the text is the
    document's own - nothing is rewritten.
    """
    if shutil.which("pdftotext"):
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(pdf), "-"],
                capture_output=True, text=True, timeout=300, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.split("\f")
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    try:
        reader = PdfReader(str(pdf))
    except Exception:
        return []
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def _ocr_noise_ratio(text: str) -> float:
    """How much of a page is untrustworthy characters."""
    stripped = OCR_NOISE.sub("", text)
    total = len(text)
    if total == 0:
        return 1.0
    return 1.0 - (len(stripped) / total)


def _is_boilerplate(line: str) -> bool:
    lowered = line.strip().lower()
    if not lowered:
        return True
    return any(marker in lowered for marker in BOILERPLATE)


def _paper_kind(path: Path, first_page: str) -> tuple[str, str]:
    """What kind of document this is, and the title to record.

    Returns ``(source_type, title)``. A paper with the SRM header is a
    past question; a document that is a question bank is an official
    sample; anything else is skipped.
    """
    name = path.name
    lowered = first_page.lower()
    if "course code and title" in lowered or "cycle test" in lowered:
        return VERIFIED_PYQ, name
    if "question bank" in name.lower() or "important questions" in name.lower():
        return OFFICIAL_SAMPLE, name
    if "pyq" in name.lower() or "ct " in name.lower() or "ct1" in name.lower():
        return VERIFIED_PYQ, name
    return OFFICIAL_SAMPLE, name


def _question_id(
    course_id: str,
    path: Path,
    number: str,
    unit: int,
    occurrence: int,
) -> str:
    """A stable id, so re-importing the same paper does not duplicate.

    The number alone is not enough: a paper that restarts its numbering
    per unit has several "question 3"s, and a bank that gave them all the
    same id would silently drop all but the first. The unit and the
    occurrence of that number within the unit keep them apart.
    """
    stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    base = f"{course_id}--{stem}--u{unit}--q{number}"
    return base if occurrence == 0 else f"{base}--{occurrence}"


#: The right-hand column of the SRM papers is a CO / Bloom-level coverage
#: table, and ``pdftotext -layout`` folds its numbers into the question
#: text. The text is never edited - the brief asks for the original to be
#: left alone - but the noise is tagged so a reviewer can find it.
LAYOUT_NOISE = re.compile(
    r"(?:\b\d+(?:\.\d+)?\b[ \t]+){3,}$"
)


def _options_on_line(line: str) -> list[str]:
    """The options on one line, however many columns it uses.

    A line that starts with an option label is an option line; the text
    between one label and the next is that option's text.
    """
    first = OPTION_LINE.match(line)
    if not first:
        return []
    matches = list(OPTION_INSIDE.finditer(line))
    if not matches:
        return [first.group(2).strip()]
    texts: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(line)
        text = line[start:end].strip()
        if text:
            texts.append(text)
    return texts


def _parse_document(
    pages: list[str],
    *,
    unit: int = 0,
) -> tuple[list[dict], int]:
    """Pull questions out of a whole document, page by page.

    State carries across page boundaries, because a question whose text is
    at the foot of one page and whose options are at the top of the next is
    one question, and losing it loses a real item from the paper.

    The rule is deliberately conservative: a question is only a question if
    it is numbered and has at least two options. A half-read line is
    dropped rather than guessed at.
    """
    questions: list[dict] = []
    current: dict | None = None
    expecting_options = False

    for page in pages:
        for raw in page.splitlines():
            line = raw.rstrip()
            if not line.strip():
                continue
            if _is_boilerplate(line):
                continue

            unit_match = UNIT_HEADING.match(line.strip())
            if unit_match and not OPTION_LINE.match(line.strip()):
                number = unit_match.group(2)
                if number.isdigit():
                    unit = int(number)
                current = None
                expecting_options = False
                continue

            question_match = QUESTION_START.match(line)
            column_match = None
            if not question_match:
                column_match = QUESTION_START_COLUMN.match(line)
            if (question_match or column_match) and not OPTION_LINE.match(line.strip()):
                if question_match:
                    number, text = question_match.group(1), question_match.group(2).strip()
                else:
                    number, text = column_match.group(1), column_match.group(2).strip()
                # A bare number with no text is a header row, not a question.
                if len(text) < 4:
                    current = None
                    expecting_options = False
                    continue
                current = {
                    "number": number,
                    "text": text,
                    "options": [],
                    "unit": unit,
                }
                questions.append(current)
                expecting_options = True
                continue

            options = _options_on_line(line)
            if options and current is not None and expecting_options:
                current["options"].extend(options)
                continue

            if current is not None:
                # Continuation of the question text or of the last option.
                if current["options"]:
                    current["options"][-1] += " " + line.strip()
                else:
                    current["text"] += " " + line.strip()
            else:
                expecting_options = False

    kept = [q for q in questions if len(q["options"]) >= 2]
    return kept, unit


def _parse_page(
    lines: list[str],
    *,
    unit: int,
) -> list[dict]:
    """Pull questions out of one page's lines.

    Kept as a thin wrapper for the single-page case; the document-level
    parser is the one that matters.
    """
    questions, _unit = _parse_document(["\n".join(lines)], unit=unit)
    return questions


def _question_start_pages(pages: list[str]) -> dict[str, int]:
    """Map a question number to the page it starts on.

    Numbers restart per paper and per section, so this is per document and
    per page - it is a pointer to help a reviewer, not a unique key.
    """
    starts: dict[str, int] = {}
    for number, page in enumerate(pages, start=1):
        for line in page.splitlines():
            match = QUESTION_START.match(line) or QUESTION_START_COLUMN.match(line)
            if not match:
                continue
            if OPTION_LINE.match(line.strip()):
                continue
            starts.setdefault(match.group(1), number)
    return starts


def import_paper(path: Path, course_id: str) -> tuple[list[ExamQuestion], dict]:
    """Extract candidate questions from one PDF."""
    pages = _pdftotext_pages(path)
    if not pages:
        return [], {
            "file": path.name,
            "error": (
                "no text layer - this is a scanned image, so it needs OCR "
                "before any question can be extracted"
            ),
        }

    source_type, title = _paper_kind(path, pages[0])
    questions: list[ExamQuestion] = []
    noisy_pages = 0
    total_pages = 0

    for page in pages:
        if not page.strip():
            continue
        total_pages += 1
        if _ocr_noise_ratio(page) > 0.06:
            noisy_pages += 1

    found, _unit = _parse_document(pages)

    # A question with no words in it is a failed extraction, not a
    # question. Scanned papers that have been through bad OCR produce
    # lines like "24. 23. 22.21." which would otherwise be imported as
    # real questions.
    kept = []
    for item in found:
        if not looks_like_a_question(item["text"]):
            continue
        kept.append(item)
    found = kept

    # The page a question starts on, so the source pointer is exact.
    starts = _question_start_pages(pages)

    occurrences: dict[tuple[int, str], int] = {}
    for item in found:
        options = item["options"]
        tags = [f"unit{item['unit']}"] if item["unit"] else []
        for coverage in COVERAGE_TAG.findall(item["text"]):
            tags.append(coverage.lower())
        if LAYOUT_NOISE.search(item["text"]) or any(
            LAYOUT_NOISE.search(o) for o in options
        ):
            # The paper's coverage table bled into the text. The original is
            # left exactly as extracted; this tag marks it for the reviewer.
            tags.append("layout-noise")
        key = (item["unit"], item["number"])
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        question = ExamQuestion(
            id=_question_id(course_id, path, item["number"], item["unit"], occurrence),
            course_id=course_id,
            question_text=item["text"],
            question_type=MCQ,
            unit=item["unit"],
            options=options,
            answer="",           # no key unless the paper prints one
            explanation="",
            source_type=source_type,
            source_title=title,
            source_file=path.name,
            source_page=starts.get(item["number"], 1),
            source_question_number=item["number"],
            verification_status=PENDING_REVIEW,
            redistribution_status="not_for_redistribution",
            tags=tags,
        )
        questions.append(question)

    stats = {
        "file": path.name,
        "questions": len(questions),
        "pages": total_pages,
        "noisy_pages": noisy_pages,
        "source_type": source_type,
    }
    if total_pages == 0:
        # A scan with no text layer at all. Saying "0 questions" would be
        # true and useless; the useful fact is that the file needs OCR
        # before anything can be extracted from it.
        stats["error"] = (
            "no text layer - this is a scanned image, so it needs OCR "
            "before any question can be extracted"
        )
    elif not questions and noisy_pages:
        stats["error"] = (
            f"text looks OCR-damaged on {noisy_pages} page(s) - nothing was "
            f"extracted that could be trusted"
        )
    return questions, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--folder", help="Folder of papers to import.")
    parser.add_argument(
        "--course", default="21css101j-pps", help="Course id to file them under."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be imported without writing anything.",
    )
    parser.add_argument(
        "--report", action="store_true",
        help="Report what in the bank still needs a human.",
    )
    args = parser.parse_args()

    if args.report:
        report = review_report()
        print("Question bank review report")
        print(f"  total questions       : {report['total']}")
        print(f"  pending human review  : {len(report['pending_review'])}")
        print(f"  missing source detail : {len(report['missing_source'])}")
        print(f"  no answer key         : {len(report['no_answer'])}")
        print(f"  ungradable (the answer is not one of the extracted options): "
              f"{len(report.get('ungradable', []))}")
        print(f"  duplicate groups      : {len(report['duplicate_groups'])}")
        for question in report["pending_review"][:10]:
            print(f"    - {question.id}: {question.question_text[:70]}")
        return 0

    if not args.folder:
        parser.error("--folder is required unless --report is given")

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        print(f"error: not a folder: {folder}", file=sys.stderr)
        return 1

    pdfs = sorted(folder.rglob("*.pdf"))
    if not pdfs:
        print(f"error: no PDFs under {folder}", file=sys.stderr)
        return 1

    all_questions: list[ExamQuestion] = []
    print(f"Reading {len(pdfs)} file(s) from {folder}\n")
    for pdf in pdfs:
        questions, stats = import_paper(pdf, args.course)
        if stats.get("error"):
            print(f"  {stats['file']}: {stats['error']}")
            continue
        note = ""
        if stats["noisy_pages"]:
            note = (
                f"  ({stats['noisy_pages']}/{stats['pages']} pages look "
                f"OCR-damaged - check those extractions)"
            )
        print(
            f"  {stats['file']}: {stats['questions']} candidate question(s) "
            f"[{stats['source_type']}]{note}"
        )
        all_questions.extend(questions)

    if args.dry_run:
        print(f"\nDry run: {len(all_questions)} question(s) would be imported.")
        print("Nothing was written.")
        return 0

    result = merge_questions(all_questions)
    print(
        f"\nImported {result['added']} question(s); "
        f"{result['already_present']} already present; "
        f"{result['duplicates']} skipped as duplicates of a question already "
        f"in the bank."
    )
    print("Every one of them is PENDING_REVIEW - none of them is a")
    print("'verified past question' until a human has checked it against")
    print("the paper. Run with --report to see what is outstanding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
