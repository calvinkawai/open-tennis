import pytest
from sqlmodel import SQLModel, create_engine
from uuid import uuid4
from types import SimpleNamespace

from app.core.errors import AppError
from app.schemas.knowledge import EvidenceSection, JournalCreate, WikiPatch
from app.services.wiki import WikiStore


@pytest.fixture
def store(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wiki.db'}")
    SQLModel.metadata.create_all(engine)
    yield WikiStore(engine)
    engine.dispose()


def tutorial(directory):
    directory.mkdir(exist_ok=True)
    (directory / "Forehand Space.md").write_text(
        """## 1. Video Summary
**Technical Detail:**
* Observe your contact space.

## 2. Segments
**Segment 1: Contact space**
Observe the space around the contact point.
* Key coaching cue: Make room
* Visual focus: Contact point
""",
        encoding="utf-8",
    )
    return directory


def test_technical_sources_require_owner_review_before_retrieval(store, tmp_path):
    path = tutorial(tmp_path / "tutorials")
    assert store.import_tutorials(path) == {"imported": 1, "unchanged": 0}
    page = store.list_pages("technical")[0]
    draft = store.get_page(page.id)
    assert draft.status == "draft"
    assert store.search_evidence("forehand contact", include_personal=False) == []

    published = store.approve(page.id, draft.version_id, expected_version=0)
    assert published.version == 1
    assert published.status == "published"
    evidence = store.search_evidence("forehand contact", include_personal=False)
    assert evidence
    assert all(item.kind == "technical" for item in evidence)
    assert "contact point" in store.get_evidence(evidence[0].id).content
    assert store.import_tutorials(path) == {"imported": 0, "unchanged": 1}


def test_confirmed_journal_is_immutable_idempotent_and_queues_personal_compilation(store):
    payload = JournalCreate(
        client_id=str(uuid4()), content="  I rushed when the ball came faster.  ",
        context="Fast rally", feeling="A clue, not a measured improvement.",
    )
    saved = store.submit_journal(payload)

    assert saved.content == payload.content
    assert saved.run_id is not None
    assert store.get_run(saved.run_id).status == "queued"
    assert store.submit_journal(payload).id == saved.id
    assert len(store.list_journal()) == 1
    assert store.list_pages("personal")[0].record_count == 1
    with pytest.raises(AppError) as error:
        store.submit_journal(payload.model_copy(update={"content": "Different original"}))
    assert error.value.status_code == 409
    assert store.get_journal(saved.id).content == payload.content


def test_personal_compilation_publishes_a_traceable_version_without_changing_the_record(store):
    entry = store.submit_journal(JournalCreate(
        client_id=str(uuid4()), content="Fast balls made me rush.",
    ))
    lease = store.claim_next_run()
    context = store.get_run_context(lease.run.id, lease.claim_token)
    note = next(item for item in context.evidence if item.kind == "journal")
    patch = WikiPatch(
        title="My timing observations",
        sections=[EvidenceSection(
            kind="personal_observation", text="I reported rushing on fast balls.",
            citation_ids=[note.id],
        )],
        change_summary="Linked the original timing observation.",
    )

    completed = store.complete_run(
        lease.run.id, lease.claim_token, patch, [item.id for item in context.evidence]
    )
    assert completed.status == "succeeded"
    page = store.get_page(completed.page_id)
    assert page.space == "personal"
    assert page.status == "published"
    assert page.version == 1
    assert page.citations[0].id == f"journal:{entry.id}"
    assert store.get_journal(entry.id).content == "Fast balls made me rush."


def test_chinese_query_retrieves_approved_forehand_evidence_without_personal_leakage(store, tmp_path):
    store.import_tutorials(tutorial(tmp_path / "tutorials"))
    page = store.list_pages("technical")[0]
    store.approve(page.id, store.get_page(page.id).version_id, 0)
    store.submit_journal(JournalCreate(
        client_id=str(uuid4()), content="我的正手在快球时容易着急。",
    ))

    results = store.search_evidence("我的正手击球点", include_personal=False)

    assert results
    assert all(item.kind == "technical" for item in results)


def personal_patch(context):
    note = next(item for item in context.evidence if item.kind == "journal")
    return WikiPatch(
        title="Personal observations",
        sections=[EvidenceSection(
            kind="personal_observation", text="An observation from my record.",
            citation_ids=[note.id],
        )],
        change_summary="Linked the record.",
    )


def test_owner_rollback_blocks_a_late_agent_write(store):
    store.submit_journal(JournalCreate(client_id=str(uuid4()), content="First observation."))
    first = store.claim_next_run()
    first_context = store.get_run_context(first.run.id, first.claim_token)
    completed = store.complete_run(
        first.run.id, first.claim_token, personal_patch(first_context),
        [item.id for item in first_context.evidence],
    )
    store.submit_journal(JournalCreate(
        client_id=str(uuid4()), page_id=completed.page_id, content="Second observation.",
    ))
    late = store.claim_next_run()
    late_context = store.get_run_context(late.run.id, late.claim_token)
    restored = store.rollback(completed.page_id, completed.result_version_id, expected_version=1)

    with pytest.raises(AppError) as error:
        store.complete_run(
            late.run.id, late.claim_token, personal_patch(late_context),
            [item.id for item in late_context.evidence],
        )

    assert error.value.code == "STALE_VERSION"
    assert store.get_page(completed.page_id).version == restored.version
    assert len(store.list_journal()) == 2


def test_technical_agent_proposal_never_self_approves(store, tmp_path):
    store.import_tutorials(tutorial(tmp_path / "tutorials"))
    page = store.list_pages("technical")[0]
    store.approve(page.id, store.get_page(page.id).version_id, 0)
    run = store.request_technical_proposal(page.id, "Reorganize the existing material.")
    lease = store.claim_next_run()
    context = store.get_run_context(run.id, lease.claim_token)
    source = context.evidence[0]
    patch = WikiPatch(
        title="Reorganized explanation",
        sections=[EvidenceSection(
            kind="source_supported", text="Contact space.", citation_ids=[source.id],
        )],
        change_summary="Proposal only.",
    )
    result = store.complete_run(run.id, lease.claim_token, patch, [source.id])
    assert result.status == "succeeded"
    assert store.get_page(page.id).version == 1
    draft = store.list_versions(page.id)[0]
    assert draft.status == "draft"
    assert store.get_page(page.id).has_draft
    approved = store.approve(page.id, draft.id, 1)
    assert approved.version == 2


def test_agent_cannot_invent_citations_or_relabel_a_personal_note_as_technical(store):
    store.submit_journal(JournalCreate(client_id=str(uuid4()), content="I felt rushed."))
    lease = store.claim_next_run()
    context = store.get_run_context(lease.run.id, lease.claim_token)
    note = context.evidence[0]
    patch = personal_patch(context)
    invented = patch.model_copy(update={"sections": [
        EvidenceSection(kind="personal_observation", text="Invented.", citation_ids=["unknown"])
    ]})
    with pytest.raises(AppError, match="citation"):
        store.complete_run(lease.run.id, lease.claim_token, invented, [note.id])
    relabeled = patch.model_copy(update={"sections": [
        EvidenceSection(kind="source_supported", text="A technique fact.", citation_ids=[note.id])
    ]})
    with pytest.raises(AppError) as error:
        store.complete_run(lease.run.id, lease.claim_token, relabeled, [note.id])
    assert error.value.code == "EVIDENCE_KIND_MISMATCH"
    assert store.get_page(lease.run.page_id).version == 0


def test_expired_claim_is_recoverable_but_the_old_worker_cannot_publish(store, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("app.services.wiki.time", SimpleNamespace(time=lambda: clock[0]))
    entry = store.submit_journal(JournalCreate(client_id=str(uuid4()), content="One original."))
    old = store.claim_next_run(lease_seconds=1)
    old_context = store.get_run_context(old.run.id, old.claim_token)
    clock[0] = 1002.0
    assert store.recover_expired_runs() == 1
    new = store.claim_next_run()
    assert new.run.id == old.run.id
    assert new.claim_token != old.claim_token
    with pytest.raises(AppError) as error:
        store.complete_run(
            old.run.id, old.claim_token, personal_patch(old_context),
            [item.id for item in old_context.evidence],
        )
    assert error.value.code == "RUN_LEASE_LOST"
    current = store.get_run_context(new.run.id, new.claim_token)
    store.complete_run(
        new.run.id, new.claim_token, personal_patch(current),
        [item.id for item in current.evidence],
    )
    assert store.get_run(entry.run_id).status == "succeeded"
    assert len(store.list_journal()) == 1
