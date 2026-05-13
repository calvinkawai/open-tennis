from typing import List, Optional

from sqlmodel import Session, select

from app.models.models import Drill


def get_drill(db: Session, drill_id: int) -> Optional[Drill]:
    """Retrieve a specific drill by its ID."""
    return db.get(Drill, drill_id)


def get_drills_by_plan(db: Session, training_plan_id: int) -> List[Drill]:
    """
    Fetch all drills associated with a specific training plan.
    Useful for rendering the full plan view in the frontend.
    """
    statement = select(Drill).where(Drill.training_plan_id == training_plan_id)
    return list(db.exec(statement).all())


def create_drill(db: Session, drill_obj: Drill) -> Drill:
    """
    Persist a new drill.
    This is typically called by the LLMService when decomposing
    the generated technical plan into individual components.
    """
    db.add(drill_obj)
    db.commit()
    db.refresh(drill_obj)
    return drill_obj
