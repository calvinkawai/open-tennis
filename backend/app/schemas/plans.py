from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.services.rendering import render_training_plan


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

    @computed_field
    @property
    def rendered_text(self) -> str:
        return render_training_plan(
            title=self.title,
            focus_area=self.focus_area,
            raw_ai_content=self.raw_ai_content,
            drills=self.drills,
        )
