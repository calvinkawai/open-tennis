from datetime import datetime
from typing import List, Optional

from sqlmodel import Field, Relationship, SQLModel


class TrainingPlan(SQLModel, table=True):
    """
    Represents a synthesized plan. Note the 'is_mutable' concept:
    The AI generates it, but the user owns and edits it.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    focus_area: str  # e.g., "Serve Toss", "Backhand Slice"

    # The technical content retrieved from the Vector Store
    raw_ai_content: str

    # The user-edited version of the plan
    edited_content: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Link to specific drill items
    drills: List["Drill"] = Relationship(back_populates="training_plan")


class Drill(SQLModel, table=True):
    """
    Individual components of a Training Plan.
    This allows users to edit reps/sets specifically.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    video_url: Optional[str] = None  # Metadata for YouTube iframes

    training_plan_id: int = Field(foreign_key="trainingplan.id")
    training_plan: TrainingPlan = Relationship(back_populates="drills")
