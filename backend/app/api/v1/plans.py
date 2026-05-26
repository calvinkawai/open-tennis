from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.crud import training_plan as training_plan_crud
from app.db.session import get_session
from app.schemas.plans import PlanCreate, TrainingPlanRead
from app.services.generation import PlanGenerationService

router = APIRouter(prefix="/plans", tags=["plans"])


@lru_cache
def get_plan_generation_service() -> PlanGenerationService:
    return PlanGenerationService()


@router.post(
    "",
    response_model=TrainingPlanRead,
    status_code=status.HTTP_201_CREATED,
)
def create_training_plan(
    payload: PlanCreate,
    db: Session = Depends(get_session),
    generation_service: PlanGenerationService = Depends(get_plan_generation_service),
) -> TrainingPlanRead:
    try:
        return generation_service.create_plan(db, payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )


@router.get("", response_model=list[TrainingPlanRead])
def list_training_plans(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_session),
) -> list[TrainingPlanRead]:
    return training_plan_crud.get_plans(db, skip=skip, limit=limit)


@router.get("/{plan_id}", response_model=TrainingPlanRead)
def get_training_plan(
    plan_id: int,
    db: Session = Depends(get_session),
) -> TrainingPlanRead:
    plan = training_plan_crud.get_plan(db, plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training plan {plan_id} was not found.",
        )
    return plan
