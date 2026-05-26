from dataclasses import dataclass, field, replace
from typing import Optional

from app.schemas.plans import GeneratedTrainingPlan
from app.services.llm import LLMService
from app.services.reflection import (
    ConversationMessage,
    ReflectionService,
    build_gemini_reflection_invoker,
)
from app.services.vector import RetrievedContext, VectorService


@dataclass
class ConversationState:
    initial_query: str
    history: list[ConversationMessage] = field(default_factory=list)
    light_contexts: list[RetrievedContext] = field(default_factory=list)
    turn_count: int = 0
    status: str = "active"


@dataclass
class TurnResult:
    status: str  # "needs_answer" | "plan_ready"
    question: Optional[str] = None
    plan: Optional[GeneratedTrainingPlan] = None
    question_number: Optional[int] = None
    max_questions: Optional[int] = None


class ConversationService:
    """In-memory orchestrator for the gap-driven clarifying conversation."""

    def __init__(
        self,
        reflection_service: ReflectionService | None = None,
        vector_service: VectorService | None = None,
        llm_service: LLMService | None = None,
        max_turns: int = 4,
        light_k: int = 3,
    ) -> None:
        self.vector_service = vector_service or VectorService()
        self.llm_service = llm_service or LLMService()
        self.reflection_service = reflection_service or ReflectionService(
            invoker=build_gemini_reflection_invoker()
        )
        self.max_turns = max_turns
        self.light_k = light_k

    def start(self, initial_query: str) -> tuple[ConversationState, TurnResult]:
        if not initial_query.strip():
            raise ValueError("Initial query cannot be empty.")
        light_contexts = list(
            self.vector_service.search(initial_query, k=self.light_k)
        )
        state = ConversationState(
            initial_query=initial_query.strip(),
            history=[ConversationMessage(role="user", content=initial_query.strip())],
            light_contexts=light_contexts,
            turn_count=0,
        )
        return self._advance(state)

    def reply(
        self, state: ConversationState, user_reply: str
    ) -> tuple[ConversationState, TurnResult]:
        if state.status != "active":
            raise ValueError("Conversation is not active; cannot reply.")
        if not user_reply.strip():
            raise ValueError("Reply cannot be empty.")
        new_history = state.history + [
            ConversationMessage(role="user", content=user_reply.strip())
        ]
        new_state = replace(state, history=new_history)
        return self._advance(new_state)

    def _advance(
        self, state: ConversationState
    ) -> tuple[ConversationState, TurnResult]:
        step = self.reflection_service.next_step(
            history=state.history,
            light_contexts=state.light_contexts,
            turn_count=state.turn_count,
            max_turns=self.max_turns,
        )
        if step.action == "ask":
            question = step.question or ""
            new_history = state.history + [
                ConversationMessage(role="assistant", content=question)
            ]
            new_state = replace(
                state,
                history=new_history,
                turn_count=state.turn_count + 1,
            )
            return new_state, TurnResult(
                status="needs_answer",
                question=question,
                question_number=new_state.turn_count,
                max_questions=self.max_turns - 1,
            )

        enriched_query = self._build_enriched_query(state)
        full_contexts = list(self.vector_service.search(enriched_query))
        plan = self.llm_service.generate_training_plan(enriched_query, full_contexts)
        new_state = replace(state, status="completed")
        return new_state, TurnResult(status="plan_ready", plan=plan)

    @staticmethod
    def _build_enriched_query(state: ConversationState) -> str:
        lines = [f"Initial goal: {state.initial_query}"]
        question: Optional[str] = None
        clarifications: list[str] = []
        # Pair each assistant question with the user's next reply.
        for message in state.history[1:]:
            if message.role == "assistant":
                question = message.content
            elif message.role == "user" and question is not None:
                clarifications.append(f"- Q: {question} A: {message.content}")
                question = None
        if clarifications:
            lines.append("Clarifications:")
            lines.extend(clarifications)
        return "\n".join(lines)
