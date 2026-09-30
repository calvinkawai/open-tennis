from dataclasses import dataclass, field
from typing import Optional

from app.schemas.plans import GeneratedDrill, GeneratedTrainingPlan
from app.services.conversation import ConversationService, ConversationState
from app.services.reflection import (
    ConversationMessage,
    ReflectionService,
    ReflectionStep,
)
from app.services.vector import RetrievedContext


def _plan() -> GeneratedTrainingPlan:
    return GeneratedTrainingPlan(
        title="Forehand topspin lift",
        focus_area="Forehand",
        raw_ai_content="- Diagnosis: hits low\n- Cue: brush up\n- Drill: shadow swings",
        drills=[
            GeneratedDrill(name="Shadow swing", description="50 reps low-to-high.", video_url=None),
            GeneratedDrill(name="Drop and lift", description="30 self-fed balls.", video_url=None),
            GeneratedDrill(name="Crosscourt rally", description="10-ball rally with topspin.", video_url=None),
        ],
    )


def _ask_step(question: str) -> ReflectionStep:
    return ReflectionStep(
        internal_draft_summary="Player needs topspin lift; insufficient signal on level.",
        biggest_gap="skill level",
        action="ask",
        question=question,
    )


def _generate_step() -> ReflectionStep:
    return ReflectionStep(
        internal_draft_summary="Player is a 3.5 with consistent forehand sails-long under pressure.",
        biggest_gap="none material",
        action="generate",
        question=None,
    )


def _context(title: str = "Forehand Topspin") -> RetrievedContext:
    return RetrievedContext(
        content="Windshield-wiper finish gives topspin and lifts the ball.",
        source=f"tutorial://{title.lower().replace(' ', '-')}",
        tutorial_title=title,
        chunk_type="segment",
        segment_title="Windshield Wiper",
    )


@dataclass
class StubVectorService:
    light_results: list[RetrievedContext]
    full_results: list[RetrievedContext]
    calls: list[tuple[str, int | None]] = field(default_factory=list)

    def search(self, query: str, k: Optional[int] = None) -> list[RetrievedContext]:
        self.calls.append((query, k))
        return self.full_results if k is None else self.light_results


@dataclass
class StubLLMService:
    plan: GeneratedTrainingPlan
    calls: list[tuple[str, int]] = field(default_factory=list)

    def generate_training_plan(self, query, contexts):
        self.calls.append((query, len(list(contexts))))
        return self.plan


def _scripted_reflection_service(steps: list[ReflectionStep]) -> ReflectionService:
    iterator = iter(steps)

    def invoker(system_prompt, user_prompt):
        return next(iterator)

    return ReflectionService(invoker=invoker)


def test_start_with_vague_query_asks_first_question():
    """A vague initial query should result in a needs_answer turn with the
    first clarifying question."""

    reflection = _scripted_reflection_service([_ask_step("What's your skill level?")])
    vector = StubVectorService(light_results=[_context()], full_results=[_context()])
    llm = StubLLMService(plan=_plan())

    service = ConversationService(
        reflection_service=reflection,
        vector_service=vector,
        llm_service=llm,
        max_turns=4,
        light_k=3,
    )

    state, result = service.start("My forehand is weak")

    assert result.status == "needs_answer"
    assert result.question == "What's your skill level?"
    assert result.question_number == 1
    assert result.max_questions == 3
    assert result.plan is None
    assert state.turn_count == 1
    assert state.status == "active"
    assert len(state.history) == 2
    assert state.history[0] == ConversationMessage(role="user", content="My forehand is weak")
    assert state.history[1].role == "assistant"
    assert state.history[1].content == "What's your skill level?"
    # Light retrieval at start used k=3 (not the default None for full retrieval)
    assert vector.calls == [("My forehand is weak", 3)]
    # No final plan generation yet
    assert llm.calls == []


