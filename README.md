# MentorSmith

A Linux-first desktop tutor for learning programming fundamentals, built with
Python and PyQt6.

MentorSmith compiles and runs **your own code** and shows you the real compiler
and runtime output, then pairs each lesson with an AI tutor that supports three
levels of help. On top of that it tracks *evidence* of understanding rather than
what you clicked, and adapts what it gives you next.

**Five tracks: C++, Python, Java, C and JavaScript.** 63 lessons, 65 concepts,
111 exercises, 63 theory chapters. Plus an Android companion and developer tooling.

---

## Status

This is a working application, not a product. It launches, runs real compilers,
and its behaviour is covered by 1151 automated tests. It has **not** been
through a security review, run at scale, or tested on anything but one Fedora
workstation and one 16 GB laptop. There is no release build, no packaging and
no store listing.

The largest untested surface is the **live AI provider path**: everything up to
the HTTP boundary is mocked, and no request has ever been sent to a real vendor.
The Android app has **never been run on a device or emulator** — it builds and
its logic is unit-tested, but nobody has watched it start.

---

## Installing it as a Linux application

```bash
python3 tools/install_desktop.py          # per-user install, no sudo needed
mentorsmith                              # or launch "MentorSmith" from your menu
```

That writes three things under `~/.local`, and nothing else anywhere:

| Path | What |
|---|---|
| `~/.local/bin/mentorsmith` | launcher, pointing at this checkout |
| `~/.local/share/applications/mentorsmith.desktop` | menu entry |
| `~/.local/share/icons/mentorsmith/<n>x<n>/mentorsmith.png` | 8 icon sizes |

The icons go into a directory of their own rather than the shared `hicolor`
tree, and the desktop entry names the PNG by absolute path — which is what
actually makes it appear, with no theme index and no cache rebuild involved.
`hicolor` belongs to every other app on the machine, and an earlier version of
this installer wrote an `index.theme` there that made unrelated icons vanish.

`--dry-run` shows what it would do; `--uninstall` removes it;
`--refresh-caches` regenerates the icon and desktop caches if your desktop
genuinely needs it. Off by default, because those caches are shared with every
other per-user application.

Editing the source takes effect immediately — the launcher points at the
checkout rather than copying files, so there is nothing to reinstall.

**The logo.** `mentorsmith/assets/logo.svg` is the single source of truth.
`tools/build_icons.py` renders it to every size the desktop and Android need
using PyQt6's QtSvg, so there is no Inkscape or ImageMagick requirement:

```bash
python3 tools/build_icons.py
python3 tools/build_icons.py --check     # fail if the PNGs are stale
```

## Try it in five minutes

```bash
git clone <your-fork-url> mentorsmith && cd mentorsmith
python3 -m pip install --user PyQt6

python3 main.py --check      # builds the UI offscreen, reports your toolchains
python3 main.py              # launch
```

Then, to see the parts that are hard to describe:

```bash
python3 -m pytest tests/ -q                       # 1151 tests
python3 tools/security_audit.py                   # real containment evidence
python3 tools/export_curriculum.py --check        # Android assets current?
python3 tools/export_theme.py --check             # Android colours current?
```

`export_theme.py` generates the Android palette from `mentorsmith/ui/theme.py`,
so the two apps cannot quietly drift into looking like different products.

A good first tour:

1. **Lessons → Variables and Types.** Mark it complete. Note that the dashboard
   still says *not started* — on purpose. Reading is not evidence.
2. **Practice**, pick a `find-a-bug` exercise, get it wrong on purpose. The
   debugging coach gives one small hint, not the answer.
3. **Progress** after a few attempts. Every label quotes the numbers behind it.
4. **Developer → Security audit.** Press the button. Read what each check says
   it *does not* prove.
5. Switch to **Python** in the toolbar and complete a C++ lesson's progress. It
   does not carry over — mastery never transfers between languages.

---

## Architecture and data flow

