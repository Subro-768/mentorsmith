# MentorSmith — 120 feature proposals

**Status:** joint brainstorm. Contributors: Space Bunny Free (lead), with input
requested from the Gemini and Nemotron agents on the MentorSmith session.

**How to read this.** Every item is grounded in something that exists today — a
module in `mentorsmith/`, a gap found in the cross-check, or a limit stated in
this repo's own docs. Anything that could have been written without opening the
codebase has been cut. `docs/feature-*.md` items are already written up.

Priority key: **S** ships in a sitting · **M** a day · **L** a week or more.

---

## Built so far

Items from this list that now exist in the code, with the commit that built
them. The list stays a list of proposals; this is the record of which ones
actually shipped.

| # | Feature | What it is now |
|---|---|---|
| 1 | Doc-freshness test | `tests/test_docs_are_current.py` — checks every headline figure in README and PROJECT_STATE against the content, and the test count against what is collected. Fourteen of the figures it checks were a whole track out of date. |
| 2 | Token and cost metering | Tokens are read from the provider's own `usage` object and are exact. Cost is an estimate from a dated list-price table, labelled as one; a model that is not in the table gets no figure at all. Shown in the chat footer. |
| 3 | Cancel a tutor request | The provider's connection is closed, which unblocks a read in progress, and a flag discards any reply that still arrives. The **Stop** button appears while a request is in flight. |
| 4 | Bubblewrap on by default | The sandbox is on wherever `bwrap` is installed, because learner code is code the learner did not write. The user's own choice is remembered; where bubblewrap is absent the setting stays off, because promising containment that is not there is worse than not promising it. |
| 7 | "What you should review today" | A **Review today** card on the Mastery page, leading with one sentence saying how many concepts are worth revisiting, with a button that opens the lesson for the top one. |
| 11 | "You got this wrong N times" | Each review carries a badge with the number of wrong attempts. One concept failed four times is one thing to revisit, and it reads differently from one that is merely stale. |
| 21 | Multi-model comparison | **Not built.** Deferred: it needs per-provider cost accounting to be meaningful, which did not exist until item 2 above. |

---

## A. Corrections to the first draft of this list

A second pass checked each claim against the code by tracing call chains rather
than grepping one directory. Several entries in the first draft were wrong, and
the wrongness was worth recording.

| Claim in the first draft | Reality |
|---|---|
| "`core/revision.py` is a finished engine with **zero UI references** — built code with no door" | **Wrong.** `main_window.refresh_insights()` → `insights.build_report()` → `revision.recommend_reviews()`, and the dashboard renders a "Concepts to review" panel from `report.reviews`. I grepped `ui/` for the literal word "revision" and missed it by one layer of indirection. |
| "There is unreachable code" | **Wrong.** Every one of `git_tools, testgen, security_audit, review, retention, comparisons, debugging, revision, workspaces, projects, mastery, adaptive, concepts` is reachable from the UI, directly or through a service. There is no dead module. |
| "Coverage visualisation tied to the learner's own code" | Half right. `testgen.coverage_gaps()` exists and checks that a generated suite includes an `expected_failure` case. What is missing is *rendering* that, not the analysis. |
| "Keyboard-first navigation" | Half right. Shortcuts exist (`Ctrl+Return` to send, page navigation in `main_window`). A command palette does not. |
| "Detect when the model ignored the reply format" | **Wrong.** `parse_tutor_response` already sets `unparsed=True` and keeps the raw text. Already built. |
| "CSV export", "streaming responses", "learner data export", "cost metering" | Verified genuinely absent. The `csv` and `stream` greps were false positives — `json.dump` on settings is not a data export, and every "stream" hit was `std::cout`. |

**The real gaps, verified:**

| # | Feature | Why it matters | P |
|---|---|---|---|
| 1 | **A doc-freshness test** — parse the lesson files, assert the counts in README and PROJECT_STATE | Ten separate figures in the docs were a whole track out of date and nothing failed. This is the same class of silence as every other bug found this session. | S |
| 2 | **Token and cost metering per request** | The provider never reads `usage` from the response, so a request's size and cost are invisible. | S |
| 3 | **Cancel a tutor request mid-flight** | `ProcessHandle.stop()` exists for code execution, but `TutorWorker` has no abort path — a slow or hung request cannot be stopped. | M |
| 4 | **Turn bubblewrap on by default where available** | `bwrap` is installed on this machine and the setting defaults to `False`, so learner code runs unconfined unless the user finds the checkbox. | S |
| 5 | A dead-code / reachability check in CI | Would have caught the mistake I made in the first draft of this list. | M |

## B. Learning science — build on `core/mastery.py`, `adaptive.py`, `retention.py`

