"""Tutor behaviour: assistance levels, prompt construction, response parsing.

All tests use a fake provider, so none of them spend quota or reach the network.
"""

from __future__ import annotations

from mentorsmith.providers.base import ProviderNotConfigured
from mentorsmith.services.tutor import (
    ASSISTANCE_LEVELS,
    TutorContext,
    TutorService,
    build_request,
    build_system_prompt,
    build_user_prompt,
    normalise_level,
    parse_tutor_response,
)

from conftest import FakeProvider


# ----------------------------------------------------------------------
# Levels
# ----------------------------------------------------------------------
def test_three_levels_are_offered() -> None:
    assert ASSISTANCE_LEVELS == ("hint", "guided", "full")


def test_normalise_level_accepts_valid_levels() -> None:
    for level in ASSISTANCE_LEVELS:
        assert normalise_level(level) == level


def test_normalise_level_defaults_to_guided() -> None:
    assert normalise_level("nonsense") == "guided"
    assert normalise_level("") == "guided"
    assert normalise_level(None) == "guided"
    assert normalise_level("HINT") == "hint"


# ----------------------------------------------------------------------
# System prompt enforces the level
# ----------------------------------------------------------------------
def test_hint_level_forbids_the_solution() -> None:
    prompt = build_system_prompt("hint", TutorContext())
    assert "do NOT include this tag" in prompt
    assert "ONE small clue" in prompt
    assert "Do not write the corrected line" in prompt


def test_guided_level_forbids_unrequested_solutions() -> None:
    prompt = build_system_prompt("guided", TutorContext())
    assert "explicitly asks" in prompt
    assert "leading questions" in prompt
    assert "Never provide the complete working program unless explicitly asked" in prompt


def test_full_level_requires_a_worked_solution() -> None:
    prompt = build_system_prompt("full", TutorContext())
    assert "include the complete, correct code" in prompt


def test_every_level_forbids_claiming_untested_code_works() -> None:
    """The handoff is explicit that an LLM's claim is not proof."""
    for level in ASSISTANCE_LEVELS:
        prompt = build_system_prompt(level, TutorContext())
        assert "Never state that code works unless the output" in prompt


def test_every_level_asks_for_the_tagged_format() -> None:
    for level in ASSISTANCE_LEVELS:
        prompt = build_system_prompt(level, TutorContext())
        for tag in ("EXPLANATION:", "MISCONCEPTION:", "QUESTION:", "ACTION:"):
            assert tag in prompt


def test_patient_after_a_misconception() -> None:
    context = TutorContext(misconception_shown=True)
    prompt = build_system_prompt("hint", context)
    assert "do not raise the assistance level on your own" in prompt


# ----------------------------------------------------------------------
# User prompt carries real evidence
# ----------------------------------------------------------------------
def test_user_prompt_includes_code_and_output() -> None:
    context = TutorContext(
        lesson_title="3. Input and Output",
        lesson_objectives="- Read with std::cin",
        code="int main(){ return 0; }",
        compile_output="error: expected ';'",
        run_output="",
        user_message="why does it fail?",
    )
    prompt = build_user_prompt(context)
    assert "int main(){ return 0; }" in prompt
    assert "error: expected ';'" in prompt
    assert "why does it fail?" in prompt
    assert "3. Input and Output" in prompt


def test_user_prompt_states_when_nothing_was_typed() -> None:
    prompt = build_user_prompt(TutorContext(code="int main(){}"))
    assert "has not typed anything" in prompt


def test_user_prompt_reports_attempt_number() -> None:
    prompt = build_user_prompt(TutorContext(attempt_count=3))
    assert "attempt number 3" in prompt


def test_user_prompt_truncates_enormous_output() -> None:
    context = TutorContext(compile_output="x" * 50_000)
    prompt = build_user_prompt(context)
    assert len(prompt) < 10_000


def test_full_level_gets_more_token_budget_than_hint() -> None:
    hint = build_request("hint", TutorContext())
    full = build_request("full", TutorContext())
    assert full.max_tokens > hint.max_tokens


