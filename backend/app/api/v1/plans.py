from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from app.db.session import get_session
from app.schemas.plans import PlanCreate, TrainingPlanRead
from app.services.generation import PlanGenerationService
from app.api.v1.workspace import Workspace

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
        return TrainingPlanRead.model_validate(
            generation_service.create_plan(db, payload.query)
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The plan request or model output failed validation.",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Plan generation is unavailable; check server configuration.",
        ) from exc


@router.get("", response_model=list[TrainingPlanRead])
def list_training_plans(
    workspace: Workspace,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=100),
) -> list[TrainingPlanRead]:
    return workspace.list_plans(skip, limit)


@router.get("/{plan_id}", response_model=TrainingPlanRead)
def get_training_plan(
    plan_id: int,
    workspace: Workspace,
) -> TrainingPlanRead:
    return workspace.get_plan(plan_id)
