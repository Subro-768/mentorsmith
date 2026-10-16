# MentorSmith

A Linux-first desktop tutor for learning programming fundamentals, built with
Python and PyQt6.

MentorSmith compiles and runs **your own code** and shows you the real compiler
and runtime output, then pairs each lesson with an AI tutor that supports three
levels of help. On top of that it tracks *evidence* of understanding rather than
what you clicked, and adapts what it gives you next.

**Four tracks: C++, Python, C and JavaScript.** 42 lessons, 44 concepts,
87 exercises.

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

- **44 concepts** with an explicit prerequisite graph, held as structured data
  and validated on load (unknown references and prerequisite cycles fail at
  startup).
- **87 exercises across 8 types**: predict-output, find-a-bug, complete-code,
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

Everything else works without the AI. To enable the tutor you need three
things.

**1. Export your API key.** Keys are read from the environment and are never
written to the settings file, the database, or a log:

```bash
export MENTORSMITH_API_KEY="your-key-here"
```

Restart the app after exporting.

**2. Enter the endpoint and model** in **Settings**:

- **Base URL** — the API root. Most providers want something ending in `/v1`,
  for example `https://your-provider.example/v1`.
- **Model** — the exact model name your account can use.

No provider or model is hardcoded, and nothing assumes free or unlimited
access.

**3. Press "Test connection".** This sends one small real request and reports
what came back, so you find out now rather than mid-lesson.

The app speaks the widely used `POST /chat/completions` shape, so one adapter
covers most hosted models.

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

**Optional — bubblewrap sandbox.** Compiled languages only. Enable it in
Settings and the binary runs in a private mount namespace with no network and a
read-only view of the system, so your program cannot read or write your home
directory. Interpreted languages have no binary to isolate, and the app says so
rather than implying otherwise.

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

- Tutor chat on Android is not implemented; it needs the backend to exist first.
- The in-app Markdown renderer covers the subset the lessons use, not the
  whole specification.
- Exercise coverage is uneven. C++ has 53 exercises; the other tracks have
  11–12 each, which is enough to be useful but not to be a full course.
- There is no project generator for Python, C or JavaScript. Projects are
  generated for C++ only; the other tracks get exercises and lessons.
- Mastery labels are a summary of recorded counts. They are explainable but
  they are not a psychometric measurement.
- Review recommendations use a fixed staleness threshold, not a proven spaced
  repetition schedule.
- There is no built-in test suite for the learner's own code; exercises are
  graded by actually compiling and running it.
- The editor has no autocomplete and highlights C++ only.
- Progress is per-machine and not synchronised anywhere.
- The bubblewrap sandbox covers compiled languages only, and unprivileged user
  namespaces give far less protection than a real isolation boundary.

## Licence

Personal project. See `PROJECT_STATE.md` for current status and next steps.