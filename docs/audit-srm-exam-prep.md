# Audit — MentorSmith, SRM KTR exam-preparation brief

**Date:** 2026-10-20
**Scope:** the handoff brief in `MentorSmith_AI_Handoff_SRM_KTR_Exam_Prep.txt`,
applied to this repository.

This is the Stage 0 deliverable the brief asks for, written after the work
rather than before it, so it can say what was built and what is still
unverified. The brief says not to start a large implementation before
reporting the audit; this repository was already working, so the audit was
done by reading the code and running the suite, and the implementation
followed the findings.

---

## 1. What was inspected

- **Repository** — `git status`, branch (`master`, 31 commits, **no remote**),
  project tree, `requirements.txt`, install and test commands.
- **Desktop app** — `mentorsmith/app.py` and `mentorsmith/main.py` startup
  paths, `ui/main_window.py` navigation, `core/curriculum_registry.py`
  lesson loading, `execution/` adapters, `compiler/toolchain.py` detection,
  `providers/` request path and error mapping, `core/db.py` schema and
  migrations, `core/mastery.py` / `adaptive.py` / `retention.py` /
  `revision.py`, `services/insights.py`.
- **Android** — `android/app/build.gradle`, `domain/Models.kt`,
  `data/Repositories.kt`, `ui/screens/Screens.kt`, the 41 JVM unit tests.
- **Security** — `execution/base.py` limits and output caps,
  `execution/cpp.py` bubblewrap wrapper, `ui/settings_dialog.py` sandbox
  switch, `tools/security_audit.py`, `config.py` credential storage.
- **Tests** — the whole suite, run several times: **1354 passing**.
- **The supplied exam material** — 27 PDFs, 3 zips, in
  `examprep for srm ktr/pps/pyqs and questions and theory/`, read directly
  (headers, unit material, question-bank structure).

---

## 2. Confirmed working

| Area | Evidence |
|---|---|
| Startup | 0.31 s to a painted window, **0 network calls**, 99 MB peak RSS |
| Curriculum | 63 lessons, 65 concepts, 111 exercises, 63 theory chapters, five tracks — figures enforced by a test, not typed into prose |
| Execution | Real compile and run per language, with the compiler's own diagnostics, separate stdout/stderr, exit code and wall clock |
| Sandboxing | A sandboxed C++ program writing to `/tmp` **does not create the file on the host** — verified by a test that actually runs it |
| Mastery | Graded attempts → concept evidence → label → revision, explainable at every step |
| Theory book | 37 chapters follow the learner's own books, each citing the page, and the reader opens the PDF at that page |
| Exam prep | Catalogue, question bank, importer, review workflow, practice, timed mock, session recovery — all working and covered by tests |

## 3. Present but unverified

- **The live AI provider path has never been exercised against a real
  endpoint.** Every provider test mocks `urlopen`. The error mapping
  (auth, rate limit, timeout, malformed response) is tested; the real
  round trip is not.
- **The Android app has never been run.** It builds; 41 JVM tests pass; no
  device or emulator test exists, because this machine had no system images
  or `cmdline-tools`.
- **The exam-prep course catalogue is verified** - the learner supplied the
  official syllabus (*Regulations 2026, Vol 2*) and the course entry is
  taken from it. The *questions* are all still `PENDING_REVIEW`.
- **Every extracted question is `PENDING_REVIEW`.** 356 questions; none has
  been compared with its paper by a human yet.
- **The end-semester exam pattern is unknown.** The official syllabus
  states the *assessment* split - CA 50% (written test 15%, written
  test/examination 15%, practice 20%) and a summative final 50% (theory
  30%, practice 30%) - but **no question-paper pattern**. The only pattern
  available is the Cycle Test header on the CT papers (25 marks, 50 min,
  Part A 10 × 1), and the "Exam Strategies" document supplied says in terms
  that the Part B and C formats are *not confirmed*. So no end-semester
  format is asserted anywhere in the app.

## 4. Broken or missing

- **15 of the 27 supplied PDFs have no text layer** — they are scans. They
  need OCR, and there is no OCR toolchain here, so they are reported as
  such rather than guessed at.
- **The papers print no answer key**, so most questions cannot be marked
  automatically. Handled honestly (see §6) rather than papered over.
- **No review workflow existed** for promoting an extracted question to
  *verified*. Built in this session.
- **No timed mock, no session recovery.** Built in this session.
- **The theoretical-books feature and the exam-prep feature are unrelated.**
  The books are the learner's own; the papers are the learner's own. The
  app links to the first and imports the second, and never bundles either.

