import logging
import re
import time
from datetime import UTC, datetime

from sqlalchemy import update
from sqlmodel import Session, col

from app.crud import training_plan as plan_crud
from app.core.config import Settings
from app.core.errors import AppError
from app.models.knowledge import AgentRun, PlanPreviewRecord, PlanProvenance, new_id, timestamp
from app.models.models import Drill, TrainingPlan
from app.schemas.knowledge import AnswerDraft, AnswerRead, EvidenceSection, Question, WikiPatch
from app.schemas.plans import GroundedPlanDraft, PlanEdit, PlanPreviewRead, TrainingPlanRead
from app.services.model import ModelGateway, StructuredModel
from app.services.retrieval import WikiRetriever
from app.services.wiki import WikiStore

logger = logging.getLogger(__name__)
HEALTH_QUERY = re.compile(
    r"pain|injur|rehab|hurt|physiotherap|疼|受伤|伤病|康复|肿胀|麻木|医疗", re.IGNORECASE
)
HEALTH_MESSAGE = (
    "你提到了疼痛或伤病。这类情况不适合用普通技术建议诊断或制定康复练习；"
    "请先停止引发不适的练习，并咨询合适的医疗专业人士。"
    "你仍可保存原始记录，等获得适合自己的建议后再安排训练。"
)