def test_start_can_short_circuit_to_plan_when_query_is_detailed():
    """If the initial query is detailed enough that the LLM chooses 'generate'
    immediately, the conversation completes in one server step."""

    reflection = _scripted_reflection_service([_generate_step()])
    vector = StubVectorService(
        light_results=[_context("Light")],
        full_results=[_context("Full A"), _context("Full B")],
    )
    plan = _plan()
    llm = StubLLMService(plan=plan)

    service = ConversationService(
        reflection_service=reflection,
        vector_service=vector,
        llm_service=llm,
        max_turns=4,
        light_k=3,
    )

    detailed_query = (
        "I'm a 3.5 NTRP player. My forehand sails long under pressure in "
        "third-set tiebreaks. I have 2 practice sessions per week with a partner."
    )
    state, result = service.start(detailed_query)

    assert result.status == "plan_ready"
    assert result.plan is plan
    assert result.question is None
    assert state.status == "completed"
    # Two retrieval calls: light(k=3) and full(k=None).
    assert len(vector.calls) == 2
    assert vector.calls[0] == (detailed_query, 3)
    assert vector.calls[1][1] is None
    # LLM was called with an enriched query and the full retrieval result.
    assert len(llm.calls) == 1
    enriched_query, context_count = llm.calls[0]
    assert "Initial goal:" in enriched_query
    assert detailed_query in enriched_query
    assert context_count == 2


def test_reply_loop_then_generate_uses_enriched_query():
    """After the user replies to the first question, the LLM generates and
    the enriched query passed to plan generation includes both the initial
    query and the Q&A from the conversation."""

    reflection = _scripted_reflection_service([
        _ask_step("Does it sail long or land short?"),
        _generate_step(),
    ])
    vector = StubVectorService(
        light_results=[_context("Light")],
        full_results=[_context("Full")],
    )
    llm = StubLLMService(plan=_plan())

    service = ConversationService(
        reflection_service=reflection,
        vector_service=vector,
        llm_service=llm,
        max_turns=4,
        light_k=3,
    )

    state, first = service.start("My forehand is weak")
    assert first.status == "needs_answer"

    state, second = service.reply(state, "It sails long, especially under pressure")

    assert second.status == "plan_ready"
    assert second.plan is not None
    assert state.status == "completed"

    enriched_query, _ = llm.calls[0]
    assert "Initial goal: My forehand is weak" in enriched_query
    assert "Does it sail long or land short?" in enriched_query
    assert "It sails long, especially under pressure" in enriched_query


def test_turn_cap_forces_generate_on_last_reflection_step():
    """When max_turns is exhausted by clarifying questions, the next step
    must produce a plan even if the underlying invoker scripted another ask."""

    # Script asks for all 4 reflection steps. The 4th one should be coerced to
    # generate by ReflectionService's force-generate guardrail.
    reflection = _scripted_reflection_service([
        _ask_step("Q1?"),
        _ask_step("Q2?"),
        _ask_step("Q3?"),
        _ask_step("Q4?"),
    ])
    vector = StubVectorService(
        light_results=[_context("Light")],
        full_results=[_context("Full")],
    )
    llm = StubLLMService(plan=_plan())

    service = ConversationService(
        reflection_service=reflection,
        vector_service=vector,
        llm_service=llm,
        max_turns=4,
        light_k=3,
    )

    state, _ = service.start("forehand weak")
    state, _ = service.reply(state, "sails long")
    state, _ = service.reply(state, "3.5 NTRP")
    state, final = service.reply(state, "twice a week")

    assert final.status == "plan_ready"
    assert final.plan is not None
    assert state.status == "completed"
    assert state.turn_count == 3, "exactly 3 clarifying questions were asked"


def test_reply_on_completed_conversation_raises():
    """Once the conversation is completed, further replies are rejected."""

    reflection = _scripted_reflection_service([_generate_step()])
    vector = StubVectorService(light_results=[_context()], full_results=[_context()])
    llm = StubLLMService(plan=_plan())

    service = ConversationService(
        reflection_service=reflection,
        vector_service=vector,
        llm_service=llm,
        max_turns=4,
        light_k=3,
    )

    state, _ = service.start("detailed enough")
    assert state.status == "completed"

    import pytest
    with pytest.raises(ValueError):
        service.reply(state, "another reply")
