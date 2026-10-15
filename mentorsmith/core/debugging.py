"""Guided debugging: diagnose, hint, let the learner retry, then escalate.

The order matters and is deliberate:

1. capture what actually happened (compiler text, exit code, stdout)
2. categorise the problem where the evidence supports it
3. offer **one small hint**, never the fix
4. let the learner retry
5. escalate to a guided explanation only after repeated failure
6. after a fix, ask a related question so the lesson lands

Two constraints are enforced in the prompts rather than left to chance:

* Hints stay small. They name *what to look at*, not what to write.
* **Hidden chain-of-thought is never requested or revealed.** Escalation asks
  the learner for a concise statement of what they think is happening and what
  evidence they have, and the tutor is explicitly told not to expose private
  reasoning.

When the evidence does not support a specific diagnosis, the category is
``unknown`` and the explanation says so. Guessing confidently would teach the
learner to trust a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Attempts with a hint before the coach escalates to a guided explanation.
DEFAULT_ESCALATION_AFTER = 2


@dataclass(frozen=True)
class DebugCategory:
    """How to talk about one class of failure."""

    name: str
    summary: str
    hint: str
    follow_up: str
    #: Patterns in compiler or runtime text that support this diagnosis.
    patterns: tuple[str, ...] = ()


#: Ordered most specific first; the first match wins.
CATEGORIES: tuple[DebugCategory, ...] = (
    DebugCategory(
        name="missing_semicolon",
        summary="A statement is missing its terminating semicolon.",
        hint="Look at the line the compiler complained about, and at the line "
             "just before it. One of them is missing a semicolon.",
        follow_up="Why does the compiler usually report the error one line "
                  "*after* the real mistake?",
        patterns=(r"expected ['\"]?;['\"]?", r"expected ';'"),
    ),
    DebugCategory(
        name="undeclared_identifier",
        summary="A name is being used that was never declared or is not in scope.",
        hint="Check the spelling of the name, and check that whatever should "
             "declare it appears before the line using it.",
        follow_up="What is the difference between a name that is misspelled "
                  "and a name that is declared too late?",
        patterns=(r"was not declared", r"not declared in this scope", r"has not been declared"),
    ),
    DebugCategory(
        name="type_mismatch",
        summary="A value of one type is being used where another is required.",
        hint="Look at the type of each operand in the reported expression. One "
             "of them is probably not the type the other needs.",
        follow_up="Which C++ rule does an implicit conversion here depend on, "
                  "and is it one you should rely on?",
        patterns=(r"invalid conversion", r"cannot convert", r"no matching function",
                  r"conflicting return type"),
    ),
    DebugCategory(
        name="missing_return",
        summary="A function declared to return a value reaches the end without returning one.",
        hint="Look at the end of the function that the warning or error names. "
             "Every path out of it must produce a value.",
        follow_up="Why is falling off the end of a value-returning function "
                  "worse than it looks?",
        patterns=(r"no return statement in function", r"control reaches end of non-void"),
    ),
    DebugCategory(
        name="null_dereference",
        summary="A pointer was dereferenced while it was null or uninitialised.",
        hint="Find every place the pointer is set before it is used. Is there a "
             "path where it is used first, or where it is reset to nothing?",
        follow_up="Which of your pointers could still be null on the very first "
                  "line of a function, and how would you find out?",
        patterns=(r"segmentation fault", r"null pointer", r"nullptr"),
    ),
    DebugCategory(
        name="memory_leak",
        summary="Memory was allocated and never released.",
        hint="Trace where the allocation happens and where it is supposed to be "
             "released. If it crosses a function boundary, check the return path.",
        follow_up="What guarantees release if an exception is thrown between "
                  "allocation and delete?",
        patterns=(r"leak", r"new\b.*without delete"),
    ),
    DebugCategory(
        name="runtime_timeout",
        summary="The program never finished, so it was stopped.",
        hint="Find the loop in your program and ask what would make its "
             "condition eventually false.",
        follow_up="Which part of the loop makes progress toward its exit "
                  "condition on every pass?",
        patterns=(),
    ),
    DebugCategory(
        name="runtime_error",
        summary="The program started and then failed while running.",
        hint="Read the exit code and any message printed before it. The last "
             "thing your program managed to do is usually the clue.",
        follow_up="What was the last value your program had before it failed?",
        patterns=(r"terminate called", r"what\(\):", r"assertion", r"uncaught exception"),
    ),
)

GENERIC_COMPILE = DebugCategory(
    name="compile_failure",
    summary="The code did not compile. The compiler told you exactly where.",
    hint="Read the first 'error:' line, not the last. It points at the first "
         "thing that was actually wrong; everything after it may be a "
         "consequence.",
    follow_up="If fixing the first error revealed a second one, why was the "
              "second one invisible before?",
    patterns=(),
)

GENERIC_RUNTIME = DebugCategory(
    name="wrong_output",
    summary="The program ran to completion but produced the wrong result.",
    hint="Work out what the correct output should be, then find the one value "
         "or one condition that differs. Do not rewrite it yet.",
    follow_up="Which single change fixed it, and why was that the right place "
              "rather than another?",
    patterns=(),
)


def category_by_name(name: str) -> DebugCategory:
    for category in (*CATEGORIES, GENERIC_COMPILE, GENERIC_RUNTIME):
        if category.name == name:
            return category
    return GENERIC_RUNTIME


@dataclass
class DebugDiagnosis:
    """What the coach believes went wrong, and how confident it is."""

    category: str
    summary: str
    hint: str
    follow_up: str
    confidence: str
    evidence: str = ""

    @property
    def is_specific(self) -> bool:
        return self.confidence == "specific"

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "summary": self.summary,
            "hint": self.hint,
            "follow_up": self.follow_up,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


def _match(text: str) -> DebugCategory | None:
    for category in CATEGORIES:
        for pattern in category.patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return category
    return None


def diagnose(
    *,
    compiled: bool,
    compile_stderr: str = "",
    stdout: str = "",
    exit_code: int | None = None,
    timed_out: bool = False,
    recorded_category: str = "",
) -> DebugDiagnosis:
    """Categorise a failure using only what actually happened.

    ``recorded_category`` is the coarse category already stored on the attempt
    (from :func:`mentorsmith.core.exercises.grade_deterministic`). It is used
    as a hint, never as a substitute for evidence.
    """
    if timed_out:
        category = category_by_name("runtime_timeout")
        return DebugDiagnosis(
            category=category.name,
            summary=category.summary,
            hint=category.hint,
            follow_up=category.follow_up,
            confidence="specific",
            evidence="The process was stopped for exceeding the runtime limit.",
        )

    if not compiled:
        matched = _match(compile_stderr)
        if matched is not None:
            evidence = _first_error_line(compile_stderr)
            return DebugDiagnosis(
                category=matched.name,
                summary=matched.summary,
                hint=matched.hint,
                follow_up=matched.follow_up,
                confidence="specific",
                evidence=evidence,
            )
        return DebugDiagnosis(
            category=GENERIC_COMPILE.name,
            summary=GENERIC_COMPILE.summary,
            hint=GENERIC_COMPILE.hint,
            follow_up=GENERIC_COMPILE.follow_up,
            # Honest: without a recognisable signature we cannot say more.
            confidence="general",
            evidence=_first_error_line(compile_stderr),
        )

    if exit_code not in (0, None):
        matched = _match(stdout)
        category = matched or GENERIC_RUNTIME
        return DebugDiagnosis(
            category=category.name,
            summary=category.summary,
            hint=category.hint,
            follow_up=category.follow_up,
            confidence="specific" if matched else "general",
            evidence=f"Exit code {exit_code}.",
        )

    # Ran to completion but produced the wrong output. The recorded category
    # from deterministic grading may name the issue, otherwise it is generic.
    category = GENERIC_RUNTIME
    confidence = "general"
    if recorded_category:
        candidate = category_by_name(recorded_category)
        if candidate is not GENERIC_RUNTIME:
            category = candidate
            confidence = "specific"
    return DebugDiagnosis(
        category=category.name,
        summary=category.summary,
        hint=category.hint,
        follow_up=category.follow_up,
        confidence=confidence,
        evidence="The program ran to completion but the output did not match.",
    )


def _first_error_line(text: str) -> str:
    for line in (text or "").splitlines():
        if "error:" in line:
            return line.strip()[:240]
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:240]
    return ""


# ----------------------------------------------------------------------
# Session
# ----------------------------------------------------------------------
STAGE_CAPTURE = "capture"
STAGE_HINT = "hint"
STAGE_RETRY = "retry"
STAGE_ESCALATE = "escalate"
STAGE_RESOLVED = "resolved"


@dataclass
class DebugSession:
    """Tracks one debugging episode from failure to fixed.

    Holds the stage, the attempt count and the hints already given, so the
    coach can escalate only after genuinely trying, and so hint usage is
    recorded honestly rather than guessed at.
    """

    concept_id: str = ""
    exercise_id: str = ""
    stage: str = STAGE_CAPTURE
    attempts: int = 0
    hints_used: int = 0
    escalations: int = 0
    last_diagnosis: DebugDiagnosis | None = None
    history: list[dict] = field(default_factory=list)
    escalation_after: int = DEFAULT_ESCALATION_AFTER

    # ------------------------------------------------------------------
    def on_failure(self, diagnosis: DebugDiagnosis) -> DebugDiagnosis:
        """Record a failed attempt and decide what to do next."""
        self.attempts += 1
        self.last_diagnosis = diagnosis
        self.history.append({"event": "failure", "diagnosis": diagnosis.to_dict()})

        if self.attempts >= self.escalation_after:
            self.stage = STAGE_ESCALATE
            self.escalations += 1
        else:
            self.stage = STAGE_HINT
        return diagnosis

    def give_hint(self) -> str:
        """Return the next hint and count it.

        After the first hint the wording pushes towards self-diagnosis rather
        than handing over more of the answer.
        """
        if self.last_diagnosis is None:
            return "Reproduce the failure first, then look at the first error."
        self.hints_used += 1
        self.stage = STAGE_RETRY
        self.history.append({"event": "hint", "index": self.hints_used})

        if self.hints_used == 1:
            return self.last_diagnosis.hint
        return (
            "Before another hint: state in one sentence what you think is "
            "wrong and what evidence in the compiler output or output supports "
            "that. Then say which line you would inspect first and why."
        )

    def on_retry(self) -> None:
        self.stage = STAGE_RETRY
        self.history.append({"event": "retry"})

    def on_resolved(self) -> str:
        """Mark fixed and return the related follow-up question."""
        self.stage = STAGE_RESOLVED
        self.history.append({"event": "resolved"})
        if self.last_diagnosis is None:
            return (
                "Now explain, in one or two sentences, what the bug was and "
                "what told you. That explanation is the part that transfers."
            )
        return (
            f"Good, that compiles and runs now. One related question before "
            f"you move on:\n\n{self.last_diagnosis.follow_up}"
        )

    @property
    def is_resolved(self) -> bool:
        return self.stage == STAGE_RESOLVED

    @property
    def needed_substantial_help(self) -> bool:
        """Whether the fix leaned on the coach rather than the learner."""
        return self.escalations > 0 or self.hints_used >= 2

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "exercise_id": self.exercise_id,
            "stage": self.stage,
            "attempts": self.attempts,
            "hints_used": self.hints_used,
            "escalations": self.escalations,
            "diagnosis": self.last_diagnosis.to_dict() if self.last_diagnosis else None,
            "needed_substantial_help": self.needed_substantial_help,
        }


def escalation_prompt(diagnosis: DebugDiagnosis | None, level: str = "guided") -> str:
    """System-style prompt for the escalation step.

    Explicitly forbids dumping private reasoning and asks for a short,
    checkable explanation instead.
    """
    known = diagnosis.summary if diagnosis else "an unresolved failure."
    return (
        "The learner has tried repeatedly and is still stuck.\n\n"
        f"Diagnosis so far: {known}\n\n"
        "Do the following:\n"
        "1. Do NOT reveal or imitate hidden internal reasoning. Do not output "
        "your own scratchpad or a 'thought process'.\n"
        "2. Give one short, verifiable piece of information the learner can "
        "check against the compiler output or the program's real output.\n"
        "3. Ask the learner to state, in one or two sentences, what they think "
        "is happening and what evidence supports it.\n"
        "4. Only after they answer, give the fix in small steps, one at a time."
    )


def post_fix_prompt(diagnosis: DebugDiagnosis | None) -> str:
    """Prompt for the related question asked after a successful fix."""
    question = diagnosis.follow_up if diagnosis else (
        "What was the bug, and what in the output told you?"
    )
    return (
        "The code now compiles and runs correctly. Ask one related question "
        "that makes the learner explain why the bug happened, so the lesson "
        "transfers to a different program.\n\n"
        f"Use this question: {question}"
    )