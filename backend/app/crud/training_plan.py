from typing import List, Optional, cast

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import InstrumentedAttribute, selectinload
from sqlmodel import Session, select

from app.models.models import Drill, TrainingPlan

# SQLModel types instance relationships as lists; class access is an ORM descriptor.
PLAN_DRILLS = cast(InstrumentedAttribute[list[Drill]], TrainingPlan.drills)


def get_plan(db: Session, plan_id: int) -> Optional[TrainingPlan]:
    """Retrieve a single training plan by its ID."""
    statement = (
        select(TrainingPlan)
        .where(TrainingPlan.id == plan_id)
        .options(selectinload(PLAN_DRILLS))
    )
    return db.exec(statement).first()


def get_plans(db: Session, skip: int = 0, limit: int = 100) -> List[TrainingPlan]:
    """Retrieve all plans for a specific user with pagination."""
    statement = (
        select(TrainingPlan)
        .options(selectinload(PLAN_DRILLS))
        .offset(skip)
        .limit(limit)
    )
    return list(db.exec(statement).all())


def create_plan(db: Session, plan_obj: TrainingPlan) -> TrainingPlan:
    """Save a new LLM-generated plan to the database."""
    db.add(plan_obj)
    try:
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        raise
    db.refresh(plan_obj)
    return plan_obj


def update_plan(db: Session, plan_id: int, update_data: dict) -> Optional[TrainingPlan]:
    """
    Fetch a plan and apply user updates.
    Logic: Uses .dict(exclude_unset=True) from the schema to only update changed fields.
    """
    db_plan = db.get(TrainingPlan, plan_id)
    if not db_plan:
        return None

    for key, value in update_data.items():
        setattr(db_plan, key, value)

    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan
