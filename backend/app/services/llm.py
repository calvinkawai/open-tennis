import json
from collections.abc import Sequence

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import Settings, get_settings
from app.schemas.plans import GeneratedTrainingPlan
from app.services.vector import RetrievedContext


SYSTEM_PROMPT = """You are a professional tennis coach and technical diagnostician.
You help amateur players understand the likely cause of their problem, then give
them a simple correction plan they can use in the next practice session.
Use the retrieved technical context as the only technical authority.
Do not invent unsupported advice.
Do not over-explain.
Answer in the same language as user_query."""


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
Create a concise diagnostic training plan using only retrieved_technical_context.

Think like this before writing the answer:
1. What visible problem or goal did the player describe?
2. What is the most likely technical cause supported by retrieved_technical_context?
3. What is the simplest correction cue?
4. Which drills will help the player feel and measure the correction?

Personalization rules:
- Use details in user_query to adjust the focus, difficulty, drill dose, and cue wording.
- Extract any available signal: stroke, weakness, goal, level, pain point, match situation, time limit, or recent mistake.
- Do not invent personal facts.
- If the user's level is missing, assume an amateur/intermediate player and keep drills safe and simple.
- If retrieved_technical_context is limited, say so briefly in raw_ai_content and stay conservative.
- Do not ask follow-up questions; produce the best useful plan from the available information.

Output rules:
- Return one JSON-compatible object.
- Do not wrap the output in markdown code fences.
- Answer in the same language as user_query.
- Use the retrieved technical context as the source of truth.
- Do not invent unsupported technical advice.
- Keep the language practical and easy for an amateur player to follow.
- raw_ai_content must be bullet-point text with 4-6 bullets.
- Each bullet must be ONE sentence, ≤25 words, no filler words ("really", "essentially", "basically", "in order to").
- raw_ai_content must not contain a drills section. Put drills only in the drills array.
- raw_ai_content should cover: diagnosis, priority correction, feel cue, what to avoid, success check, and next progression.
- The drills array must include 3-5 progressive drills.
- Include a feel/shadow drill, a controlled ball drill, and a more realistic rally or point-play drill when supported by retrieved_technical_context.
- Each drill description must be ONE sentence, ≤30 words, covering setup, action, dose, and success target.
- If video_url is unknown, use null.

Style anchor (match this tone and length):
- Example bullet: "Diagnosis: your forehand sails long because contact is flat and the racket finishes low."
- Example drill: "Stand 4 feet from a wall; brush up low-to-high with self-fed balls for 30 reps; success: 8/10 land inside the service line."

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
