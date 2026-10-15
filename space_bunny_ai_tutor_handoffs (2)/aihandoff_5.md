# AI HANDOFF — PHASE 5
## Developer tools, reliability, and portfolio readiness

Continue the existing project as Space Bunny Free. Improve the system; do not rewrite it or add complexity for its own sake.

## Workflow
Read `PROJECT_STATE.md`, README, architecture/security notes, and tests. Run tests and record a baseline. Audit implementations before replacing them. Prioritise actual risks and user value. Make focused, reversible changes. Ask before destructive operations, external pushes, credential changes, or major architecture changes. Report actual test results and update project state.

## 1. Git integration
Optionally detect Git repositories, show modified files/diffs and recent commits, and create checkpoints. Commits require explicit approval; remote pushes always require explicit approval. Never discard user changes or resolve conflicts destructively without showing consequences and asking. Explain risky operations.

## 2. Project workspaces
Keep each learning project in its own workspace. Track requirements, milestones, source files, test results, feedback, notes, and progress. Do not mix learner projects with the tutor's source tree or write files to arbitrary locations.

## 3. AI code review
Find possible correctness issues, missing error handling, resource-management problems, maintainability concerns, missing tests, and unsafe operations. Each finding should include file/location where possible, explanation, importance, suggested fix, and verification steps. Distinguish confirmed compiler/test findings from speculative AI suggestions. Combine AI with compiler diagnostics, linters, static analysis, and tests. Show diffs before applying changes.

## 4. Test generation
Let AI propose tests for normal cases, boundaries, invalid input, expected failures, and prior bugs. Review generated tests before execution. Distinguish proposed from executed tests. A passing generated suite does not prove completeness.

## 5. Execution security audit
Review trust boundaries. Use appropriate isolation, dedicated workspaces, timeouts, resource limits, and restricted filesystem/network access where supported. A subprocess timeout is not a complete sandbox. Never claim full isolation unless actually implemented and verified.

## 6. Offline learning
Keep downloaded lessons, saved exercises, source code, local diagnostics, requirements, and progress available offline where practical. Explain which features need a network. Do not claim AI works offline unless a local model is configured and tested.

## 7. Provider/privacy
Improve model configuration, timeouts, rate-limit handling, response validation, and errors. Never commit/log secrets. Do not silently upload whole repositories. Explain the scope of source sharing. Do not assume free providers have unlimited availability.

## 8. Learning analytics
Show independent exercise completion, hint usage, repeated misconceptions, delayed review results, project milestones, and topics to practise. Distinguish independent work from work needing substantial AI assistance. Do not treat time or chat-message count as proof of learning. Explain recommendations.

## 9. Reliability
Review logging, errors, migrations, API validation, dependencies, configuration, test coverage, startup/shutdown, and sync recovery. Remove obsolete code only after verifying it is unused. Avoid premature optimisation.

## 10. Portfolio documentation
Update README with purpose, implemented features, architecture/data flow, stack, Fedora and Android setup, AI configuration, test instructions/results, security notes, limitations, and demo workflow/screenshots if available. Document only implemented features. Do not claim production readiness without evidence. Keep secrets and personal data out of Git.

## Acceptance checklist
- [ ] Git actions are reviewable and approval-gated
- [ ] Workspaces are organised
- [ ] AI review findings are qualified and verifiable
- [ ] Generated tests can be reviewed before running
- [ ] Execution security limitations are documented
- [ ] Offline behaviour matches docs
- [ ] Provider/privacy behaviour is clear
- [ ] Analytics use meaningful evidence
- [ ] Linux and Android still work
- [ ] Tests actually ran and results recorded
- [ ] Documentation matches the repo

## Final handoff
Update `PROJECT_STATE.md` with architecture, implemented features, real test results, security limitations, bugs, setup instructions, a demo plan, and prioritised future work. Do not claim production readiness just because the app launches.