```
lesson (Markdown) ──┐
concept graph (JSON)┼─> curriculum_registry ──> per-language Track
exercise bank (JSON)┘                              (lessons, model, bank)
                                                        │
  learner edits code ──> execution adapter ──> compiler/interpreter
        │                   (limits, timeout,          │
        │                    bounded output)           ▼
        └──────────────> stdout / stderr / exit code  real output
                                                        │
  graded attempt ──> db.record_exercise_attempt(language, ...)
                                                        │
                          concept_evidence(language) ──┤
                                   │                    │
                          core/mastery ──> core/adaptive ──> services/insights
                                   │           core/revision            │
                                   v                                 v
                            label + evidence                 dashboard explains
                                                                     │
                                                                     v
                                                                 Qt UI / Compose
```

The rule that shapes the layering: **evidence flows one way.**
`exercise_attempts` → `concept_evidence` → `mastery` → `adaptive`/`revision` →
`insights` → UI. All interpretation lives in `mastery` and `adaptive`; no widget
computes a label. That is why the desktop app and the Android app can agree on
the same answer without sharing a line of code.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Desktop UI | PyQt6 | Native Linux widgets, no web runtime |
| Language | Python 3.11+ | The tutor's own code is short enough to read |
| HTTP | Python standard library | No third-party HTTP client to audit |
| Persistence | SQLite | One file, no server, trivially backed up |
| Android | Kotlin + Compose + Room | One data model, two very different UIs |
| Sync | FastAPI + SQLite | Optional, local, no cloud service |
| Dependencies at runtime | **PyQt6 only** | |

The test-only dependencies are pytest and, for the sync server, FastAPI. The
Android build needs the Android SDK and a JDK 17–21.

---

## What it does

### Four language tracks

| Track | Lessons | Toolchain |
|---|---|---|
| C++ | 16 | `g++` or `clang++` |
| Python | 9 | `python3` |
| C | 9 | `gcc` or `clang` |
| JavaScript | 8 | `node` |

Switch language from the toolbar. Lessons, concepts, exercises, adaptive
recommendations and progress are all **scoped per language**: being strong at
C++ pointers says nothing about C pointers, so a label is never carried across
tracks.

A **Compare languages** tab shows the same idea in two languages side by side,
focused on where they genuinely differ — `7 / 2` is `3` in C and `3.5` in
Python, and reading one track after another quietly teaches the wrong thing.

### Curriculum and lessons

- Each lesson has objectives, an explanation, a worked example, knowledge
  checks, an exercise with starter code, common mistakes, and a recap. Content
  lives in Markdown under `mentorsmith/lessons/<language>/`, not in UI code.

### The theory book, and the books it follows

- Every track has a **Theory Book**: a longer conceptual reference beside
  the lesson, covering the same ground at a different pace. 63 chapters
  across the five languages, each with examples, common mistakes, review
  questions and a practice task.
- The Java and C++ chapters are written to accompany two textbooks that sit
  in this project under `theory/`:
  - *Programming with Java: A Primer*, E. Balagurusamy (3rd edition)
  - *Object Oriented Programming with C++*, Dhamodharan G, Balasubramanian
    and Priya K
- Each chapter names the book section it follows and the **page** it starts
  on, so the two can be read side by side. The **Open in book** button
  opens your own copy of the PDF at that page.
- The app never ships, copies or quotes the books. It holds an original
  explanation per topic and points at the page; the PDFs are found on disk
  in `theory/<language>/`, in `~/.local/share/mentorsmith/books/<language>/`,
  or wherever `MENTORSMITH_BOOKS_DIR` points.
- Java gained six chapters and C++ three, covering what the books teach and
  the app was missing: inheritance, interfaces, packages, file I/O,
  threads, assertions, operator overloading and virtual functions.

### Real compile and run

- Compiles or interprets with the right tool per language, showing the exact
  command, the compiler's own diagnostics, stdout and stderr separately, the
  exit code and the wall-clock time. Failures are displayed honestly and are
  never dressed up as success.
- A **code editor** with syntax highlighting and a line-number gutter.
- Language-specific differences are preserved rather than abstracted away:
  Python runs in isolated mode, JavaScript has its heap capped, C is forced into
  C mode with `-x c`, and only compiled languages can be sandboxed.

