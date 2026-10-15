# AI HANDOFF — PHASE 2
## Adaptive learning, debugging coach, and personalised projects

Continue the existing project as Space Bunny Free. This is a continuation, not a rewrite.

## Workflow
Read `PROJECT_STATE.md`, README, architecture notes, relevant source, and tests. Run the current tests first and record the baseline. Plan briefly, then implement incrementally. Preserve Phase 1 behaviour and data. Use focused diffs, run tests after meaningful changes, and explain major code paths in plain language. Ask before destructive migrations or major architecture changes. Update `PROJECT_STATE.md`.

## Objective
Adapt the tutor to evidence of my understanding. Completing a lesson or receiving an AI solution must not automatically mean mastery.

## 1. Concept model
Represent concepts and prerequisites as structured data, including variables, types, conditions, loops, functions, arrays, strings, pointers, references, memory, classes, files, and errors.

Track exercise attempts, correctness, first-attempt success, hints used, repeated error categories, ability to explain a solution, unfamiliar variations, and delayed review results. Labels such as `needs_review`, `developing`, and `strong` are summaries—not scientific measurements. Make the evidence behind labels understandable.

## 2. Adaptive exercises
Support predict-output, find-a-bug, complete-code, write-a-function, explain-code, modify-code, solve-without-AI, and compare-implementations exercises. Use learning history, prerequisites, recurring mistakes, and recent results to choose work. Use deterministic tests where practical; use AI feedback for free-form explanations but label it as interpretive. Do not advance the learner just because they clicked through lessons.

## 3. Guided debugging
When code fails:
1. Capture actual output/error.
2. Categorise the issue where possible.
3. Offer a small hint.
4. Let me retry.
5. Escalate to guided explanation if needed.
6. After a fix, ask a related question.

Record attempts and hint use. Do not reveal hidden chain-of-thought; request concise explanations, evidence, and understandable debugging steps.

## 4. Project generator
Generate projects based on concepts I have studied and demonstrated. Each project needs a title, purpose, objectives, prerequisites, functional requirements, constraints, acceptance criteria, milestones, hints, tests/evaluation criteria, extension challenges, and difficulty estimate.

Examples: number guessing game, marks analyser, contact manager, library manager, expense tracker, log analyser, file-processing utility. These are examples, not a fixed list. Flag missing prerequisites. Prefer projects I implement myself.

## 5. Milestones and evaluation
Split projects into small milestones. Show requirements and acceptance criteria, let me implement, offer hints before full solutions, run tests where possible, record whether work was independent or needed substantial help, and preserve feedback. Never claim tests passed unless they were run. Show diffs and don't silently replace my files.

## 6. Revision
Add review exercises for concepts that need practice. Use past errors and delayed performance. Don't claim any scheduling method guarantees mastery. Explain why each topic is recommended for review.

## 7. Dashboard
Show topics studied, concepts to review, independent exercise results, hint usage, projects in progress, milestones, recurring error categories, and a suggested next activity with its reason. Don't count chatbot messages or app time as proof of learning.

## 8. Data and tests
Extend SQLite safely without losing Phase 1 progress. Keep concepts, prerequisites, attempts, projects, and UI separate. Validate structured model output before saving; never treat model output as executable instructions.

Test prerequisites, adaptive selection, hint tracking, project milestones, migrations, malformed AI content, provider failures, and revision recommendations.

## Acceptance checklist
- [ ] Exercise history affects recommendations
- [ ] Concepts can be flagged for review with explainable evidence
- [ ] Projects have milestones and acceptance criteria
- [ ] Attempts and progress persist
- [ ] Tests evaluate code where practical
- [ ] Dashboard explains next-step recommendations
- [ ] Phase 1 still works
- [ ] Tests/docs are updated

## Handoff
Update `PROJECT_STATE.md`. Report changes, migrations, actual test results, remaining issues, and how recommendations work. Explain what I should understand before Phase 3. **Do not start Phase 3 until I approve.**
