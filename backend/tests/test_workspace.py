from uuid import uuid4

from sqlmodel import SQLModel, create_engine

from app.core.config import Settings
from app.schemas.knowledge import EvidenceSection, JournalCreate
from app.services.wiki import WikiStore
from app.services.workspace import WorkspaceService


def test_answer_uses_raw_personal_evidence_and_labels_it_separately(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'workspace.db'}")
    SQLModel.metadata.create_all(engine)
    store = WikiStore(engine)
    entry = store.submit_journal(JournalCreate(
        client_id=str(uuid4()), content="My forehand rushes on fast balls.",
    ))

    class Model:
        def generate(self, schema, task, payload):
            note = next(item for item in payload["evidence"] if item["kind"] == "journal")
            return schema(sections=[EvidenceSection(
                kind="personal_observation", text="You reported rushing on fast balls.",
                citation_ids=[note["id"]],
            )])

    service = WorkspaceService(
        store,
        Settings(_env_file=None, agent_enabled=True, allow_personal_model_context=True),
        model=Model(),
    )
    answer = service.ask("My forehand", include_personal=True)

    assert answer.sections[0].kind == "personal_observation"
    assert answer.citations[0].id == f"journal:{entry.id}"
    assert "technical" not in {item.kind for item in answer.citations}
    assert store.get_run(answer.run_id).status == "succeeded"
    engine.dispose()


def test_plan_preview_is_canonical_and_adoption_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'plans.db'}")
    SQLModel.metadata.create_all(engine)
    store = WikiStore(engine)

    class Model:
        def generate(self, schema, task, payload):
            return schema(
                title="One focus", focus_area="Forehand", raw_ai_content="Model suggestion",
                drills=[
                    {"name": f"Step {i}", "description": "Example only.", "video_url": None}
                    for i in range(3)
                ],
                sections=[EvidenceSection(kind="model_supplement", text="No technical sources were found.")],
            )

    service = WorkspaceService(store, Settings(_env_file=None, agent_enabled=True), model=Model())
    preview = service.preview("A forehand practice")
    assert service.list_plans() == []
    first = service.adopt(preview.preview_id, None)
    second = service.adopt(preview.preview_id, None)

    assert first.id == second.id
    assert len(first.drills) == 3
    assert len(service.list_plans()) == 1
    assert first.sections[0].kind == "model_supplement"
    engine.dispose()


def test_pain_request_does_not_invoke_a_training_model(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'health.db'}")
    SQLModel.metadata.create_all(engine)
    store = WikiStore(engine)

    class ForbiddenModel:
        def generate(self, *args):
            raise AssertionError("Health boundary must not call the model")

    service = WorkspaceService(store, Settings(_env_file=None), model=ForbiddenModel())
    answer = service.ask("My wrist hurts after practice")
    assert answer.warning
    assert answer.citations == []
    assert "医疗" in answer.sections[0].text
    engine.dispose()