### Adaptive practice

- **65 concepts** with an explicit prerequisite graph, held as structured data
  and validated on load (unknown references and prerequisite cycles fail at
  startup).
- **111 exercises across 8 types**: predict-output, find-a-bug, complete-code,
  write-a-function, explain-code, modify-code, solve-without-AI, and
  compare-implementations. Every concept has at least one.
- **Deterministic grading where possible.** Code exercises are compiled or run,
  and the real output is compared against the expected output, with a diff when
  they differ. Free-form explanations are graded by the tutor against a rubric
  and are always labelled *interpretive* — an opinion, not a proof.
- **A guided debugging coach**: capture the failure, categorise it where the
  evidence allows, give one small hint, let you retry, escalate only after
  repeated failure, and ask a related question after you fix it.
- **The next activity is chosen from your history** and always comes with its
  reason, quoting your own numbers.
- **A "Review today" card** on the Mastery page leads with one sentence saying
  how many concepts are worth revisiting, and each one carries a badge with the
  number of times you got it wrong — a concept failed four times is a different
  problem from one that is merely stale. **Start reviewing** opens the lesson
  that teaches the top one.

### Evidence, not vibes

A concept gets a label — `not_started`, `needs_review`, `developing`, `strong` —
but a label is a **summary, not a measurement**, and the app always shows the
counts behind it. Two things are deliberately *not* counted as evidence of
learning:

- chat messages sent to the tutor
- time spent in the app

Only graded exercise attempts count, and **completing a lesson is not
evidence** either.

### Projects

- Projects are proposed from concepts you have *demonstrated*, not merely
  opened. A blocked project tells you which concepts to strengthen first.
- Each project splits into small milestones, each with requirements and
  acceptance criteria you can check yourself.

## Requirements

- Fedora Linux (other Linux distributions should work)
- Python 3.11 or newer
- PyQt6
- A compiler or interpreter for each track you want to use

| Track | Needs | Install if missing |
|---|---|---|
| C++ | `g++` or `clang++` | `sudo dnf install gcc` |
| C | `gcc` or `clang` | `sudo dnf install gcc` |
| Python | `python3` | `sudo dnf install python3` |
| JavaScript | `node` | `sudo dnf install nodejs` |

Check what is present:

```bash
python3 main.py --check
```

MentorSmith never installs software for you. If a tool is missing it says so
and gives the exact command, and the rest of the app keeps working.

Run it straight from the checkout — no install step or packaging is required:

```bash
cd "/home/subro/Documents/APPS/programming tutor space bunny"
python3 main.py
```

To confirm the install without opening a window:

```bash
python3 main.py --check
```

That builds the entire UI headlessly and prints what was found:

```
MentorSmith 0.1.0
  lessons loaded : 16
  pages built    : 3
  compiler       : g++ (g++ (GCC) 16.2.1 20260819 (Red Hat 16.2.1-2))
  sandbox        : INACTIVE
  database       : /home/subro/.local/share/mentorsmith/progress.db
```

## Configuring the AI tutor

Everything else works without the AI. To enable the tutor: open **Settings →
AI Provider**, paste your key, and press **Detect**.

**The key.** Paste it into the masked field and press **Save**. It is written
to `~/.local/share/mentorsmith/secrets.json` with mode `0600` — deliberately a
*different file* from `settings.json`, so sharing or diffing your settings
cannot leak it. It is never written to the database, to a log, or into an
error message.

If you would rather not keep a key on disk, leave the field empty and export
`MENTORSMITH_API_KEY` in your shell instead. Both work, the stored key wins,
and **Forget stored key** removes it again.

**The provider is worked out from the key.** A key beginning `sk-or-v1-` is
OpenRouter's alone, so the endpoint fills itself in; `gsk_` and `AIza` work the
same way. Detection is local string inspection and **sends the key nowhere**.

