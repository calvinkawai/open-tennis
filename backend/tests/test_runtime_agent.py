from uuid import uuid4

from sqlmodel import SQLModel, create_engine

from app.core.config import Settings
from app.schemas.knowledge import EvidenceSection, JournalCreate, WikiPatch
from app.services.agent import RuntimeAgent
from app.services.wiki import WikiStore


def test_runtime_agent_compiles_a_submitted_note_through_bounded_context(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'agent.db'}")
    SQLModel.metadata.create_all(engine)
    store = WikiStore(engine)
    entry = store.submit_journal(JournalCreate(
        client_id=str(uuid4()), content="I rush on faster balls.",
    ))
    calls = []

    class Model:
        def generate(self, schema, task, payload):
            calls.append(payload)
            evidence = next(item for item in payload["evidence"] if item["kind"] == "journal")
            return WikiPatch(
                title="My timing",
                sections=[EvidenceSection(
                    kind="personal_observation", text="I reported rushing.",
                    citation_ids=[evidence["id"]],
                )],
                change_summary="Linked one original note.",
            )

    agent = RuntimeAgent(
        store,
        model=Model(),
        settings=Settings(_env_file=None, agent_enabled=True, allow_personal_model_context=True),
    )
    assert agent.run_once()
    run = store.get_run(entry.run_id)
    assert run.status == "succeeded"
    assert len(calls) == 1
    assert store.get_page(run.page_id).citations[0].id == f"journal:{entry.id}"
    assert not agent.run_once()
    engine.dispose()


def test_personal_cloud_permission_is_required_even_after_the_record_is_saved(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'permission.db'}")
    SQLModel.metadata.create_all(engine)
    store = WikiStore(engine)
    entry = store.submit_journal(JournalCreate(client_id=str(uuid4()), content="A private observation."))

    class ForbiddenModel:
        def generate(self, *args):
            raise AssertionError("Personal content must not leave without permission")

    agent = RuntimeAgent(
        store, Settings(_env_file=None, agent_enabled=True), model=ForbiddenModel()
    )
    assert agent.run_once()
    assert store.get_run(entry.run_id).error_code == "PERSONAL_CONTEXT_DISABLED"
    assert store.get_journal(entry.id).content == "A private observation."
    engine.dispose()