# ----------------------------------------------------------------------
# Response parsing
# ----------------------------------------------------------------------
def test_parses_all_fields() -> None:
    reply = parse_tutor_response(
        "EXPLANATION: 7 / 2 is 2 because both operands are integers.\n"
        "MISCONCEPTION: You expected 3.5, which requires a double operand.\n"
        "QUESTION: What is 7.0 / 2, and why does it differ?\n"
        "ACTION: predict_output"
    )
    assert reply.message.startswith("7 / 2 is 2")
    assert reply.misconception is not None
    assert "double operand" in reply.misconception
    assert reply.question is not None
    assert reply.action == "predict_output"
    assert not reply.reveals_solution
    assert not reply.unparsed


def test_solution_sets_reveals_solution() -> None:
    reply = parse_tutor_response(
        "EXPLANATION: Here is the finished program.\n"
        "SOLUTION: int main(){ return 0; }"
    )
    assert reply.reveals_solution
    assert "int main" in reply.solution


def test_multiline_field_is_preserved() -> None:
    reply = parse_tutor_response(
        "SOLUTION: int main() {\n    return 0;\n}\n"
    )
    assert "return 0;" in reply.solution
    assert "}" in reply.solution


def test_unknown_action_falls_back_to_none() -> None:
    reply = parse_tutor_response("EXPLANATION: hmm\nACTION: teleport")
    assert reply.action == "none"


def test_unparseable_reply_is_still_usable() -> None:
    """A chatty model must not produce an empty chat bubble."""
    reply = parse_tutor_response(
        "Sure! Let me think about this. First, look at your loop condition. "
        "Are you sure the counter starts at zero?"
    )
    assert reply.unparsed
    assert "loop condition" in reply.message
    assert reply.as_chat_text()


def test_empty_reply_is_handled() -> None:
    reply = parse_tutor_response("   ")
    assert reply.unparsed
    assert not reply.reveals_solution


def test_omitted_fields_become_none() -> None:
    reply = parse_tutor_response("EXPLANATION: only this")
    assert reply.misconception is None
    assert reply.question is None
    assert reply.solution is None
    assert reply.action == "none"


def test_case_insensitive_tags() -> None:
    reply = parse_tutor_response("explanation: lower case\nquestion: lower too")
    assert reply.message == "lower case"
    assert reply.question == "lower too"


def test_question_without_answer_is_kept() -> None:
    reply = parse_tutor_response("QUESTION: What does 5 / 2 evaluate to?")
    assert reply.question is not None
    assert "5 / 2" in reply.question


def test_as_chat_text_includes_solution() -> None:
    reply = parse_tutor_response("EXPLANATION: x\nSOLUTION: code here")
    rendered = reply.as_chat_text()
    assert "x" in rendered
    assert "code here" in rendered
    assert "Worked solution" in rendered


# ----------------------------------------------------------------------
# Service integration with a fake provider
# ----------------------------------------------------------------------
def test_service_uses_the_fake_provider_and_parses() -> None:
    provider = FakeProvider(
        reply="EXPLANATION: use a double\nQUESTION: what if both are double?"
    )
    service = TutorService(provider=provider, level="guided")
    context = TutorContext(code="int a = 5; int b = 2; auto c = a / b;")
    reply = service.ask(context)

    assert reply.action == "none"
    assert reply.question is not None
    assert service.last_request_sent is True
    assert len(provider.requests) == 1
    assert provider.requests[0].system


def test_service_records_the_level_in_the_request() -> None:
    provider = FakeProvider(reply="EXPLANATION: ok")
    service = TutorService(provider=provider, level="hint")
    service.ask(TutorContext())
    assert "ONE small clue" in provider.requests[0].system


def test_set_level_normalises() -> None:
    service = TutorService(provider=FakeProvider(), level="bogus")
    assert service.set_level("FULL") == "full"
    assert service.set_level("nope") == "guided"


def test_provider_errors_propagate() -> None:
    provider = FakeProvider(error=ProviderNotConfigured("no key"))
    service = TutorService(provider=provider)
    try:
        service.ask(TutorContext())
    except ProviderNotConfigured as exc:
        assert "no key" in str(exc)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("expected ProviderNotConfigured")


def test_code_is_included_in_the_prompt_not_hidden() -> None:
    """Guard against a regression that drops the learner's code."""
    provider = FakeProvider(reply="EXPLANATION: ok")
    TutorService(provider=provider).ask(
        TutorContext(code='std::cout << "marker-string-42";')
    )
    assert "marker-string-42" in provider.requests[0].user