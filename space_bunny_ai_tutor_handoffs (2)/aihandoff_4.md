# AI HANDOFF — PHASE 4
## Add Python, C, and JavaScript learning tracks

Continue the current project. Do not rebuild it or replace the existing C++ curriculum.

## Workflow
Read `PROJECT_STATE.md`, architecture, curriculum models, execution adapters, database schema, API contracts, and tests. Run tests first. Plan incremental changes. Preserve progress and compatibility. Test actual execution for each language. A lesson page alone does not mean a language is supported. Update handoff notes with real results.

## Objective
Support C++, Python, C, and JavaScript using shared learning logic and language-specific tooling.

## 1. Architecture
Shared model: concepts, prerequisites, lessons, exercises, assessments, projects, and history.

Language-specific modules: syntax/examples, compiler/interpreter selection, diagnostics, execution config, tests, and curriculum. Do not abstract away meaningful language differences.

## 2. Curriculum scope
**Python:** variables/types, conditions/loops, functions, collections, exceptions, modules, files, classes, testing.

**C:** program structure, types, conditions/loops, functions, arrays/strings, pointers, structures, memory management, files.

**JavaScript:** variables/types, conditions/loops, functions, arrays/objects, scope, error handling, modules, asynchronous fundamentals.

Preserve the existing C++ curriculum. Respect prerequisites.

## 3. Execution adapters
- C++: GCC or Clang
- C: GCC or Clang
- Python: configured Python interpreter
- JavaScript: configured runtime such as Node.js

Detect missing tools and provide installation guidance; do not silently install software. Keep adapters modular. Use timeouts and appropriate isolation. Never execute arbitrary generated shell commands automatically. Document security limits.

## 4. Cross-language comparisons
Offer exercises comparing concepts such as loops in C++/Python, pointers in C/C++, and functions in JavaScript/Python. Explain meaningful differences; similar names do not imply identical semantics.

## 5. Projects and adaptive learning
Generate projects based on demonstrated prerequisites. Include requirements, milestones, acceptance criteria, hints, and tests where practical. Do not transfer mastery automatically between languages; use diagnostic exercises to check whether knowledge transfers.

## 6. Android
Allow language selection and browsing lessons, quizzes, revision, and project requirements on Android. Keep complex execution on Linux unless Android execution is separately designed and genuinely tested. Sync progress per language.

## 7. Tests
Test curriculum loading, language selection, runtime selection, missing tools, compile/run failures, per-language progress, comparisons, sync, and backwards compatibility.

## Acceptance checklist
- [ ] Four tracks have meaningful lessons and exercises
- [ ] Correct runtime/compiler used per language
- [ ] Missing tools handled clearly
- [ ] Progress tracked per language
- [ ] Adaptive recommendations and projects work
- [ ] Android/Linux remain compatible
- [ ] Tests actually run and results recorded
- [ ] Docs accurately describe coverage

## Handoff
Update `PROJECT_STATE.md` with features, runtime requirements, curriculum coverage, actual test results, limitations, and how to add a language. **Do not start Phase 5 until I approve.**
