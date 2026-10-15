# MentorSmith

A Linux-first desktop tutor for learning C++ fundamentals, built with Python and
PyQt6.

MentorSmith compiles and runs **your own code** and shows you the real compiler
and runtime output, then pairs each lesson with an AI tutor that supports three
levels of help. On top of that it tracks *evidence* of understanding rather than
what you clicked, and adapts what it gives you next.

---

## What it does

### Curriculum and lessons

- **16 beginner C++ lessons**, from program structure to exceptions. Each has
  objectives, an explanation, a worked example, knowledge checks, an exercise
  with starter code, common mistakes, and a recap. The content lives in
  Markdown under `mentorsmith/lessons/`, not inside the UI code.

### Real compile and run

- Compiles and runs with `g++` or `clang++`, showing the exact command, the
  compiler's own diagnostics, stdout and stderr separately, the exit code and
  the wall-clock time. Failures are displayed honestly and are never dressed up
  as success.
- A **code editor** with C++ syntax highlighting and a line-number gutter.

### Adaptive practice

- **18 concepts** with an explicit prerequisite graph, held as structured data
  in `mentorsmith/data/concepts.json`.
- **53 exercises across 8 types**: predict-output, find-a-bug, complete-code,
  write-a-function, explain-code, modify-code, solve-without-AI, and
  compare-implementations.
- **Deterministic grading where possible.** Code exercises are compiled and run,
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
- A C++ compiler — `gcc` or `clang`

Check what you have:

```bash
python3 --version
g++ --version
```

## Install

```bash
sudo dnf install python3-pip gcc bubblewrap
python3 -m pip install --user PyQt6
```

`bubblewrap` is optional but recommended; see [Running your code](#running-your-code-sandbox-and-limits).

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
dumps are capped for the child process only.

**Optional — bubblewrap sandbox.** Enable it in Settings. It then runs your
program in a private mount namespace with no network and a read-only view of
the system, so your program cannot read or write your home directory.

**This is defence in depth, not a real sandbox.** `bwrap` relies on unprivileged
user namespaces, and those give far less protection than a VM or a properly
configured container. Do not treat it as isolation you can safely run genuinely
hostile code in. With the sandbox off (the default), your program runs as your
own user with your own file access. The status bar always states which mode is
actually in force — the app never claims protection it does not have.

Your code is compiled and run in a dedicated directory:

```
~/.local/share/mentorsmith/workdir/
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
mentorsmith/
  app.py                    QApplication bootstrap
  config.py                 Paths and non-secret settings
  data/
    concepts.json           Concept graph + project catalogue
    exercises.json          Adaptive exercise bank
  lessons/                  The 16 lessons, as Markdown
  core/
    db.py                   SQLite persistence, schema migrations
    curriculum.py           Lesson loading and the file format
    concepts.py             Concept model + prerequisite graph
    exercises.py            Exercise bank, grading, model-output prompts
    mastery.py              Evidence -> label, always with reasons
    adaptive.py             Which exercise next, and why
    debugging.py            Diagnose, hint, retry, escalate
    projects.py             Project proposals and milestones
    revision.py             Review recommendations and regressions
  compiler/
    toolchain.py            Detect, compile, run, contain
  providers/
    base.py                 Provider interface and typed errors
    openai_compat.py        /chat/completions client, stdlib only
  services/
    tutor.py                Assistance levels, prompts, response parsing
    practice.py             One exercise, end to end (no Qt)
    insights.py             Dashboard assembly and justifications
  ui/                       Qt widgets (theme, editor, panels, window)
tests/                      pytest suite
docs/                       Architecture notes
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

## Known limitations

- Linux desktop only. The Android companion is not built yet.
- The in-app Markdown renderer covers the subset the lessons use, not the
  whole specification.
- The exercise bank ships 53 exercises. Coverage is thin for `constructors`,
  `files`, `strings` and `structures` (2 each).
- Mastery labels are a summary of recorded counts. They are explainable but
  they are not a psychometric measurement.
- Review recommendations use a fixed staleness threshold, not a proven spaced
  repetition schedule.
- There is no built-in test suite for the learner's own C++; exercises are
  graded by the compiler when you press **Run & check**.
- The editor has no autocomplete.
- Progress is per-machine and not synchronised anywhere.

## Licence

Personal project. See `PROJECT_STATE.md` for current status and next steps.