from sqlmodel import SQLModel, create_engine
from uuid import uuid4

from app.cli.backup import backup_database
from app.schemas.knowledge import JournalCreate
from app.services.wiki import WikiStore


def test_backup_restores_original_records_into_a_separate_database(tmp_path):
    source = tmp_path / "source.db"
    engine = create_engine(f"sqlite:///{source}")
    SQLModel.metadata.create_all(engine)
    store = WikiStore(engine)
    entry = store.submit_journal(JournalCreate(client_id=str(uuid4()), content="My original observation."))
    destination = tmp_path / "restored.db"

    backup_database(source, destination)

    restored_engine = create_engine(f"sqlite:///{destination}")
    assert WikiStore(restored_engine).get_journal(entry.id).content == "My original observation."
    assert store.get_journal(entry.id).content == "My original observation."
    restored_engine.dispose()
    engine.dispose()
