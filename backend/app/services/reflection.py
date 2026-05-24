import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.services.vector import RetrievedContext


@dataclass(frozen=True)
class ConversationMessage:
    role: str
    content: str


class ReflectionStep(BaseModel):
    internal_draft_summary: str = Field(min_length=20)
    biggest_gap: str = Field(min_length=3)
    action: Literal["ask", "generate"]
    question: str | None = None


# Low-level boundary: production wires this to Gemini.with_structured_output.
# Tests stub it directly to script ReflectionStep outputs.
Invoker = Callable[[str, str], ReflectionStep]

SYSTEM_PROMPT = """You are a tennis coaching diagnostician. Your job is to gather just enough context to produce a personalized training plan in 4 or fewer turns.

For each turn:
1. Silently draft a tentative training plan from the conversation so far, anchored in the retrieved technical context.
2. Identify the SINGLE most impactful gap — a detail that, if known, would substantially change your draft. Examples: severity (sails long vs. lands short), skill level, frequency (always vs. only under pressure), practice context (court access, partner, wall, ball machine), time budget, recent attempted fix, physical limit or injury.
3. Decide: is the current draft already specific and well-supported by the retrieved context? If yes, set action="generate". Otherwise, action="ask".
4. If asking, produce ONE question that:
   - is plainly worded for an amateur player (no jargon unless the user used it)
   - can be answered in one sentence
   - targets the highest-impact gap, not the next obvious one
   - is NOT a repeat of anything already in the conversation
   - is NOT a yes/no question unless yes/no genuinely changes the plan

Output a ReflectionStep object with internal_draft_summary, biggest_gap, action, and question (required when action="ask")."""

_RETRY_HINT_REPETITION = (
    "Your previous output repeated a question already asked in this conversation. "
    "Ask a different question that targets a different gap, or set action='generate'."
)

_FORCE_GENERATE_CLAUSE = (
    "This is your final turn. You MUST set action='generate'. "
    "Do not ask another question even if the conversation is incomplete."
)

_PUNCT_RE = re.compile(r"[^\w\s]")


def _normalize(text: str) -> str:
    lowered = _PUNCT_RE.sub(" ", text.lower())
    return " ".join(lowered.split())


def _prior_assistant_normals(history: Sequence[ConversationMessage]) -> set[str]:
    return {
        _normalize(message.content)
        for message in history
        if message.role == "assistant"
    }


def _coerce_to_generate(result: ReflectionStep) -> ReflectionStep:
    return result.model_copy(update={"action": "generate", "question": None})


def _fallback_generate(reason: str) -> ReflectionStep:
    return ReflectionStep(
        internal_draft_summary=(
            "Reflection unavailable; proceeding to generate with current context."
        ),
        biggest_gap=reason,
        action="generate",
        question=None,
    )


def _format_light_context(index: int, context: RetrievedContext) -> str:
    title = context.segment_title or context.tutorial_title or "Untitled chunk"
    chunk_type = context.chunk_type or "chunk"
    snippet = (context.content or "").strip().replace("\n", " ")
    if len(snippet) > 280:
        snippet = snippet[:277] + "..."
    return f"{index}. [{chunk_type}] {title}: {snippet}"


def build_user_prompt(
    history: Sequence[ConversationMessage],
    light_contexts: Sequence[RetrievedContext],
    turn_count: int,
    max_turns: int,
    force_generate: bool,
    retry_hint: str | None = None,
) -> str:
    """Assemble the per-turn user prompt for the reflection LLM call."""

    transcript_lines = [
        f"[{message.role}] {message.content}" for message in history
    ]
    transcript = "\n".join(transcript_lines) if transcript_lines else "(no messages yet)"

    if light_contexts:
        context_lines = [
            _format_light_context(index, context)
            for index, context in enumerate(light_contexts, start=1)
        ]
        context_block = "\n".join(context_lines)
    else:
        context_block = "(no retrieved context available)"

    # max_turns counts total reflection steps; the last is always "generate",
    # so clarifying-question capacity is max_turns - 1.
    questions_capacity = max(max_turns - 1, 0)
    questions_used = min(turn_count, questions_capacity)
    questions_remaining = max(questions_capacity - questions_used, 0)
    budget_line = (
        f"Turn budget: {questions_used} of {questions_capacity} questions used "
        f"({questions_remaining} remaining before forced generate)."
    )

    parts = [
        "Conversation so far:",
        transcript,
        "",
        "Retrieved technical context (light, top N):",
        context_block,
        "",
        budget_line,
    ]
    if force_generate:
        parts.extend(["", _FORCE_GENERATE_CLAUSE])
    if retry_hint:
        parts.extend(["", retry_hint])
    parts.extend(["", "Output your ReflectionStep now."])
    return "\n".join(parts)


class ReflectionService:
    """Gap-driven self-reflection for the clarifying conversation."""

    def __init__(self, invoker: Invoker | None = None) -> None:
        self._invoker = invoker

    def next_step(
        self,
        history: Sequence[ConversationMessage],
        light_contexts: Sequence[RetrievedContext],
        turn_count: int,
        max_turns: int,
    ) -> ReflectionStep:
        force_generate = turn_count >= max_turns - 1
        history_list = list(history)
        light_list = list(light_contexts)
        prior_questions_norm = _prior_assistant_normals(history_list)

        user_prompt = build_user_prompt(
            history_list, light_list, turn_count, max_turns, force_generate
        )
        result = self._safe_invoke(user_prompt)
        if result is None:
            return _fallback_generate("invoker raised; falling back to generate")
        result = self._apply_guardrails(result, force_generate)
        if result.action != "ask":
            return result

        if _normalize(result.question or "") in prior_questions_norm:
            retry_prompt = build_user_prompt(
                history_list,
                light_list,
                turn_count,
                max_turns,
                force_generate,
                retry_hint=_RETRY_HINT_REPETITION,
            )
            retry_result = self._safe_invoke(retry_prompt)
            if retry_result is None:
                return _fallback_generate("retry invoker raised; falling back to generate")
            retry_result = self._apply_guardrails(retry_result, force_generate)
            if retry_result.action != "ask":
                return retry_result
            if _normalize(retry_result.question or "") in prior_questions_norm:
                return _coerce_to_generate(retry_result)
            return retry_result

        return result

    def _safe_invoke(self, user_prompt: str) -> ReflectionStep | None:
        try:
            return self._invoker(SYSTEM_PROMPT, user_prompt)
        except Exception:
            return None

    @staticmethod
    def _apply_guardrails(result: ReflectionStep, force_generate: bool) -> ReflectionStep:
        if force_generate and result.action != "generate":
            return _coerce_to_generate(result)
        if result.action == "ask" and not (result.question or "").strip():
            return _coerce_to_generate(result)
        return result


def build_gemini_reflection_invoker(settings: Settings | None = None) -> Invoker:
    """Wire a real Gemini call as a ReflectionService invoker."""

    settings = settings or get_settings()
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_genai_api_key,
        temperature=0.3,
    )
    structured = model.with_structured_output(ReflectionStep)

    def _invoke(system_prompt: str, user_prompt: str) -> ReflectionStep:
        response = structured.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        if isinstance(response, ReflectionStep):
            return response
        return ReflectionStep.model_validate(response)

    return _invoke
