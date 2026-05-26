from dataclasses import dataclass

from sqlmodel import Session

from app.crud import drill as drill_crud
from app.crud import training_plan as training_plan_crud
from app.models.models import Drill, TrainingPlan
from app.schemas.plans import GeneratedTrainingPlan
from app.services.llm import LLMService
from app.services.vector import RetrievedContext, VectorService


@dataclass(frozen=True)
class PlanPreview:
    plan: GeneratedTrainingPlan
    contexts: list[RetrievedContext]


class PlanGenerationService:
    """Coordinates retrieval, generation, and optional persistence."""

    def __init__(
        self,
        vector_service: VectorService | None = None,
        llm_service: LLMService | None = None,
    ) -> None:
        self.vector_service = vector_service or VectorService()
        self.llm_service = llm_service or LLMService()

    def preview_plan_with_context(self, query: str) -> PlanPreview:
        contexts = self.vector_service.search(query)
        plan = self.llm_service.generate_training_plan(query, contexts)
        return PlanPreview(plan=plan, contexts=contexts)

    def preview_plan(self, query: str) -> GeneratedTrainingPlan:
        return self.preview_plan_with_context(query).plan

    def create_plan(self, db: Session, query: str) -> TrainingPlan:
        generated_plan = self.preview_plan(query)
        plan = training_plan_crud.create_plan(
            db,
            TrainingPlan(
                title=generated_plan.title,
                focus_area=generated_plan.focus_area,
                raw_ai_content=generated_plan.raw_ai_content,
            ),
        )

        for generated_drill in generated_plan.drills:
            drill_crud.create_drill(
                db,
                Drill(
                    name=generated_drill.name,
                    description=generated_drill.description,
                    video_url=generated_drill.video_url,
                    training_plan_id=plan.id,
                ),
            )

        saved_plan = training_plan_crud.get_plan(db, plan.id)
        if saved_plan is None:
            raise RuntimeError(f"Created plan {plan.id} could not be reloaded.")
        return saved_plan
