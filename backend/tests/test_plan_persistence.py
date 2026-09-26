import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

from app.crud.training_plan import get_plans
from app.schemas.plans import GeneratedDrill, GeneratedTrainingPlan
from app.services.generation import PlanGenerationService


class EmptyRetrieval:
    def search(self, query):
        return []


class FixedPlan:
    def generate_training_plan(self, query, contexts):
        return GeneratedTrainingPlan(
            title="Observation",
            focus_area="Forehand",
            raw_ai_content="Observe one detail.",
            drills=[
                GeneratedDrill(name=f"Step {index}", description="An example step.")
                for index in range(3)
            ],
        )


def test_failed_drill_write_does_not_publish_a_partial_plan():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    insert_count = 0

    def reject_second_drill(conn, cursor, statement, parameters, context, executemany):
        nonlocal insert_count
        if statement.lstrip().upper().startswith("INSERT INTO DRILL "):
            insert_count += 1
            if insert_count == 2:
                raise OperationalError(statement, parameters, RuntimeError("write fault"))

    event.listen(engine, "before_cursor_execute", reject_second_drill)
    service = PlanGenerationService(
        vector_service=EmptyRetrieval(),
        llm_service=FixedPlan(),
    )
    with Session(engine) as session:
        with pytest.raises(OperationalError):
            service.create_plan(session, "Observe my forehand")
        assert get_plans(session) == []
    engine.dispose()
