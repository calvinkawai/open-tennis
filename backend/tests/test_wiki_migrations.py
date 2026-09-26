from sqlalchemy import inspect
from sqlmodel import Session, create_engine

from app.db.migrations import initialize_database
from app.models.models import Drill, TrainingPlan


def test_existing_unversioned_plans_survive_idempotent_wiki_migration(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    TrainingPlan.__table__.create(engine)
    Drill.__table__.create(engine)
    with Session(engine) as db:
        db.add(TrainingPlan(
            title="Existing plan", focus_area="Forehand", raw_ai_content="Original advice"
        ))
        db.commit()

    initialize_database(engine)
    initialize_database(engine)

    assert {"wikipage", "wikiversion", "journalentry", "agentrun"} <= set(inspect(engine).get_table_names())
    with Session(engine) as db:
        assert db.get(TrainingPlan, 1).raw_ai_content == "Original advice"
    engine.dispose()
