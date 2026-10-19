"""Tutor behaviour: three assistance levels, prompting and response parsing.

Privacy note
------------
Every method here that reaches a provider sends the learner's **code, compiler
output and lesson text to an external service**. That is a deliberate network
transfer and the UI states so explicitly. Nothing is sent when the provider is
unconfigured, and ``MENTORSMITH_OFFLINE=1`` can forbid calls outright.

Assistance levels
-----------------
``hint``
    One small clue. No solution, no code, and one question to push thinking
    forward.
``guided``
    Leading questions and stepwise direction. Still withholds the finished
    program, but will correct a misconception.
``full``
    A worked solution with the reasoning laid out. Used when the learner asks
    for it or gives up.

The level is a *default*, not a cage: a learner can ask for the full
explanation at any time. What the lower levels guarantee is that the tutor
does not volunteer the answer first.

Response format
---------------
The model is asked to answer in a small tagged format so replies can be parsed
reliably rather than by pattern-matching prose:

    EXPLANATION: what the learner should understand
    MISCONCEPTION: only when the learner has said something incorrect
    QUESTION: one question the learner should answer next
    ACTION: one of predict_output / explain_code / find_bug / write_program / none
    SOLUTION: only at the full level

:func:`parse_tutor_response` is pure and has no I/O, so it is unit-testable
without a network call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..providers.base import CompletionRequest, LLMProvider, TokenUsage

#: Ordered so the UI can present them as an escalation.
ASSISTANCE_LEVELS: tuple[str, ...] = ("hint", "guided", "full")

LEVEL_LABELS: dict[str, str] = {
    "hint": "Hint — a small clue only",
    "guided": "Guided — leading questions, stepwise",
    "full": "Full explanation — worked solution",
}

#: Recognised ``ACTION`` values.
ACTIONS = ("predict_output", "explain_code", "find_bug", "write_program", "none")

FIELD_RE = re.compile(
    r"^\s*(EXPLANATION|MISCONCEPTION|QUESTION|ACTION|SOLUTION)\s*:\s*(.*)$",
    re.IGNORECASE,
)


@dataclass
class TutorContext:
    """Everything the tutor knows about the learner's current attempt.

    ``attempt_count`` and ``misconception_shown`` let the tutor stay patient
    after a wrong answer instead of escalating to a solution on its own.
    """

    lesson_title: str = ""
    lesson_objectives: str = ""
    section: str = "exercise"
    code: str = ""
    compile_output: str = ""
    run_output: str = ""
    user_message: str = ""
    attempt_count: int = 0
    misconception_shown: bool = False


@dataclass
class TutorReply:
    """A parsed tutor response."""

    message: str = ""
    question: str | None = None
    misconception: str | None = None
    solution: str | None = None
    action: str = "none"
    reveals_solution: bool = False
    #: True when the raw text did not follow the tagged format.
    unparsed: bool = False
    raw: str = ""

    def as_chat_text(self) -> str:
        """Render the reply for the chat panel."""
        blocks = [block for block in (self.message, self.misconception, self.question) if block]
        if self.solution:
            blocks.append(f"**Worked solution**\n\n{self.solution}")
        return "\n\n".join(blocks) if blocks else self.raw


def normalise_level(level: str) -> str:
    """Coerce user input to a valid level, defaulting to ``guided``."""
    candidate = (level or "").strip().lower()
    return candidate if candidate in ASSISTANCE_LEVELS else "guided"


def build_system_prompt(level: str, context: TutorContext) -> str:
    """Instructions that enforce the chosen level and the tagged format."""
    level = normalise_level(level)

    common = [
        "You are MentorSmith, a patient C++ tutor for a learner who is building "
        "stronger fundamentals.",
        "",
        "Rules you always follow:",
        "- A claim is not proof. Refer only to the compiler and runtime output "
        "actually provided. Never state that code works unless the output "
        "shows it compiling and running without errors.",
        "- If output is missing, say you cannot tell yet and ask for a compile "
        "or run.",
        "- Address the specific misconception shown. Do not move on until it "
        "is resolved.",
        "- Keep replies short enough to read on a screen.",
        "",
        "Answer using exactly these tags, one per line, omitting any tag you "
        "do not need:",
        "EXPLANATION: what the learner should take away",
        "MISCONCEPTION: the wrong idea, and why it is wrong (only if the "
        "learner stated something incorrect)",
        "QUESTION: exactly one question for the learner to answer next",
        "ACTION: one of predict_output, explain_code, find_bug, "
        "write_program, none",
    ]

    if level == "hint":
        common += [
            "SOLUTION: do NOT include this tag at all.",
            "",
            "Level rules:",
            "- Give ONE small clue that unblocks their next step.",
            "- Do not write the corrected line, the full program, or the final "
            "answer.",
            "- Do not dump an example solution, even a partial one.",
            "- End with QUESTION so they keep thinking.",
        ]
    elif level == "guided":
        common += [
            "SOLUTION: do NOT include this tag unless the learner explicitly "
            "asks you to just show the answer.",
            "",
            "Level rules:",
            "- Ask leading questions one at a time instead of stating answers.",
            "- Break the problem into the next single step only.",
            "- If the learner is wrong, use MISCONCEPTION to correct the idea, "
            "then let them try again.",
            "- Never provide the complete working program unless explicitly "
            "asked.",
        ]
    else:
        common += [
            "SOLUTION: include the complete, correct code plus an explanation "
            "of why it works.",
            "",
            "Level rules:",
            "- Give the full worked answer, but explain the reasoning so it "
            "transfers to the next problem.",
            "- Still point out anything in their attempt that was right.",
        ]

    if context.misconception_shown:
        common += [
            "",
            "The learner has already been corrected once and is trying again. "
            "Be encouraging, address the same misconception, and do not raise "
            "the assistance level on your own.",
        ]

    return "\n".join(common)


def build_user_prompt(context: TutorContext) -> str:
    """The learner-facing half of the request, carrying the real evidence."""
    sections: list[str] = []

    if context.lesson_title:
        objectives = context.lesson_objectives.strip()
        sections.append(
            f"Lesson: {context.lesson_title}\n"
            + (f"Objectives:\n{objectives}\n" if objectives else "")
        )

    if context.section:
        sections.append(f"Part of the lesson: {context.section}")

    if context.code.strip():
        sections.append(f"The learner's C++ code:\n```cpp\n{context.code.strip()}\n```")

    if context.compile_output.strip():
        sections.append(
            "Actual compiler output:\n```\n"
            f"{context.compile_output.strip()[:4000]}\n```"
        )

    if context.run_output.strip():
        sections.append(
            "Actual runtime output:\n```\n" f"{context.run_output.strip()[:4000]}\n```"
        )

    if context.user_message.strip():
        sections.append(f"The learner's message:\n{context.user_message.strip()}")
    else:
        sections.append("The learner has not typed anything; respond to their code and output.")

    if context.attempt_count > 1:
        sections.append(
            f"This is attempt number {context.attempt_count}."
        )

    return "\n\n".join(sections)


def build_request(
    level: str, context: TutorContext, model: str = ""
) -> CompletionRequest:
    """Assemble the full :class:`CompletionRequest` for a turn.

    ``model`` is optional and defaults to empty, which means "use whatever the
    provider is configured with". The UI passes the chat panel's selection so a
    conversation can switch model between turns; every other caller is
    unaffected.
    """
    return CompletionRequest(
        system=build_system_prompt(level, context),
        user=build_user_prompt(context),
        # Hints need very little; a full explanation needs more room.
        max_tokens=1400 if normalise_level(level) == "full" else 700,
        temperature=0.3 if normalise_level(level) != "full" else 0.2,
        model=model.strip() or None,
    )


def parse_tutor_response(text: str) -> TutorReply:
    """Parse the tutor's tagged reply.

    Tolerant by design: if the model ignored the format, the whole text is
    kept as the message and ``unparsed`` is set, so a chatty or non-compliant
    model still produces a usable reply instead of an empty bubble.
    """
    raw = (text or "").strip()
    if not raw:
        return TutorReply(message="", unparsed=True, raw=raw)

    fields: dict[str, list[str]] = {}
    order: list[str] = []
    for line in raw.splitlines():
        match = FIELD_RE.match(line)
        if not match:
            # Continuation of the previous field.
            if order and line.strip():
                fields[order[-1]].append(line.strip())
            continue
        tag = match.group(1).upper()
        order.append(tag)
        fields.setdefault(tag, []).append(match.group(2).strip())

    if not fields:
        return TutorReply(message=raw, unparsed=True, raw=raw)

    def joined(tag: str) -> str:
        return "\n".join(part for part in fields.get(tag, []) if part).strip()

    action = joined("ACTION").strip().lower()
    if action not in ACTIONS:
        action = "none"

    explanation = joined("EXPLANATION")
    misconception = joined("MISCONCEPTION") or None
    question = joined("QUESTION") or None
    solution = joined("SOLUTION") or None

    # Build the main message from whatever explanatory text was given.
    message_parts = [explanation] if explanation else []
    if not message_parts:
        # The model only produced a solution, for instance.
        leftovers = [
            line for line in raw.splitlines() if not FIELD_RE.match(line)
        ]
        message_parts = ["\n".join(line for line in leftovers if line.strip()).strip()]

    return TutorReply(
        message="\n".join(part for part in message_parts if part).strip(),
        question=question,
        misconception=misconception,
        solution=solution,
        action=action,
        reveals_solution=bool(solution),
        unparsed=False,
        raw=raw,
    )


@dataclass
class TutorService:
    """Stateless glue between the UI and a provider.

    Kept free of Qt imports so it can be exercised headlessly in tests.
    """

    provider: LLMProvider
    level: str = "guided"
    #: Model for this conversation. Empty means "use the configured default";
    #: set from the chat panel's model picker.
    model: str = ""
    #: Set True the moment a request is actually dispatched, so the UI can
    #: show an explicit "this was sent to an external provider" notice.
    last_request_sent: bool = field(default=False, init=False)
    #: Token accounting and model for the most recent completed call, so the
    #: UI can show what it cost. ``None`` when the provider reported nothing.
    last_usage: "TokenUsage | None" = field(default=None, init=False)
    last_model: str = field(default="", init=False)

    def set_level(self, level: str) -> str:
        self.level = normalise_level(level)
        return self.level

    def ask(self, context: TutorContext) -> TutorReply:
        """Send one turn to the provider and parse the reply.

        Provider errors propagate to the caller; the UI is responsible for
        showing them, because only it knows how to present the settings link.
        """
        request = build_request(self.level, context, self.model)
        self.last_request_sent = True
        response = self.provider.complete(request)
        # Recorded before parsing: a reply the tutor parser dislikes still cost
        # real tokens, and pretending otherwise would undercount the meter.
        self.last_usage = getattr(response, "usage", None)
        self.last_model = getattr(response, "model", "") or request.model or ""
        return parse_tutor_response(response.text)