class WorkspaceService:
    def __init__(
        self, store: WikiStore, settings: Settings, model: StructuredModel | None = None,
        retrieval: WikiRetriever | None = None,
    ) -> None:
        self.store = store
        self.settings = settings
        self.model = model or ModelGateway(settings)
        self.retrieval = retrieval or WikiRetriever(store, settings)

    def preview(
        self, query: str, page_id: str | None = None, include_personal: bool = False
    ) -> PlanPreviewRead:
        request = Question(query=query, page_id=page_id, include_personal=include_personal)
        self._check_personal_access(request)
        if HEALTH_QUERY.search(query):
            raise AppError("HEALTH_LIMITATION", HEALTH_MESSAGE, 422)
        run_id = self._start_request("plan_preview", page_id)
        try:
            retrieved = self.retrieval.search(query, page_id, include_personal)
            evidence = retrieved.evidence
            draft = self.model.generate(
                GroundedPlanDraft,
                """Create a concise, conservative tennis training-card PREVIEW with 3-5
progressive drills. Return title, focus_area, raw_ai_content, drills and typed
sections. Use supplied personal observations only as self-report, not diagnosis.
Technical explanations need technical citations. Doses, ordering and any
unsupported advice are model supplements, never claimed as established facts.
Each drill must be concise and adjustable. video_url must be null unless an exact
video URL is supplied in the evidence. No invented links, health advice or scores.
Never claim the owner has adopted the plan. Match the language of the query.""",
                {"query": query, "evidence": [item.model_dump(exclude={"content"}) for item in evidence]},
            )
            known_urls = {item.source_url for item in evidence if item.source_url}
            if any(drill.video_url and drill.video_url not in known_urls for drill in draft.drills):
                raise AppError("UNSUPPORTED_VIDEO", "The model supplied a video URL not present in the sources.", 502)
            sections = draft.sections + [EvidenceSection(
                kind="model_supplement",
                text="练习的编排、顺序和组数是可调整的模型补充，未经知识库核验；由你决定是否采用。",
            )]
            document = self.store.validate_patch(
                WikiPatch(title=draft.title, sections=sections, change_summary="Training-card preview."),
                evidence,
            )
            identifier = new_id()
            preview = PlanPreviewRead(
                **draft.model_dump(exclude={"sections", "raw_ai_content"}),
                preview_id=identifier, sections=document.sections,
                raw_ai_content=document.content, citations=document.citations,
                warning=retrieved.warning if any(item.kind == "technical" for item in evidence)
                else "没有检索到已审阅的技术依据；这张卡中的建议未经知识库核验。",
                run_id=run_id,
            )
            with Session(self.store.engine) as db, db.begin():
                db.add(PlanPreviewRecord(
                    id=identifier, page_id=page_id, run_id=run_id,
                    document_json=preview.model_dump_json(),
                ))
            self._finish_request(run_id)
            return preview
        except AppError as exc:
            self._finish_request(run_id, exc)
            raise

    def adopt(self, preview_id: str, edited_content: str | None) -> TrainingPlanRead:
        if edited_content is not None and len(edited_content) > 20000:
            raise AppError("EDIT_TOO_LARGE", "The edited plan is too long.", 422)
        with Session(self.store.engine) as db, db.begin():
            record = db.get(PlanPreviewRecord, preview_id)
            if record is None:
                raise AppError("PREVIEW_NOT_FOUND", "The original plan preview does not exist.", 404)
            if record.adopted_plan_id is not None:
                plan = self._plan(db, record.adopted_plan_id)
                if plan.edited_content != edited_content:
                    raise AppError("ADOPTION_CONFLICT", "This preview was already adopted; edit the saved card instead.", 409)
                return self._plan_read(db, plan)
            preview = PlanPreviewRead.model_validate_json(record.document_json)
            plan = TrainingPlan(
                title=preview.title, focus_area=preview.focus_area,
                raw_ai_content=preview.raw_ai_content, edited_content=edited_content,
                drills=[Drill(**drill.model_dump()) for drill in preview.drills],
            )
            db.add(plan)
            db.flush()
            assert plan.id is not None
            result = db.exec(update(PlanPreviewRecord).where(
                col(PlanPreviewRecord.id) == preview_id,
                col(PlanPreviewRecord.adopted_plan_id).is_(None),
            ).values(adopted_plan_id=plan.id))
            if result.rowcount != 1:
                raise AppError("ADOPTION_CONFLICT", "The card was adopted concurrently; retry this preview identifier.", 409)
            db.add(PlanProvenance(
                plan_id=plan.id, page_id=record.page_id, document_json=record.document_json,
            ))
            db.flush()
            return self._plan_read(db, plan)

    def list_plans(self, skip: int = 0, limit: int = 100) -> list[TrainingPlanRead]:
        with Session(self.store.engine) as db:
            return [self._plan_read(db, plan) for plan in plan_crud.get_plans(db, skip, limit)]

    def get_plan(self, identifier: int) -> TrainingPlanRead:
        with Session(self.store.engine) as db:
            return self._plan_read(db, self._plan(db, identifier))

    def edit_plan(self, identifier: int, edit: PlanEdit) -> TrainingPlanRead:
        with Session(self.store.engine) as db, db.begin():
            plan = self._plan(db, identifier)
            if edit.title is not None:
                if not edit.title.strip():
                    raise AppError("EMPTY_TITLE", "The plan title cannot be blank.", 422)
                plan.title = edit.title
            if "edited_content" in edit.model_fields_set:
                plan.edited_content = edit.edited_content
            if edit.drills is not None:
                by_id = {drill.id: drill for drill in plan.drills}
                if len({drill.id for drill in edit.drills}) != len(edit.drills):
                    raise AppError("DUPLICATE_DRILL", "Edit each drill at most once.", 422)
                for change in edit.drills:
                    drill = by_id.get(change.id)
                    if drill is None:
                        raise AppError("DRILL_MISMATCH", "This exercise does not belong to this card.", 422)
                    if change.name is not None:
                        drill.name = change.name
                    if change.description is not None:
                        drill.description = change.description
                    db.add(drill)
            plan.updated_at = datetime.now(UTC)
            db.add(plan)
            db.flush()
            return self._plan_read(db, plan)

    @staticmethod
    def _plan(db: Session, identifier: int) -> TrainingPlan:
        plan = plan_crud.get_plan(db, identifier)
        if plan is None:
            raise AppError("PLAN_NOT_FOUND", "The training card does not exist.", 404)
        return plan

    @staticmethod
    def _plan_read(db: Session, plan: TrainingPlan) -> TrainingPlanRead:
        result = TrainingPlanRead.model_validate(plan)
        provenance = db.get(PlanProvenance, plan.id)
        if provenance is not None:
            preview = PlanPreviewRead.model_validate_json(provenance.document_json)
            result.sections = preview.sections
            result.citations = preview.citations
            result.wiki_page_id = provenance.page_id
        elif not result.sections:
            result.sections = [EvidenceSection(
                kind="model_supplement",
                text="旧版训练卡没有结构化来源记录，不能据此确认资料支持。\n\n" + plan.raw_ai_content,
            )]
        return result

    def ask(
        self, query: str, page_id: str | None = None, include_personal: bool = False
    ) -> AnswerRead:
        request = Question(query=query, page_id=page_id, include_personal=include_personal)
        self._check_personal_access(request)
        run_id = self._start_request("answer", page_id)
        try:
            if HEALTH_QUERY.search(query):
                result = AnswerRead(
                    sections=[EvidenceSection(kind="model_supplement", text=HEALTH_MESSAGE)],
                    citations=[], run_id=run_id, warning="非诊疗提醒：未调用模型生成训练建议。",
                )
            else:
                retrieved = self.retrieval.search(query, page_id, include_personal)
                evidence = retrieved.evidence
                page = self.store.get_page(page_id) if page_id else None
                draft = self.model.generate(
                    AnswerDraft,
                    """Answer the question using the provided source excerpts and original
personal observations. If evidence is missing, say so and use model_supplement
sections only. Never imply a personal observation proves technical correctness.
Do not invent source IDs or medical advice. Keep the answer short and practical.""",
                    {
                        "query": query,
                        "topic": page.topic if page else None,
                        "evidence": [item.model_dump(exclude={"content"}) for item in evidence],
                    },
                )
                document = self.store.validate_patch(
                    WikiPatch(title="Answer", sections=draft.sections, change_summary="Requested answer"),
                    evidence,
                )
                result = AnswerRead(
                    sections=document.sections, citations=document.citations, run_id=run_id,
                    warning=retrieved.warning if any(item.kind == "technical" for item in evidence)
                    else "没有检索到已审阅的技术依据；模型补充未经知识库核验。",
                )
            self._finish_request(run_id)
            return result
        except AppError as exc:
            self._finish_request(run_id, exc)
            raise

    def _check_personal_access(self, request: Question) -> None:
        if not request.query.strip():
            raise AppError("EMPTY_QUERY", "The question cannot be blank.", 422)
        if request.include_personal and not self.settings.allow_personal_model_context:
            raise AppError(
                "PERSONAL_CONTEXT_DISABLED",
                "Personal model context is disabled. Enable it on the private server before sending personal records.",
                403,
            )

    def _start_request(self, kind: str, page_id: str | None) -> str:
        if page_id:
            self.store.get_page(page_id)
        with Session(self.store.engine) as db, db.begin():
            row = AgentRun(kind=kind, page_id=page_id, status="running")
            row.lease_until = time.time() + 600
            db.add(row)
            db.flush()
            return row.id

    def _finish_request(self, identifier: str, error: AppError | None = None) -> None:
        with Session(self.store.engine) as db, db.begin():
            row = db.get(AgentRun, identifier)
            if row is None:
                raise AppError("RUN_NOT_FOUND", "The request audit record is missing.", 500)
            row.status = "failed" if error else "succeeded"
            row.updated_at = timestamp()
            row.error_code = error.code if error else None
            row.error_message = error.message if error else None
            db.add(row)
        logger.log(
            logging.WARNING if error else logging.INFO,
            "workspace_request",
            extra={"run_id": identifier, "status": "failed" if error else "succeeded"},
        )