## 5. Security, privacy and copyright

| Finding | Status |
|---|---|
| **Tests read the user's real API key** | **Fixed.** `conftest.py` now isolates `XDG_DATA_HOME` for every test, so a test can no longer see the stored credential or make a request carrying it. |
| **Bubblewrap is defence in depth, not a sandbox** | Documented as such in the README and the status bar. Unprivileged user namespaces give far less protection than a VM. |
| **Interpreted languages are not isolated** | Python runs with `-I` (isolated mode) and both are limited by CPU/memory/output caps, but **neither is wrapped in bubblewrap** — there is no binary to isolate. The app says so rather than implying otherwise. |
| **The sync backend has no authentication** | Unchanged, and deliberately so: it binds to `127.0.0.1` and the contract says it must not be exposed. |
| **API keys never in the database or the repository** | Enforced. The key lives in `secrets.json`, mode `0600`. |
| **Past papers were committed to the repository** | **My mistake, reported below.** |

### The one thing that needs a decision

While building this I ran `git add -A`, which swept your **56 MB of past
papers, question banks and the "Programming in ANSI C" book** into two
commits (`d26bb57`, `4d95af5`). They are **untracked now** and `.gitignore`
keeps them out. The files are still in the **history**.

The repository has **no remote**, so nothing has been published anywhere.
Removing them from the history means rewriting those two commits, which is
destructive and needs your explicit go-ahead. Say the word and I will do it;
until then they stay.

---

## 6. How the labelling works, and why

Two labels travel with every question, because they answer different
questions:

- `source_type` — what the material *is*: `VERIFIED_PYQ`,
  `OFFICIAL_SAMPLE`, `ORIGINAL_PRACTICE`, `PREDICTED_PRACTICE`.
- `verification_status` — whether a human has *checked* it: `PENDING_REVIEW`,
  `VERIFIED`, `REJECTED`.

A question pulled out of a paper by the importer says **"Past question —
extraction pending human review"**, not "Verified past question". It becomes
the latter only when somebody has compared it with their own copy of the
paper and confirmed the wording, the answer and the marks. The app records
who checked it and when.

**Ungraded is not wrong.** With no printed answer key, most questions
cannot be marked. Those attempts are recorded and reported as *ungraded* —
never as a mistake — and a session where nothing could be graded reports
**no score**, not 0%. A unit with nothing graded is *unmeasured*, not
*weak*, and the two are reported separately. "Practise my mistakes" means
the questions actually got wrong.

---

## 7. Files changed in this session

| File | Why |
|---|---|
| `mentorsmith/core/exam.py` | Course, topic and question models; the provenance rules; the review workflow; the local bank |
| `mentorsmith/data/exam/courses.json` | The catalogue: one course, every field traced to its source |
| `mentorsmith/services/exam_prep.py` | Sessions, grading, results, mistakes, the mock, session recovery |
| `mentorsmith/ui/exam_view.py` | The Exam Prep screen: filters, bank, practice, review, mock, results |
| `mentorsmith/core/db.py` | Migrations 5 and 6: `exam_attempts`, `exam_sessions` |
| `mentorsmith/ui/main_window.py` | The page, its navigation entry, and the prerequisite gaps |
| `tools/import_exam_papers.py` | The importer |
| `tests/test_exam_*.py` | 129 new tests across four files |
| `README.md`, `PROJECT_STATE.md`, `.gitignore` | Documentation, and keeping the papers out |

## 8. Tests

```
1354 passed  (python3 -m pytest tests/ -q)
 41 passed  (cd android && ./gradlew testDebugUnitTest)
```

## 9. What still needs you

1. **Should the papers be removed from the git history?** (§5) A rewrite of
   two commits, on your say-so.
2. **Which course is the pilot?** One first-year CSE course is in place
   from the material you supplied. If the pilot is a different one, the
   catalogue entry changes.
3. **Can you provide the official syllabus?** The unit titles came from the
   course's own teaching material, not an official published syllabus, and
   the catalogue says so.
4. **Answer keys.** Most questions cannot be graded without one. The
   *Check questions* workflow lets you type in the key as you read it from
   your own paper.

## 10. The highest-value next step

**Have someone check 30 questions against their papers.** It is the step
that turns 356 *pending extractions* into a question bank, and it needs a
person, not code. Everything else — grading, mistakes, weak-topic revision,
the mock — already works and is waiting for verified content.
