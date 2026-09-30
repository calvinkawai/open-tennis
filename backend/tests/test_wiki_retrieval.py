from uuid import uuid4

from sqlmodel import SQLModel, create_engine

from app.core.config import Settings
from app.schemas.knowledge import JournalCreate
from app.services.retrieval import WikiRetriever
from app.services.wiki import WikiStore
from tests.test_wiki_store import tutorial


def test_semantic_index_excludes_unapproved_sources_and_unconsented_private_notes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'retrieval.db'}")
    SQLModel.metadata.create_all(engine)
    store = WikiStore(engine)
    store.import_tutorials(tutorial(tmp_path / "tutorials"))
    store.submit_journal(JournalCreate(client_id=str(uuid4()), content="A private original note."))
    embedded = []

    class Embeddings:
        def embed_documents(self, texts):
            embedded.extend(texts)
            return [[1.0, 0.0, 0.0] for _ in texts]

        def embed_query(self, text):
            return [1.0, 0.0, 0.0]

    retrieval = WikiRetriever(
        store, Settings(
            _env_file=None, semantic_index_enabled=True, wiki_index_path=tmp_path / "index",
            allow_personal_model_context=False,
        ), embeddings=Embeddings(),
    )
    retrieval.sync()
    assert embedded == []
    page = store.list_pages("technical")[0]
    store.approve(page.id, store.get_page(page.id).version_id, 0)
    retrieval.sync()

    assert embedded and not any("private original" in text for text in embedded)
    result = retrieval.search("contact space", include_personal=False)
    assert result.evidence and result.mode == "hybrid"
    assert all(item.kind == "technical" for item in result.evidence)
    assert store.get_page(page.id).index_status == "ready"
    engine.dispose()
