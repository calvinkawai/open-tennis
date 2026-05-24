from app.services.reflection import (
    ConversationMessage,
    ReflectionService,
    ReflectionStep,
    build_user_prompt,
)
from app.services.vector import RetrievedContext


def _draft_summary() -> str:
    return "Player likely benefits from a windshield-wiper finish drill."


def _ask_step(question: str, gap: str = "skill level") -> ReflectionStep:
    return ReflectionStep(
        internal_draft_summary=_draft_summary(),
        biggest_gap=gap,
        action="ask",
        question=question,
    )


def test_force_generate_overrides_invoker_when_invoker_still_asks():
    """On the final allowed turn, the result must be 'generate' even if the
    underlying invoker (LLM) tries to ask another question."""

    captured_prompts: list[str] = []

    def stubborn_invoker(system_prompt, user_prompt):
        captured_prompts.append(user_prompt)
        return _ask_step("What is your NTRP level?")

    service = ReflectionService(invoker=stubborn_invoker)
    result = service.next_step(
        history=[ConversationMessage(role="user", content="My forehand is weak")],
        light_contexts=[],
        turn_count=3,
        max_turns=4,
    )

    assert result.action == "generate"
    assert result.question is None
    assert "MUST set action='generate'" in captured_prompts[0]


def test_returns_invoker_question_when_not_forced():
    """When force_generate is False, an 'ask' result is passed through."""

    expected_question = "Does the ball sail long or land short?"

    def asking_invoker(system_prompt, user_prompt):
        assert "MUST set action='generate'" not in user_prompt
        return _ask_step(expected_question, gap="symptom direction")

    service = ReflectionService(invoker=asking_invoker)
    result = service.next_step(
        history=[ConversationMessage(role="user", content="My forehand is weak")],
        light_contexts=[],
        turn_count=0,
        max_turns=4,
    )

    assert result.action == "ask"
    assert result.question == expected_question


def test_empty_question_is_treated_as_generate():
    """If the LLM returns action='ask' but the question is blank, fall back
    to generate so we don't ask the user a non-question."""

    def blank_question_invoker(system_prompt, user_prompt):
        return _ask_step("   ", gap="practice context")

    service = ReflectionService(invoker=blank_question_invoker)
    result = service.next_step(
        history=[ConversationMessage(role="user", content="My forehand is weak")],
        light_contexts=[],
        turn_count=1,
        max_turns=4,
    )

    assert result.action == "generate"
    assert result.question is None


def test_repeated_question_triggers_retry_then_accepts_fresh_question():
    """If the LLM repeats a prior assistant question, retry once. If the retry
    returns a fresh question, use it. The retry prompt must include the
    repetition hint."""

    repeated = "Does the ball sail long or land short?"
    fresh = "How many years have you been playing?"
    prompts: list[str] = []

    def flaky_invoker(system_prompt, user_prompt):
        prompts.append(user_prompt)
        if len(prompts) == 1:
            return _ask_step(repeated, gap="symptom direction")
        return _ask_step(fresh, gap="experience")

    service = ReflectionService(invoker=flaky_invoker)
    result = service.next_step(
        history=[
            ConversationMessage(role="user", content="My forehand is weak"),
            ConversationMessage(role="assistant", content=repeated),
            ConversationMessage(role="user", content="It sails long"),
        ],
        light_contexts=[],
        turn_count=1,
        max_turns=4,
    )

    assert len(prompts) == 2, "should have retried exactly once"
    assert "repeated a question" in prompts[1], "retry prompt must include repetition hint"
    assert "repeated a question" not in prompts[0]
    assert result.action == "ask"
    assert result.question == fresh


def test_repeated_question_twice_falls_back_to_generate():
    """If the LLM still repeats after the retry, fall back to generate."""

    repeated = "Does the ball sail long or land short?"
    calls = {"count": 0}

    def stubborn_repeater(system_prompt, user_prompt):
        calls["count"] += 1
        return _ask_step(repeated, gap="symptom direction")

    service = ReflectionService(invoker=stubborn_repeater)
    result = service.next_step(
        history=[
            ConversationMessage(role="user", content="My forehand is weak"),
            ConversationMessage(role="assistant", content=repeated),
            ConversationMessage(role="user", content="It sails long"),
        ],
        light_contexts=[],
        turn_count=1,
        max_turns=4,
    )

    assert calls["count"] == 2, "should have retried exactly once before falling back"
    assert result.action == "generate"
    assert result.question is None


def test_invoker_exception_falls_back_to_generate():
    """If the structured-output invoker raises, fall back to generate."""

    def broken_invoker(system_prompt, user_prompt):
        raise RuntimeError("structured output parse failed")

    service = ReflectionService(invoker=broken_invoker)
    result = service.next_step(
        history=[ConversationMessage(role="user", content="My forehand is weak")],
        light_contexts=[],
        turn_count=0,
        max_turns=4,
    )

    assert result.action == "generate"
    assert result.question is None


def test_user_prompt_includes_history_light_contexts_and_budget():
    """The assembled user prompt must include the conversation transcript,
    light retrieved context, and a turn-budget line for the LLM."""

    history = [
        ConversationMessage(role="user", content="My forehand is weak"),
        ConversationMessage(role="assistant", content="Sails long or short?"),
        ConversationMessage(role="user", content="Sails long under pressure"),
    ]
    contexts = [
        RetrievedContext(
            content="Windshield-wiper finish gives topspin and lifts the ball.",
            source="tutorial://forehand-topspin",
            tutorial_title="Forehand Topspin",
            chunk_type="segment",
            segment_title="Windshield Wiper",
        ),
    ]

    prompt = build_user_prompt(
        history=history,
        light_contexts=contexts,
        turn_count=1,
        max_turns=4,
        force_generate=False,
    )

    assert "My forehand is weak" in prompt
    assert "Sails long under pressure" in prompt
    assert "[user]" in prompt and "[assistant]" in prompt
    assert "Windshield-wiper finish" in prompt
    assert "Forehand Topspin" in prompt or "Windshield Wiper" in prompt
    assert "1 of 3 questions used" in prompt
    assert "2 remaining" in prompt
    assert "MUST set action='generate'" not in prompt
    assert "repeated a question" not in prompt
    assert "Output your ReflectionStep now." in prompt
