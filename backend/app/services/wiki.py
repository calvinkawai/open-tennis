import hashlib
import json
import time
from pathlib import Path

from sqlalchemy import Engine, func, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.core.config import BACKEND_DIR
from app.core.errors import AppError
from app.models.knowledge import (
    AgentRun, JournalEntry, SourceChunk, SourceSnapshot, WikiPage, WikiVersion, new_id, timestamp,
)
from app.models.models import Drill, TrainingPlan
from app.schemas.knowledge import (
    EvidenceDetail,
    EvidenceSection,
    JournalCreate,
    JournalRead,
    RunRead,
    RunLease,
    RunContext,
    Space,
    WikiDetail,
    WikiDocument,
    WikiPatch,
    WikiSummary,
    WikiVersionRead,
    render_sections,
)
from app.services.vector import query_tokens
from scripts.embed_markdowns import load_tutorial_chunks


class WikiStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def submit_journal(self, payload: JournalCreate) -> JournalRead:
        payload = JournalCreate.model_validate(payload.model_dump())
        try:
            with Session(self.engine) as db, db.begin():
                existing = db.exec(select(JournalEntry).where(
                    JournalEntry.client_id == payload.client_id
                )).first()
                if existing:
                    return self._replay_journal(existing, payload)
                if payload.plan_id is not None and db.get(TrainingPlan, payload.plan_id) is None:
                    raise AppError("PLAN_NOT_FOUND", "The associated training card does not exist.", 422)
                if payload.completed_drill_ids:
                    if payload.plan_id is None:
                        raise AppError("PLAN_REQUIRED", "Completed exercises need an associated training card.", 422)
                    allowed = set(db.exec(select(Drill.id).where(
                        Drill.training_plan_id == payload.plan_id
                    )).all())
                    if not set(payload.completed_drill_ids) <= allowed:
                        raise AppError("DRILL_MISMATCH", "An exercise does not belong to this training card.", 422)
                selected = self._page(db, payload.page_id) if payload.page_id else None
                if selected and selected.space == "personal":
                    page = selected
                else:
                    topic_key = selected.id if selected else "unclassified"
                    page = db.exec(select(WikiPage).where(
                        WikiPage.space == "personal", WikiPage.topic_key == topic_key
                    )).first()
                    if page is None:
                        topic = selected.topic if selected else "待归类训练记录"
                        page = WikiPage(
                            space="personal", topic_key=topic_key, topic=topic, title=topic,
                            related_page_id=selected.id if selected else None,
                        )
                        db.add(page)
                        db.flush()
                record = JournalEntry(
                    client_id=payload.client_id, topic_page_id=page.id,
                    payload_json=payload.model_dump_json(),
                )
                db.add(record)
                db.flush()
                run = AgentRun(
                    kind="personal_wiki", page_id=page.id, entry_id=record.id,
                    base_version=page.version, epoch=page.epoch,
                )
                db.add(run)
                db.flush()
                record.run_id = run.id
                db.add(record)
                return self._journal_read(record)
        except IntegrityError as exc:
            with Session(self.engine) as db:
                existing = db.exec(select(JournalEntry).where(
                    JournalEntry.client_id == payload.client_id
                )).first()
                if existing:
                    return self._replay_journal(existing, payload)
            raise AppError("WRITE_CONFLICT", "A concurrent write conflicted; retry with the same identifier.", 409) from exc

    def list_journal(self) -> list[JournalRead]:
        with Session(self.engine) as db:
            return [self._journal_read(row) for row in db.exec(
                select(JournalEntry).order_by(col(JournalEntry.created_at).desc(), JournalEntry.id)
            ).all()]

    def get_journal(self, identifier: str) -> JournalRead:
        with Session(self.engine) as db:
            row = db.get(JournalEntry, identifier)
            if row is None:
                raise AppError("JOURNAL_NOT_FOUND", "The original training record does not exist.", 404)
            return self._journal_read(row)

    def get_run(self, identifier: str) -> RunRead:
        with Session(self.engine) as db:
            row = db.get(AgentRun, identifier)
            if row is None:
                raise AppError("RUN_NOT_FOUND", "The agent run does not exist.", 404)
            return self._run_read(row)

    def list_runs(self, entry_id: str | None = None) -> list[RunRead]:
        with Session(self.engine) as db:
            statement = select(AgentRun).order_by(col(AgentRun.created_at).desc())
            if entry_id:
                statement = statement.where(AgentRun.entry_id == entry_id)
            return [self._run_read(row) for row in db.exec(statement.limit(100)).all()]

    def request_technical_proposal(self, page_id: str, instructions: str) -> RunRead:
        if not instructions.strip() or len(instructions) > 2000:
            raise AppError("INVALID_INSTRUCTIONS", "Provide a short description of the requested change.", 422)
        with Session(self.engine) as db, db.begin():
            page = self._page(db, page_id)
            if page.space != "technical":
                raise AppError("TECHNICAL_PAGE_REQUIRED", "Only technical pages use owner-reviewed proposals.", 422)
            run = AgentRun(
                kind="technical_wiki", page_id=page.id,
                base_version=page.version, epoch=page.epoch,
                input_json=json.dumps({"instructions": instructions}),
            )
            db.add(run)
            db.flush()
            return self._run_read(run)

    def claim_next_run(self, lease_seconds: int = 240) -> RunLease | None:
        if lease_seconds < 1 or lease_seconds > 900:
            raise ValueError("Run lease must be between 1 and 900 seconds.")
        now = time.time()
        with Session(self.engine) as db, db.begin():
            candidates = db.exec(select(AgentRun).where(
                AgentRun.status == "queued",
                col(AgentRun.kind).in_(["personal_wiki", "technical_wiki"]),
            ).order_by(AgentRun.created_at, AgentRun.id).limit(100)).all()
            for candidate in candidates:
                busy = db.exec(select(AgentRun.id).where(
                    AgentRun.page_id == candidate.page_id,
                    AgentRun.status == "running", AgentRun.lease_until > now,
                )).first()
                if busy:
                    continue
                page = self._page(db, candidate.page_id)
                if candidate.epoch != page.epoch:
                    candidate.status = "needs_input"
                    candidate.error_code = "OWNER_ROLLBACK"
                    candidate.error_message = "The owner restored this page. Confirm a retry before updating it."
                    db.add(candidate)
                    continue
                token = new_id()
                result = db.exec(update(AgentRun).where(
                    col(AgentRun.id) == candidate.id, col(AgentRun.status) == "queued"
                ).values(
                    status="running", claim_token=token, lease_until=now + lease_seconds,
                    attempts=candidate.attempts + 1, base_version=page.version,
                    updated_at=timestamp(), error_code=None, error_message=None,
                ))
                if result.rowcount != 1:
                    continue
                db.refresh(candidate)
                return RunLease(run=self._run_read(candidate), claim_token=token)
        return None

    def recover_expired_runs(self) -> int:
        count = 0
        with Session(self.engine) as db, db.begin():
            for row in db.exec(select(AgentRun).where(
                AgentRun.status == "running", AgentRun.lease_until < time.time()
            )).all():
                row.status = "queued" if row.attempts < 3 and row.kind in {"personal_wiki", "technical_wiki"} else "failed"
                row.error_code = "RUN_INTERRUPTED"
                row.error_message = "A previous run was interrupted; its original input is preserved."
                row.claim_token = None
                row.updated_at = timestamp()
                db.add(row)
                count += 1
        return count

    def retry_run(self, identifier: str) -> RunRead:
        with Session(self.engine) as db, db.begin():
            row = self._run(db, identifier)
            if row.kind not in {"personal_wiki", "technical_wiki"} or row.status not in {"failed", "needs_input"}:
                raise AppError("RUN_NOT_RETRYABLE", "Only a failed wiki update can be retried here.", 409)
            page = self._page(db, row.page_id)
            row.status = "queued"
            row.base_version = page.version
            row.epoch = page.epoch
            row.claim_token = None
            row.error_code = None
            row.error_message = None
            row.updated_at = timestamp()
            inputs = json.loads(row.input_json)
            row.input_json = json.dumps({"instructions": inputs.get("instructions", "")})
            db.add(row)
            return self._run_read(row)

    def get_run_context(self, identifier: str, claim_token: str) -> RunContext:
        with Session(self.engine) as db, db.begin():
            row = self._claimed_run(db, identifier, claim_token)
            page = self._page(db, row.page_id)
            if page.version != row.base_version or page.epoch != row.epoch:
                raise AppError("STALE_VERSION", "The target page changed during this run.", 409)
            detail = self._detail(db, page)
            inputs = json.loads(row.input_json)
            selected = {item.id: self._evidence(db, item.id) for item in detail.citations}
            omitted = 0
            if page.space == "personal":
                notes = db.exec(select(JournalEntry).where(
                    JournalEntry.topic_page_id == page.id
                ).order_by(col(JournalEntry.created_at).desc(), JournalEntry.id).limit(41)).all()
                omitted = max(0, self._summary(db, page).record_count - 40)
                for note in notes[:40]:
                    evidence = self._evidence(db, f"journal:{note.id}")
                    selected[evidence.id] = evidence
                if row.entry_id:
                    trigger = self._evidence(db, f"journal:{row.entry_id}")
                    selected[trigger.id] = trigger
                if page.related_page_id:
                    related = self._detail(db, self._page(db, page.related_page_id))
                    if related.status == "published":
                        for citation in related.citations:
                            item = self._evidence(db, citation.id)
                            if item.kind == "technical":
                                selected[item.id] = item
            evidence = list(selected.values())
            if not evidence:
                raise AppError("NO_EVIDENCE", "No original material is available for this update.", 422)
            if len(evidence) > 100:
                raise AppError("CONTEXT_BUDGET", "This topic needs owner review before further automatic expansion.", 422)
            inputs["evidence_ids"] = [item.id for item in evidence]
            inputs["evidence_revisions"] = {item.id: item.revision for item in evidence}
            row.input_json = json.dumps(inputs, ensure_ascii=False)
            db.add(row)
            return RunContext(
                run=self._run_read(row), page=detail,
                instructions=inputs.get("instructions", ""),
                evidence=evidence, omitted_records=omitted,
            )

    def complete_run(
        self, identifier: str, claim_token: str, patch: WikiPatch, allowed_evidence_ids: list[str]
    ) -> RunRead:
        patch = WikiPatch.model_validate(patch.model_dump())
        with Session(self.engine) as db, db.begin():
            row = self._claimed_run(db, identifier, claim_token)
            page = self._page(db, row.page_id)
            if page.version != row.base_version or page.epoch != row.epoch:
                raise AppError("STALE_VERSION", "The page changed; this output was not published.", 409)
            inputs = json.loads(row.input_json)
            recorded = set(inputs.get("evidence_ids", []))
            if not recorded or not set(allowed_evidence_ids) <= recorded:
                raise AppError("INVALID_CONTEXT", "The run cannot introduce evidence it did not read.", 422)
            evidence = [self._evidence(db, item) for item in allowed_evidence_ids]
            if any(item.revision != inputs["evidence_revisions"].get(item.id) for item in evidence):
                raise AppError("STALE_SOURCE", "The source version changed; retry the update.", 409)
            document = self.validate_patch(patch, evidence)
            required_kind = "personal_observation" if page.space == "personal" else "source_supported"
            if not any(section.kind == required_kind for section in patch.sections):
                raise AppError("UNSUPPORTED_PAGE", "The update must retain the page's original evidence type.", 422)
            if page.space == "technical" and any(item.kind == "journal" for item in document.citations):
                raise AppError("TECHNICAL_AUTHORITY", "A personal observation cannot publish technical authority.", 422)
            if page.space == "personal":
                required_records = {
                    item.id for item in self._detail(db, page).citations if item.kind == "journal"
                }
                if row.entry_id:
                    required_records.add(f"journal:{row.entry_id}")
                if not required_records <= {item.id for item in document.citations}:
                    raise AppError(
                        "MISSING_RECORD_CITATION",
                        "The update omitted a triggering or previously linked original record; nothing was published.",
                        422,
                    )
            version = WikiVersion(
                page_id=page.id, number=self._next_number(db, page.id),
                base_version=row.base_version, epoch=row.epoch, run_id=row.id,
                document_json=document.model_dump_json(),
            )
            db.add(version)
            db.flush()
            if page.space == "personal":
                self._publish(db, page, version, row.base_version)
            row.status = "succeeded"
            row.result_version_id = version.id
            row.claim_token = None
            row.lease_until = 0
            row.updated_at = timestamp()
            db.add(row)
            return self._run_read(row)

    def fail_run(self, identifier: str, claim_token: str, code: str, safe_message: str) -> RunRead:
        with Session(self.engine) as db, db.begin():
            row = self._run(db, identifier)
            if row.status != "running" or row.claim_token != claim_token:
                raise AppError("RUN_LEASE_LOST", "The run no longer owns this operation.", 409)
            row.status = "needs_input" if code == "OWNER_ROLLBACK" else "failed"
            row.error_code = code
            row.error_message = safe_message
            row.claim_token = None
            row.lease_until = 0
            row.updated_at = timestamp()
            db.add(row)
            return self._run_read(row)

    def import_tutorials(self, docs_path: Path) -> dict[str, int]:
        root = docs_path.resolve()
        if not root.is_dir():
            raise AppError("SOURCE_DIRECTORY_MISSING", "The tutorial directory is unavailable.", 503)
        files = sorted(root.glob("**/*.md"))
        if len(files) > 1000:
            raise AppError("IMPORT_BUDGET", "Import at most 1000 documents at a time.", 413)
        for path in files:
            if not path.resolve().is_relative_to(root) or path.stat().st_size > 1_048_576:
                raise AppError("SOURCE_NOT_ALLOWED", "A source is outside the corpus or too large.", 422)
        parsed = load_tutorial_chunks(root)
        grouped = {}
        for chunk in parsed:
            source = Path(str(chunk.metadata["source"]))
            absolute = source if source.is_absolute() else BACKEND_DIR / source
            grouped.setdefault(absolute.resolve(), []).append(chunk)
        imported = unchanged = 0
        with Session(self.engine) as db, db.begin():
            for path in files:
                content = path.read_text(encoding="utf-8")
                key = path.relative_to(root).as_posix()
                revision = hashlib.sha256(("sections-v2\0" + content).encode()).hexdigest()
                existing = db.exec(
                    select(SourceSnapshot).where(
                        SourceSnapshot.document_key == key,
                        SourceSnapshot.revision == revision,
                    )
                ).first()
                if existing:
                    unchanged += 1
                    continue
                chunks = grouped.get(path.resolve(), [])
                if not chunks:
                    raise AppError("SOURCE_FORMAT", f"No technical sections found in {key}.", 422)
                source = SourceSnapshot(
                    document_key=key,
                    revision=revision,
                    title=str(chunks[0].metadata["tutorial_title"]),
                    content=content,
                )
                db.add(source)
                db.flush()
                page = db.exec(select(WikiPage).where(
                    WikiPage.space == "technical", WikiPage.topic_key == key
                )).first()
                if page is None:
                    page = WikiPage(
                        space="technical", topic_key=key, topic=source.title, title=source.title
                    )
                    db.add(page)
                    db.flush()
                evidence = []
                sections = []
                for chunk in chunks:
                    stored = SourceChunk(
                        source_id=source.id,
                        title=str(chunk.metadata.get("segment_title") or source.title),
                        content=chunk.content,
                    )
                    db.add(stored)
                    db.flush()
                    item = self._evidence(db, stored.id)
                    evidence.append(item)
                    sections.append(EvidenceSection(
                        kind="source_supported", text=chunk.content, citation_ids=[stored.id]
                    ))
                patch = WikiPatch(
                    title=source.title, sections=sections, change_summary="Imported source snapshot; owner review required."
                )
                document = self.validate_patch(patch, evidence)
                version = WikiVersion(
                    page_id=page.id, number=self._next_number(db, page.id),
                    base_version=page.version, epoch=page.epoch,
                    document_json=document.model_dump_json(),
                )
                db.add(version)
                page.updated_at = timestamp()
                db.add(page)
                imported += 1
        return {"imported": imported, "unchanged": unchanged}

    @staticmethod
    def validate_patch(patch: WikiPatch, evidence: list[EvidenceDetail]) -> WikiDocument:
        allowed = {item.id: item for item in evidence}
        used = []
        for section in patch.sections:
            for identifier in section.citation_ids:
                item = allowed.get(identifier)
                if item is None:
                    raise AppError("INVALID_CITATION", "A citation was not in the supplied source context.", 422)
                expected = "technical" if section.kind == "source_supported" else "journal"
                if item.kind != expected:
                    raise AppError("EVIDENCE_KIND_MISMATCH", "Personal observations are not technical authority.", 422)
                if identifier not in used:
                    used.append(identifier)
        return WikiDocument(
            **patch.model_dump(),
            content=render_sections(patch.title, patch.sections),
            citations=[allowed[identifier].citation() for identifier in used],
        )

    def list_pages(self, space: Space, query: str = "") -> list[WikiSummary]:
        with Session(self.engine) as db:
            pages = db.exec(select(WikiPage).where(WikiPage.space == space).order_by(
                col(WikiPage.updated_at).desc(), WikiPage.id
            )).all()
            words = query_tokens(query)
            return [
                self._summary(db, page)
                for page in pages
                if not words or words & query_tokens(page.title + " " + page.topic)
            ]

    def get_page(self, page_id: str) -> WikiDetail:
        with Session(self.engine) as db:
            return self._detail(db, self._page(db, page_id))

    def list_versions(self, page_id: str) -> list[WikiVersionRead]:
        with Session(self.engine) as db:
            self._page(db, page_id)
            return [
                self._version_read(version)
                for version in db.exec(select(WikiVersion).where(
                    WikiVersion.page_id == page_id
                ).order_by(col(WikiVersion.number).desc())).all()
            ]

    def approve(self, page_id: str, version_id: str, expected_version: int) -> WikiDetail:
        with Session(self.engine) as db, db.begin():
            page = self._page(db, page_id)
            version = self._version(db, page_id, version_id)
            if page.space != "technical" or version.status != "draft":
                raise AppError("NOT_A_TECHNICAL_PROPOSAL", "Only a technical draft can be approved.", 409)
            if version.base_version != expected_version or version.epoch != page.epoch:
                raise AppError("STALE_VERSION", "The proposal is based on an older page; regenerate it.", 409)
            self._publish(db, page, version, expected_version)
            return self._detail(db, page)

    def rollback(self, page_id: str, version_id: str, expected_version: int) -> WikiDetail:
        with Session(self.engine) as db, db.begin():
            page = self._page(db, page_id)
            previous = self._version(db, page_id, version_id)
            if previous.status != "published":
                raise AppError("UNPUBLISHED_VERSION", "A draft cannot be restored as a published page.", 409)
            document = WikiDocument.model_validate_json(previous.document_json)
            document.change_summary = f"Owner restored version {previous.number}."
            version = WikiVersion(
                page_id=page.id, number=self._next_number(db, page.id),
                base_version=expected_version, epoch=page.epoch,
                document_json=document.model_dump_json(),
            )
            db.add(version)
            db.flush()
            self._publish(db, page, version, expected_version)
            page.epoch += 1
            db.add(page)
            return self._detail(db, page)

    def get_evidence(self, identifier: str) -> EvidenceDetail:
        with Session(self.engine) as db:
            return self._evidence(db, identifier)

    def list_indexable_evidence(self) -> list[EvidenceDetail]:
        with Session(self.engine) as db:
            return self._published_evidence(db)

    def search_evidence(
        self, query: str, page_id: str | None = None, include_personal: bool = True, limit: int = 12
    ) -> list[EvidenceDetail]:
        words = query_tokens(query)
        with Session(self.engine) as db:
            preferred = set()
            if page_id:
                page = self._page(db, page_id)
                detail = self._detail(db, page)
                if detail.status == "published":
                    preferred.update(item.id for item in detail.citations)
                if include_personal:
                    associated = db.exec(select(WikiPage.id).where(
                        WikiPage.space == "personal", WikiPage.related_page_id == page_id
                    )).all()
                    preferred.update(
                        f"journal:{note.id}" for note in db.exec(select(JournalEntry).where(
                            col(JournalEntry.topic_page_id).in_([page_id, *associated])
                        )).all()
                    )
            evidence = self._published_evidence(db)
            if not include_personal:
                evidence = [item for item in evidence if item.kind == "technical"]
            ranked = sorted(
                evidence,
                key=lambda item: (4 if item.id in preferred else 0) + len(words & query_tokens(item.title + " " + item.excerpt)),
                reverse=True,
            )
            return [item for item in ranked if item.id in preferred or words & query_tokens(item.title + " " + item.excerpt)][:limit]

    def set_index_status(self, page_id: str, status: str) -> None:
        if status not in {"pending", "ready", "failed"}:
            raise ValueError("Invalid index status.")
        with Session(self.engine) as db, db.begin():
            page = self._page(db, page_id)
            page.index_status = status
            db.add(page)

    @staticmethod
    def _page(db: Session, identifier: str | None) -> WikiPage:
        if identifier is None:
            raise AppError("PAGE_NOT_FOUND", "This operation has no associated wiki page.", 404)
        page = db.get(WikiPage, identifier)
        if page is None:
            raise AppError("PAGE_NOT_FOUND", "The wiki page does not exist.", 404)
        return page

    @staticmethod
    def _run(db: Session, identifier: str) -> AgentRun:
        row = db.get(AgentRun, identifier)
        if row is None:
            raise AppError("RUN_NOT_FOUND", "The agent run does not exist.", 404)
        return row

    def _claimed_run(self, db: Session, identifier: str, token: str) -> AgentRun:
        row = self._run(db, identifier)
        if row.status != "running" or row.claim_token != token or row.lease_until < time.time():
            raise AppError("RUN_LEASE_LOST", "This run expired or another worker owns it.", 409)
        return row

    @staticmethod
    def _version(db: Session, page_id: str, identifier: str) -> WikiVersion:
        version = db.get(WikiVersion, identifier)
        if version is None or version.page_id != page_id:
            raise AppError("VERSION_NOT_FOUND", "The version does not belong to this page.", 404)
        return version

    @staticmethod
    def _next_number(db: Session, page_id: str) -> int:
        latest = db.exec(select(func.max(WikiVersion.number)).where(WikiVersion.page_id == page_id)).one()
        return (latest if latest is not None else 0) + 1

    def _summary(self, db: Session, page: WikiPage) -> WikiSummary:
        draft = db.exec(select(WikiVersion.id).where(
            WikiVersion.page_id == page.id, WikiVersion.status == "draft",
            WikiVersion.base_version == page.version, WikiVersion.epoch == page.epoch,
        )).first()
        return WikiSummary.model_validate({
            "id": page.id, "space": page.space, "title": page.title, "topic": page.topic,
            "version": page.version, "updated_at": page.updated_at,
            "has_draft": draft is not None, "index_status": page.index_status,
            "record_count": db.exec(select(func.count()).select_from(JournalEntry).where(
                JournalEntry.topic_page_id == page.id
            )).one(),
        })

    def _detail(self, db: Session, page: WikiPage) -> WikiDetail:
        version = db.get(WikiVersion, page.current_version_id) if page.current_version_id else None
        if version is None:
            version = db.exec(select(WikiVersion).where(
                WikiVersion.page_id == page.id
            ).order_by(col(WikiVersion.number).desc())).first()
        if version is None:
            return WikiDetail(
                **self._summary(db, page).model_dump(), version_id=None, status="empty",
                content="", sections=[], citations=[], change_summary="",
            )
        document = WikiDocument.model_validate_json(version.document_json)
        return WikiDetail.model_validate({
            **self._summary(db, page).model_dump(), "version_id": version.id, "status": version.status,
            "content": document.content, "sections": document.sections,
            "citations": document.citations, "change_summary": document.change_summary,
        })

    @staticmethod
    def _version_read(version: WikiVersion) -> WikiVersionRead:
        document = WikiDocument.model_validate_json(version.document_json)
        return WikiVersionRead.model_validate({
            "id": version.id, "page_id": version.page_id, "number": version.number,
            "status": version.status, "content": document.content, "sections": document.sections,
            "citations": document.citations, "created_at": version.created_at,
            "change_summary": document.change_summary,
        })

    @staticmethod
    def _evidence(db: Session, identifier: str) -> EvidenceDetail:
        if identifier.startswith("journal:"):
            row = db.get(JournalEntry, identifier.removeprefix("journal:"))
            if row is None:
                raise AppError("EVIDENCE_NOT_FOUND", "The original training record does not exist.", 404)
            payload = JournalCreate.model_validate_json(row.payload_json)
            content = "\n".join([
                f"本人记录：{payload.content}",
                f"情境：{payload.context or '未填写'}",
                f"主观感受：{payload.feeling or '未填写'}",
                "本人标记完成的练习编号：" + ", ".join(map(str, payload.completed_drill_ids)),
            ])
            return EvidenceDetail(
                id=identifier, kind="journal", title=f"本人训练记录 / {row.created_at[:10]}",
                excerpt=content, content=content,
                revision=hashlib.sha256(row.payload_json.encode()).hexdigest(),
            )
        chunk = db.get(SourceChunk, identifier)
        if chunk is None:
            raise AppError("EVIDENCE_NOT_FOUND", "The original evidence does not exist.", 404)
        source = db.get(SourceSnapshot, chunk.source_id)
        if source is None:
            raise AppError("SOURCE_INTEGRITY", "The source snapshot is missing.", 500)
        return EvidenceDetail(
            id=chunk.id, kind="technical", title=chunk.title, excerpt=chunk.content,
            content=source.content, revision=source.revision, source_url=source.source_url,
        )

    def _published_evidence(self, db: Session) -> list[EvidenceDetail]:
        identifiers = set()
        for page in db.exec(select(WikiPage).where(
            WikiPage.space == "technical", col(WikiPage.current_version_id).is_not(None)
        )).all():
            version = db.get(WikiVersion, page.current_version_id)
            if version is None:
                raise AppError("VERSION_INTEGRITY", "The published wiki version is missing.", 500)
            document = WikiDocument.model_validate_json(version.document_json)
            identifiers.update(item.id for item in document.citations if item.kind == "technical")
        identifiers.update(
            f"journal:{row.id}" for row in db.exec(select(JournalEntry)).all()
        )
        return [self._evidence(db, identifier) for identifier in sorted(identifiers)]

    @staticmethod
    def _journal_read(row: JournalEntry) -> JournalRead:
        payload = JournalCreate.model_validate_json(row.payload_json)
        return JournalRead(
            **payload.model_dump(), id=row.id, created_at=row.created_at, run_id=row.run_id
        )

    def _replay_journal(self, row: JournalEntry, payload: JournalCreate) -> JournalRead:
        if row.payload_json != payload.model_dump_json():
            raise AppError("SUBMISSION_CONFLICT", "This identifier already belongs to a different original record.", 409)
        return self._journal_read(row)

    @staticmethod
    def _run_read(row: AgentRun) -> RunRead:
        return RunRead.model_validate({
            key: getattr(row, key) for key in RunRead.model_fields
        })

    @staticmethod
    def _publish(db: Session, page: WikiPage, version: WikiVersion, expected_version: int) -> None:
        document = WikiDocument.model_validate_json(version.document_json)
        result = db.exec(update(WikiPage).where(
            col(WikiPage.id) == page.id, col(WikiPage.version) == expected_version,
            col(WikiPage.epoch) == version.epoch,
        ).values(
            version=version.number, current_version_id=version.id,
            title=document.title, updated_at=timestamp(), index_status="pending",
        ))
        if result.rowcount != 1:
            raise AppError("STALE_VERSION", "The page changed; reload before applying this change.", 409)
        version.status = "published"
        db.add(version)
        db.flush()
        db.refresh(page)
