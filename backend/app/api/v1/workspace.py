from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response

from app.schemas.knowledge import (
    AnswerRead, EvidenceDetail, JournalCreate, JournalRead, ProposalCreate,
    Question, RunRead, Space, VersionAction, WikiDetail, WikiSummary, WikiVersionRead,
)
from app.schemas.plans import AdoptPlan, PlanEdit, PlanPreviewRead, TrainingPlanRead
from app.services.wiki import WikiStore
from app.services.workspace import WorkspaceService

router = APIRouter()


def get_store(request: Request) -> WikiStore:
    return request.app.state.wiki_store


def get_workspace(request: Request) -> WorkspaceService:
    return request.app.state.workspace_service


Store = Annotated[WikiStore, Depends(get_store)]
Workspace = Annotated[WorkspaceService, Depends(get_workspace)]


@router.get("/status")
def status(request: Request, store: Store) -> dict[str, object]:
    settings = request.app.state.settings
    technical = store.list_pages("technical")
    return {
        "agent_enabled": settings.agent_enabled,
        "model_configured": bool(settings.google_api_key or settings.gemini_api_key),
        "personal_context_enabled": settings.allow_personal_model_context,
        "semantic_index_enabled": settings.semantic_index_enabled,
        "sources_count": len(technical),
        "pending_reviews": sum(page.has_draft for page in technical),
        "ready": True,
    }


@router.post("/wiki/import")
def import_wiki(request: Request, store: Store) -> dict[str, int]:
    return store.import_tutorials(request.app.state.settings.tutorial_path)


@router.post("/wiki/reindex")
def reindex(request: Request) -> dict[str, str]:
    request.app.state.retrieval.sync(force=True)
    return {"status": "complete" if request.app.state.settings.semantic_index_enabled else "disabled"}


@router.get("/wiki", response_model=list[WikiSummary])
def list_wiki(store: Store, space: Space = "technical", q: str = "") -> list[WikiSummary]:
    return store.list_pages(space, q)


@router.get("/wiki/{page_id}", response_model=WikiDetail)
def get_wiki(page_id: str, store: Store) -> WikiDetail:
    return store.get_page(page_id)


@router.get("/wiki/{page_id}/versions", response_model=list[WikiVersionRead])
def versions(page_id: str, store: Store) -> list[WikiVersionRead]:
    return store.list_versions(page_id)


@router.post("/wiki/{page_id}/approve", response_model=WikiDetail)
def approve(page_id: str, payload: VersionAction, store: Store) -> WikiDetail:
    return store.approve(page_id, payload.version_id, payload.expected_version)


@router.post("/wiki/{page_id}/rollback", response_model=WikiDetail)
def rollback(page_id: str, payload: VersionAction, store: Store) -> WikiDetail:
    return store.rollback(page_id, payload.version_id, payload.expected_version)


@router.post("/wiki/{page_id}/propose", response_model=RunRead, status_code=202)
def propose(page_id: str, payload: ProposalCreate, store: Store) -> RunRead:
    return store.request_technical_proposal(page_id, payload.instructions)


@router.get("/wiki/{page_id}/export")
def export_page(page_id: str, store: Store) -> Response:
    page = store.get_page(page_id)
    sources = "\n".join(
        f"- {item.id} ({item.kind}, {item.revision}): {item.title}" for item in page.citations
    )
    content = page.content + f"\n\n## Source revisions\n\n{sources}\n"
    return Response(
        content=content, media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="wiki-{page.id}.md"'},
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceDetail)
def evidence(evidence_id: str, store: Store) -> EvidenceDetail:
    return store.get_evidence(evidence_id)


@router.post("/agent/ask", response_model=AnswerRead)
def ask(payload: Question, workspace: Workspace) -> AnswerRead:
    return workspace.ask(payload.query, payload.page_id, payload.include_personal)


@router.get("/agent/runs", response_model=list[RunRead])
def list_runs(store: Store, entry_id: str | None = None) -> list[RunRead]:
    return store.list_runs(entry_id)


@router.get("/agent/runs/{run_id}", response_model=RunRead)
def get_run(run_id: str, store: Store) -> RunRead:
    return store.get_run(run_id)


@router.post("/agent/runs/{run_id}/retry", response_model=RunRead)
def retry(run_id: str, store: Store) -> RunRead:
    return store.retry_run(run_id)


@router.get("/journal", response_model=list[JournalRead])
def list_journal(store: Store) -> list[JournalRead]:
    return store.list_journal()


@router.post("/journal", response_model=JournalRead, status_code=201)
def submit_journal(payload: JournalCreate, store: Store) -> JournalRead:
    return store.submit_journal(payload)


@router.post("/plans/preview", response_model=PlanPreviewRead)
def preview(payload: Question, workspace: Workspace) -> PlanPreviewRead:
    return workspace.preview(payload.query, payload.page_id, payload.include_personal)


@router.post("/plans/adopt", response_model=TrainingPlanRead, status_code=201)
def adopt(payload: AdoptPlan, workspace: Workspace) -> TrainingPlanRead:
    return workspace.adopt(payload.preview_id, payload.edited_content)


@router.patch("/plans/{plan_id}", response_model=TrainingPlanRead)
def edit_plan(plan_id: int, payload: PlanEdit, workspace: Workspace) -> TrainingPlanRead:
    return workspace.edit_plan(plan_id, payload)