| # | Feature | P |
|---|---|---|
| 6 | Spaced repetition scheduler surfaced (follows #1) | S |
| 7 | "What you should review today" as a dashboard card | S |
| 8 | Per-concept decay curve over time | M |
| 9 | Distinguish *recall* from *transfer* in the UI — `retention.py` computes both, nothing shows it | M |
| 10 | Misconception library built from `mastery.py` reasons | M |
| 11 | "You got this wrong 4 times" badge per concept | S |
| 12 | Prerequisite graph visualisation (the data exists in `concepts.py`) | M |
| 13 | Warn when a lesson is unlocked without its prerequisites met | S |
| 14 | Confidence calibration — ask the learner to self-rate, compare to actual | M |
| 15 | Learning-curve export as CSV for the learner to keep | S |
| 16 | Due-date queue that respects the "don't nag" principle | M |
| 17 | Effort-vs-mastery scatter (fast + weak vs slow + strong) | L |
| 18 | Detect a stuck loop: same exercise failed 3× in a row | M |
| 19 | Auto-suggest the *next* concept when one is mastered | M |
| 20 | Test-retest with a shuffled question order to check for order effects | L |

---

## C. The AI tutor — build on `services/tutor.py`, now with the model picker

| # | Feature | P |
|---|---|---|
| 21 | **Multi-model response comparison** — send the same question to 2–3 models, show answers side by side | M |
| 22 | Per-turn model override is already in; add per-*lesson* default | S |
| 23 | Tutor explains its own reasoning ("here's how I'd debug this") | M |
| 24 | Socratic mode that refuses to answer until asked twice | M |
| 25 | Rubber-duck mode — the tutor asks questions and never suggests | M |
| 26 | Tutor can run your code and comment on the *output*, not just the code | M |
| 27 | Streaming token-by-token responses instead of one blocking call | M |
| 28 | Cancel a request mid-flight (the worker thread has no abort) | M |
| 29 | Token/latency/cost meter per request | S |
| 30 | Save good tutor answers into a personal "aha!" notebook | M |
| 31 | Let the learner rate each tutor reply 1–5 and feed it back into prompt choice | M |
| 32 | Context window budget — truncate old turns intelligently instead of failing | M |
| 33 | Tutor persona selector (Socratic / debugger / interviewer / examiner) | M |
| 34 | Offline canned answers so the tutor degrades gracefully with no network | M |
| 35 | Detect when the model ignored the requested reply format | S |

---

## D. Exercise engine — build on `core/exercises.py`, `debugging.py`, `comparisons.py`

| # | Feature | P |
|---|---|---|
| 36 | **Custom exercises** — the learner writes their own and it runs through the same pipeline | M |
| 37 | Import an exercise from a URL or pasted snippet | M |
| 38 | Test-case authoring UI (visual pass/fail per check) | M |
| 39 | Fuzzing — random inputs to find crashes the author missed | L |
| 40 | Property-based checks (e.g. "sort never loses elements") | L |
| 41 | Performance assertions (`O(n²)` vs `O(n log n)`) | L |
| 42 | Memory-leak detection for C/C++ | L |
| 43 | Diff view: learner code vs the reference solution | M |
| 44 | "Why is my answer wrong" button that shows the discriminating test | M |
| 45 | Side-by-side output comparison with whitespace made visible | S |
| 46 | Exercise difficulty auto-adjust based on attempt history | M |
| 47 | Partial credit — score each check separately, not pass/fail | M |
| 48 | Hint ladder that reveals exactly one more level each click | M |
| 49 | Exercise-of-the-day with a deterministic seed | S |

---

## E. Code execution — build on `execution/`

| # | Feature | P |
|---|---|---|
| 50 | Debugger integration (gdb/lldb) with breakpoints | L |
| 51 | Step-through visualisation of loops and branches | L |
| 52 | Show the generated bytecode/bytecode disassembly for Java | L |
| 53 | Compilation flags sandbox — let the learner add `-Wall` etc. | S |
| 54 | Per-language run presets (compile fast / debug / sanitise) | M |
| 55 | **Enable bubblewrap by default on capable machines** | S |
| 56 | ASan/UBSan build mode for C and C++ | M |
| 57 | Record and replay a run as a GIF for the progress page | L |
| 58 | Wall-clock and memory profile per run | M |
| 59 | Multi-file projects in the playground | M |
| 60 | stdin/stdout streaming so interactive programs show partial output | M |
| 61 | Network-call blocking inside the sandbox | L |
| 62 | Per-language "typical beginner errors" hint database | M |
| 63 | Assembly output panel for the C/C++ compiler | L |
| 64 | Unicode/locale edge-case test corpus | L |

---

## F. Theory book — build on `core/theory.py`

| # | Feature | P |
|---|---|---|
| 65 | Cross-language concept comparison ("pointers in C vs references in Java") | M |
| 66 | Full-text search with highlighted matches and ranking | M |
| 67 | "Explain this differently" — rephrase at a chosen reading level | M |
| 68 | Reading-level estimation per chapter | S |
| 69 | Track which theory chapters were read | S |
| 70 | Link a concept to the lesson that teaches it and vice versa (already modelled) | S |
| 71 | Diagrams rendered from a description language | L |
| 72 | Quizzes generated from theory text | M |
| 73 | Annotate a chapter with the learner's own notes | M |
| 74 | Export a chapter to PDF or Markdown | S |
| 75 | Offline-first theory cache | S |

---

## G. Projects — build on `core/projects.py`

| # | Feature | P |
|---|---|---|
| 76 | Multi-file projects with a real build step | L |
| 77 | Milestone-based progress with per-milestone tests | M |
| 78 | Git integration *inside* a project (commit at each milestone) | M |
| 79 | Project template generator from a description | M |
| 80 | Peer-review style rubric the learner self-assesses against | M |
| 81 | Portfolio export: generate a README from completed projects | M |
| 82 | Time-to-complete tracking per project | S |

---

## H. Developer tooling — build on `services/git_tools.py`, `testgen.py`, `security_audit.py`

| # | Feature | P |
|---|---|---|
| 83 | **Cross-model code review** — two models review the same snippet, report where they disagree *(from Nemotron)* | M |
| 84 | **Error-pattern classifier** — feed broken code, catalogue which failures recur *(from Nemotron)* | M |
| 85 | Expand `testgen.py` to every language, not just the default | M |
| 86 | Mutation testing — break the tests and see which catch it | L |
| 87 | Coverage visualisation tied to the learner's own code | M |
| 88 | Security audit as a scheduled weekly report | M |
| 89 | Explain a security finding with a concrete exploit on *their* code | L |
| 90 | Lint integration (clang-tidy, ruff, eslint) with fix suggestions | M |
| 91 | Format-on-save so style stops being a distraction | S |
| 92 | Keyboard-first navigation and a command palette | M |
| 93 | Workspaces: per-project settings and history | M |
| 94 | Snapshot/restore the whole app state | M |
| 95 | Export all learner data as JSON (portability) | S |

---

## I. Android companion

| # | Feature | P |
|---|---|---|
| 96 | Offline-first sync with conflict UI (the contract exists; the UI does not) | M |
| 97 | Read theory chapters on the phone | M |
| 98 | Flashcards for concepts — the single best use of a phone for this app | M |
| 99 | Daily review notification | S |
| 100 | Widget showing streak and today's review queue | M |
| 101 | Home-screen practice widget | M |
| 102 | Voice input for asking the tutor a question | L |
| 103 | Camera capture of handwritten work → ask the tutor about it | L |
| 104 | Wear OS companion: streak + one flashcard | L |
| 105 | Biometric lock for the app | S |
| 106 | Tablet layout using the larger screen properly | M |
| 107 | Dark/light follows the desktop theme automatically | S |
| 108 | Code-snippet sharing between desktop and phone | M |

---

## J. Curriculum and content

| # | Feature | P |
|---|---|---|
| 109 | Add Rust | L |
| 110 | Add Go | L |
| 111 | Add SQL | M |
| 112 | Add TypeScript | M |
| 113 | Add Shell/Bash | M |
| 114 | Capstone projects that use two languages together | L |
| 115 | Difficulty tiers per track (beginner / interview / competitive) | L |
| 116 | Prerequisite chains shared *across* languages | M |
| 117 | Content review checklist in `docs/adding-a-language.md` | S |
| 118 | Every lesson validated by running its own example code in CI | M |

---

## K. Platform and trust

| # | Feature | P |
|---|---|---|
| 119 | First-run wizard (language → goal → optional AI key) | M |
| 120 | Accessibility pass: keyboard-only, screen-reader labels, contrast | M |
| 121 | i18n — the strings are hardcoded in the UI modules | L |
| 122 | Crash reporting the learner opts into | L |
| 123 | Telemetry, strictly opt-in and off by default | L |
| 124 | Signed release build + reproducible APK | M |
| 125 | Flathub / AUR packaging | M |

---

## Where I think the leverage is

If only three get built, they should be **#1** (a finished revision engine
with no door), **#3** (the doc-freshness test — it would have caught every
count that went stale), and **#83** (cross-model review, and the one idea the
other agents contributed that turns this from a single-model tool into
something better than either model alone).

## Open questions for the other agents

1. Which of these do you think are wrong about a learning app and worth
   removing rather than building?
2. Is there a feature here that is technically impossible on the hardware
   budget (8 GB VRAM, 16 GB RAM)?
3. What would you cut first if only twenty could ship?