Most prefixes are *not* unique — `sk-` is issued by OpenAI, OpenRouter's
legacy keys, DeepSeek and Together. Guessing between them decides which company
receives your credential, so an ambiguous key lists the candidates and asks you
once instead of picking silently. Pick from **Provider** or type the endpoint
yourself if you would rather not.

**The model.** A dropdown in the chat topbar, filled from your provider's own
`/models` listing — so it is never a stale hardcoded list. It stays editable,
because a provider without that endpoint should not stop you typing a name.
The selection is per conversation, and you can switch model between turns.

**Test connection** sends one small real request and reports what came back, so
you find out now rather than mid-lesson.

The app speaks the widely used `POST /chat/completions` shape, so one adapter
covers most hosted models.

### What a request cost

The chat footer shows the running cost of the conversation: tokens in and out,
and an estimated dollar figure. **Token counts are exact** — they come from the
provider's own accounting, not from counting characters locally. **The money
is an estimate**, computed from a dated table of published list prices, and it
is labelled as one. A model that is not in the table gets **no figure at all** —
not zero, not a guess. A provider that reports no usage is not counted.

### Stopping a request

A request to a slow or wedged provider can be given up on. The **Stop** button
appears while a request is in flight; it closes the provider's connection, which
unblocks a read already in progress, and any reply that still arrives is
discarded rather than appearing in the transcript as though it had been wanted.

### When your code leaves the machine

Only when you send a message, MentorSmith sends the following to your provider:
the lesson title and objectives, the code in the editor, the compiler and
runtime output on screen, and your message. Nothing is sent otherwise, and the
chat panel says so at all times.

To block every AI call:

```bash
export MENTORSMITH_OFFLINE=1
```

Or tick the box in Settings. Lessons, compiling, running and progress tracking
keep working; the tutor explains that it is offline instead of pretending.

## Running your code: sandbox and limits

Your code is untrusted input, so it is contained rather than trusted. Two
layers apply:

**Always on — resource limits.** CPU time, address space, file size and core
dumps are capped for the child process only. Limits are per language where the
runtime needs it: Node's V8 reserves a large *virtual* address space before
running any user code, so its limit is raised and the real heap is bounded with
`--max-old-space-size` instead.

**Always on — bounded output.** Captured output is capped at 200,000 characters
**while it is being read**, not afterwards. A program printing in a tight loop can
emit gigabytes within the time it is allowed to run, and reading all of it into
memory first is how the app would exhaust the machine. Discarded output is
counted and the learner is told, rather than being silently dropped.

**On by default — bubblewrap sandbox.** Compiled languages only. Where
bubblewrap (`bwrap`) is installed, the binary runs in a private mount
namespace with no network and a read-only view of the system, so your program
cannot read or write your home directory. This is the default because learner
code is code you did not write, and running it with your own file access
means a stray path can do real damage. Turn it off in Settings if a program
needs to reach the host; your choice is remembered. Where bubblewrap is not
installed the setting stays off, because a promise of containment that is not
there is worse than none. Interpreted languages have no binary to isolate,
and the app says so rather than implying otherwise.

**This is defence in depth, not a real sandbox.** `bwrap` relies on unprivileged
user namespaces, and those give far less protection than a VM or a properly
configured container. Do not treat it as isolation you can safely run genuinely
hostile code in. The status bar always states which mode is actually in force.

Your code runs in a dedicated directory per language:

```
~/.local/share/mentorsmith/workdir/<language>/
```

Compiled binaries and objects never touch the source tree.

## Tests

```bash
python3 -m pip install pytest
python3 -m pytest tests/ -q
```

The suite covers database operations and migrations, curriculum parsing,
tutor prompting and response parsing, provider error handling (with the network
replaced by a fake), compiler detection, successful and failed compilation,
runtime timeouts, stopping a running program, memory limits, sandbox isolation,
and a headless UI smoke test.

Compiler-dependent tests skip themselves if no compiler is present. AI is
always mocked, so the suite runs offline and costs nothing.

## Project layout

