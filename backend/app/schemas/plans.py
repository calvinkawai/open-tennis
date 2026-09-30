from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.services.rendering import render_training_plan
from app.schemas.knowledge import Evidence, EvidenceSection, StrictModel


class PlanCreate(BaseModel):
    query: str = Field(min_length=3, max_length=1000)


class GeneratedDrill(BaseModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    video_url: str | None = None


class GeneratedTrainingPlan(BaseModel):
    title: str = Field(min_length=1)
    focus_area: str = Field(min_length=1)
    raw_ai_content: str = Field(min_length=1)
    drills: list[GeneratedDrill] = Field(min_length=3, max_length=5)


class DrillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str
    video_url: str | None = None
    training_plan_id: int


class TrainingPlanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    focus_area: str
    raw_ai_content: str
    edited_content: str | None = None
    created_at: datetime
    updated_at: datetime
    drills: list[DrillRead] = Field(default_factory=list)
    sections: list[EvidenceSection] = Field(default_factory=list)
    citations: list[Evidence] = Field(default_factory=list)
    wiki_page_id: str | None = None

    @computed_field
    @property
    def rendered_text(self) -> str:
        return render_training_plan(
            title=self.title,
            focus_area=self.focus_area,
            raw_ai_content=self.raw_ai_content,
            drills=self.drills,
        )


class GroundedPlanDraft(GeneratedTrainingPlan):
    model_config = ConfigDict(extra="forbid")
    sections: list[EvidenceSection] = Field(min_length=1, max_length=16)


class PlanPreviewRead(GroundedPlanDraft):
    preview_id: str
    citations: list[Evidence]
    warning: str | None = None
    run_id: str


class AdoptPlan(StrictModel):
    preview_id: str
    edited_content: str | None = Field(default=None, max_length=20000)


class DrillEdit(StrictModel):
    id: int = Field(gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=2000)


class PlanEdit(StrictModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    edited_content: str | None = Field(default=None, max_length=20000)
    drills: list[DrillEdit] | None = Field(default=None, max_length=5)
