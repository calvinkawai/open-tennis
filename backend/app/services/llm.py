import json
from collections.abc import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import Settings, get_settings
from app.schemas.plans import GeneratedTrainingPlan
from app.services.vector import RetrievedContext


SYSTEM_PROMPT = """You are a tennis training coach for a RAG application.
Use only the retrieved source material as the technical basis for the answer.
Do not invent unsupported technical advice.
Write practical guidance for an amateur player."""


class LLMService:
    """Generates structured training plans with Gemini."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model: ChatGoogleGenerativeAI | None = None

    @property
    def model(self) -> ChatGoogleGenerativeAI:
        if self._model is None:
            self._model = ChatGoogleGenerativeAI(
                model=self.settings.gemini_model,
                google_api_key=self.settings.google_genai_api_key,
                temperature=0.3,
            )
        return self._model

    def generate_training_plan(
        self,
        query: str,
        contexts: Sequence[RetrievedContext],
    ) -> GeneratedTrainingPlan:
        if not query.strip():
            raise ValueError("Query cannot be empty.")

        structured_model = self.model.with_structured_output(GeneratedTrainingPlan)
        response = structured_model.invoke(
            [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=self._build_user_prompt(query, contexts)),
            ]
        )
        if not isinstance(response, GeneratedTrainingPlan):
            return GeneratedTrainingPlan.model_validate(response)
        return response

    def _build_user_prompt(
        self,
        query: str,
        contexts: Sequence[RetrievedContext],
    ) -> str:
        prompt_input = {
            "user_query": query.strip(),
            "retrieved_technical_context": [
                self._format_retrieved_context(index, context)
                for index, context in enumerate(contexts, start=1)
            ],
        }

        return f"""You will receive a tennis training request and retrieved technical context from the tutorial knowledge base.

Input format:
{{
  "user_query": "<the user's tennis training question, weakness, or goal>",
  "retrieved_technical_context": [
    {{
      "source_index": 1,
      "chunk_type": "technical_detail or segment",
      "tutorial_topic": "<tutorial topic>",
      "segment_title": "<segment title, if applicable>",
      "technical_detail": "<technical principles when chunk_type is technical_detail>",
      "segments": "<relevant segment explanation when chunk_type is segment>",
      "key_coaching_cues": ["<short coaching cue>", "..."],
      "visual_focus": ["<what the player should observe or feel>", "..."]
    }}
  ]
}}

Input:
{json.dumps(prompt_input, ensure_ascii=False, indent=2)}

Task:
Create a tennis training plan that directly answers user_query using only retrieved_technical_context.

Output rules:
- Return one JSON-compatible object.
- Do not wrap the output in markdown code fences.
- Use the retrieved technical context as the source of truth.
- Do not invent unsupported technical advice.
- Keep the language practical and easy for an amateur player to follow.
- raw_ai_content must be bullet-point text.
- raw_ai_content must not contain a drills section.
- Put drills only in the drills array.
- Each drill should be specific, actionable, and connected to the retrieved technical context.
- If video_url is unknown, use null.

Output JSON shape:
{{
  "title": "<training plan title>",
  "focus_area": "<main technique focus area>",
  "raw_ai_content": "<bullet-point training plan text; no drills>",
  "drills": [
    {{
      "name": "<drill name>",
      "description": "<descriptive, ultra-concise one-sentence drill instruction>",
      "video_url": "<url> or null"
    }}
  ]
}}
"""

    def _format_retrieved_context(
        self,
        index: int,
        context: RetrievedContext,
    ) -> dict:
        chunk_type = context.chunk_type or "unknown"
        return {
            "source_index": index,
            "chunk_type": chunk_type,
            "tutorial_topic": context.tutorial_title or "",
            "segment_title": context.segment_title or "",
            "technical_detail": (
                context.content if chunk_type == "technical_detail" else ""
            ),
            "segments": context.content if chunk_type == "segment" else "",
            "key_coaching_cues": _optional_list(context.key_coaching_cue),
            "visual_focus": _optional_list(context.visual_focus),
        }


def _optional_list(value: str | None) -> list[str]:
    return [value] if value else []