```
main.py                     Entry point (--check builds the UI headlessly)
tools/export_curriculum.py  Publishes the curriculum as the Android app's JSON
sync_server/                Optional local sync backend (FastAPI + SQLite)
android/                    Android companion (Kotlin, Compose, Room)
mentorsmith/
  app.py                    QApplication bootstrap
  config.py                 Paths and non-secret settings
  data/
    concepts.json           C++ concept graph + project catalogue
    exercises.json          C++ exercise bank
    curriculum/<lang>.json  Concept graph + exercises for the other tracks
  lessons/<language>/       One Markdown file per lesson
  core/
    db.py                   SQLite persistence, schema migrations
    curriculum.py           Lesson loading and the file format
    curriculum_registry.py  One entry point per language
    concepts.py             Concept model + prerequisite graph
    exercises.py            Exercise bank, grading, model-output prompts
    mastery.py              Evidence -> label, always with reasons
    adaptive.py             Which exercise next, and why
    debugging.py            Diagnose, hint, retry, escalate
    projects.py             Project proposals and milestones
    revision.py             Review recommendations and regressions
    comparisons.py          Cross-language differences
  execution/                Per-language adapters + shared process runner
    base.py                 Adapter interface, resource limits, sandbox
    cpp.py c.py python.py javascript.py
  providers/
    base.py                 Provider interface and typed errors
    openai_compat.py        /chat/completions client, stdlib only
  services/
    tutor.py                Assistance levels, prompts, response parsing
    practice.py             One exercise, end to end (no Qt)
    insights.py             Dashboard assembly and justifications
  ui/                       Qt widgets (theme, editor, panels, window)
tests/                      pytest suite
docs/                       Architecture notes, how to add a language
```

Only PyQt6 is required at runtime; HTTP uses the Python standard library, so
there is no third-party HTTP dependency.

## How recommendations work

Deterministic, and inspectable in the UI:

1. **Repair** — a concept already attempted but weak, especially with a
   recurring error category. New material waits.
2. **Consolidate** — correct first time, but only once. One correct answer is
   not evidence of understanding, so an unfamiliar variation comes next.
3. **Extension** — prerequisites all strong, nothing attempted yet.
4. **Delayed review** — a strong concept not practised recently, revisited with
   a variation rather than the worked example.

A recurring error category (three or more occurrences of the same one) forces a
review flag even when the overall score is high, because one recurring
misunderstanding is the thing worth fixing.

No scheduling method guarantees mastery, and the app says so where it shows
recommendations. Only a new, unfamiliar problem can show whether something
transferred.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+R` | Dashboard |
| `Ctrl+K` | Practice |
| `Ctrl+L` | Lessons |
| `Ctrl+P` | Progress and insights |
| `Ctrl+J` | Projects |
| `Ctrl+Shift+P` | Compile and run the current lesson |
| `Ctrl+,` | Settings |
| `Ctrl+Enter` | Send a chat message |

### Developer tools

A **Developer** page in the desktop app, and a CLI equivalent for the audit.

**Security audit — `python3 tools/security_audit.py`**

Runs real code and reports what it observed on this machine, right now. Every
check states both what it *proves* and what it *does not*. A check that cannot
run here is reported as `SKIPPED` with the reason, never as passed.

```
Verdict: 9 check(s) verified on this machine, 0 skipped.
Limits are real but this is NOT a security boundary.

[PASS] runtime timeout
  Proves: That a program which never finishes is killed and reported as a timeout.
  Does not prove: That a runaway program is stopped. It says nothing about a
  program that exits cleanly after doing damage.

[PASS] filesystem sandbox
  Proves: That with the sandbox enabled, a compiled program cannot list the
  user's home directory.
  Does not prove: Isolation of *any* kind. The sandbox is off by default,
  depends on unprivileged user namespaces being permitted, and is far weaker
  than a VM or a configured container.
