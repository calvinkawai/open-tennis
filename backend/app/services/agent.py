import logging

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.core.errors import AppError
from app.schemas.knowledge import WikiPatch
from app.services.model import ModelGateway, StructuredModel
from app.services.wiki import WikiStore

logger = logging.getLogger(__name__)


class RuntimeAgent:
    def __init__(
        self, store: WikiStore, settings: Settings, model: StructuredModel | None = None
    ) -> None:
        self.store = store
        self.settings = settings
        self.model = model or ModelGateway(settings)

    def run_once(self) -> bool:
        if not self.settings.agent_enabled:
            return False
        self.store.recover_expired_runs()
        lease = self.store.claim_next_run(lease_seconds=600)
        if lease is None:
            return False
        try:
            if lease.run.kind == "personal_wiki" and not self.settings.allow_personal_model_context:
                raise AppError(
                    "PERSONAL_CONTEXT_DISABLED",
                    "The original record is saved. Permit personal model context before compiling this wiki.",
                    403,
                )
            context = self.store.get_run_context(lease.run.id, lease.claim_token)
            patch = self.model.generate(
                WikiPatch,
                """Organize a wiki page from the supplied original evidence.
Return a COMPLETE next version, retaining relevant prior observations and their
citations, not a destructive fragment. Previous wiki text helps navigation but is
not new evidence. Record contradictions instead of resolving them without evidence.
If some older records were omitted, preserve existing supported context and state
the limitation; do not claim to have reviewed all history.
Personal pages need at least one personal_observation section and may link
technical sources. Technical pages need source_supported sections and cannot
turn journal observations into technical authority. Technical output is only a
proposal: the owner, not you, decides publication.
Do not claim an action was approved, a record changed, or a source verified.
Use Chinese for the wiki headings unless the owner explicitly requests English.""",
                {
                    "space": context.page.space,
                    "topic": context.page.topic,
                    "owner_instructions": context.instructions,
                    "previous_sections": [section.model_dump() for section in context.page.sections],
                    "evidence": [
                        item.model_dump(exclude={"content"}) for item in context.evidence
                    ],
                    "omitted_older_records": context.omitted_records,
                },
            )
            self.store.complete_run(
                lease.run.id, lease.claim_token, patch,
                [item.id for item in context.evidence],
            )
            logger.info("wiki_run_succeeded", extra={"run_id": lease.run.id})
        except AppError as exc:
            self.store.fail_run(lease.run.id, lease.claim_token, exc.code, exc.message)
            logger.warning("wiki_run_failed", extra={"run_id": lease.run.id, "error_code": exc.code})
        except (SQLAlchemyError, ValueError, RuntimeError) as exc:
            logger.error("wiki_run_failed", extra={"run_id": lease.run.id, "error_type": type(exc).__name__})
            self.store.fail_run(
                lease.run.id, lease.claim_token, "RUN_FAILED",
                "The wiki update failed. The original record is preserved; retry the run.",
            )
        return True