```

**Git integration**

Read-only inspection (status, diff, log, branches) is free to do. Committing is
**approval-gated**: the first press produces a preview of exactly what would be
recorded, and only then does the write button become live. It then asks again
before writing.

There is deliberately **no** push, checkout, reset, clean or stash in that
module. Phase 5 requires those to be approval-gated and to show consequences
first; the most reliable way to guarantee that is for the capability not to
exist. Uncommitted work can be hours of effort.

Note that an untracked file is *not* in the index, so it is never reported as
about to be committed until you stage it.

**Code review**

Findings are labelled by how they were established, and the label is not
decorative:

| Label | Meaning | Counted as a defect? |
|---|---|---|
| `CONFIRMED` | A compiler or a test produced the diagnostic | yes |
| `HEURISTIC` | A static pattern matched; needs a human to read it | no |
| `SUGGESTION` | The model *believes* there may be a problem | no |

Compiler diagnostics are merged into the same list as the model's output while
keeping their origin visible. Only `CONFIRMED` findings count as bugs, and a
model cannot promote itself by writing `origin: confirmed` — a test asserts
that.

**Test generation**

Tests are proposed, never run automatically. `ProposedTest.execute()` requires
an explicit confirmation, and the report always states how many were proposed
versus executed, and which kinds of case were never covered. A passing generated
suite is not evidence of correctness, and the output says so.

**Project workspaces**

Each learning project gets its own directory under
`~/.local/share/mentorsmith/workspaces/<id>/`. Project files are never written
into the tutor's source tree. Paths are validated *after resolution*, so
`../../` and absolute paths are both refused rather than sanitised and hoped
about.

## Android companion

A read-and-revise companion app lives in `android/`. It does **not** run code —
that stays on Linux, where the real compiler is.

```bash
python3 tools/export_curriculum.py     # publish the curriculum into assets/
cd android
./gradlew :app:assembleDebug           # build the APK
./gradlew :app:testDebugUnitTest       # 41 JVM unit tests
```

It carries the same curriculum, the same mastery rules and the same output
comparison, so both devices agree about what was learned. Progress is written
locally first and only marked *synced* once a server confirms it.

**Tutor chat is disabled on Android, on purpose.** An APK is not a secret: a key
compiled into it can be extracted by anyone who downloads it. Chat is served by
the optional backend instead, which holds the key server-side. See
[docs/sync-contract.md](docs/sync-contract.md).

## Known limitations

**Untested surfaces**

- **No request has ever been sent to a real AI provider.** The provider tests
  mock `urlopen`. The live path, including how a real model responds to the
  interpretive-grading prompts, is unverified.
- **The Android app has never been run.** It builds and its logic is unit
  tested, but no device or emulator test exists — this machine had no system
  images or `cmdline-tools`.
- **No release build, packaging or signing** has been attempted.
- **No security review.** The audit in `tools/security_audit.py` verifies
  containment, not the absence of vulnerabilities.

**Deliberate gaps**

- Tutor chat on Android is disabled: an APK is not a secret store, so the key
  must live on a backend. See [docs/sync-contract.md](docs/sync-contract.md).
- The sync backend has **no authentication**. Anyone who can reach the port can
  read and write stored progress. Bind it to localhost.
- There is no offline model. Everything except the tutor's AI features works
  with no network; the tutor itself does not.
- No project generator for Python, C or JavaScript — projects are generated for
  C++ only.

**Quality and scope**

- The in-app Markdown renderer covers the subset the lessons use, not the whole
  specification.
- Exercise coverage is uneven: C++ has 53, the other tracks 11–12 each.
- Mastery labels are a summary of recorded counts. Explainable, but not a
  psychometric measurement.
- Review recommendations use a fixed staleness threshold, not a proven spaced
  repetition schedule. Delayed-review results are reported, but scheduling is
  not adaptive.
- The editor has no autocomplete and highlights C++ only.
- Progress is per-machine on the desktop.
- The bubblewrap sandbox covers compiled languages only, and unprivileged user
  namespaces give far less protection than a real isolation boundary.

**Known bugs**

None are known at the time of writing, beyond the limits above. The one real
defect found during development was in output capture — see
[PROJECT_STATE.md](PROJECT_STATE.md) — and it is fixed with a regression test.

## Licence

Personal project. See `PROJECT_STATE.md` for current status and next steps.