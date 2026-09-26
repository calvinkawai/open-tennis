import asyncio
import logging
import time
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, create_engine

from app.api.v1.plans import get_plan_generation_service
from app.api.v1.plans import router as plans_router
from app.api.v1.workspace import router as workspace_router
from app.core.access import owner_authorized
from app.core.config import Settings
from app.core.errors import AppError
from app.core.observability import configure_logging
from app.db.migrations import initialize_database
from app.db.session import get_session
from app.services.agent import RuntimeAgent
from app.services.generation import PlanGenerationService
from app.services.llm import LLMService
from app.services.model import ModelGateway, StructuredModel
from app.services.retrieval import WikiRetriever
from app.services.vector import VectorService
from app.services.wiki import WikiStore
from app.services.workspace import WorkspaceService

logger = logging.getLogger("open_tennis")


def create_app(settings: Settings | None = None, model: StructuredModel | None = None) -> FastAPI:
    settings = settings or Settings()
    engine = create_engine(
        settings.sqlite_url, connect_args={"check_same_thread": False, "timeout": 20}
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=20000")

    store = WikiStore(engine)
    gateway = model or ModelGateway(settings)
    agent = RuntimeAgent(store, settings, gateway)
    retrieval = WikiRetriever(store, settings)
    stop = asyncio.Event()

    async def worker() -> None:
        while not stop.is_set():
            try:
                await asyncio.to_thread(agent.run_once)
                await asyncio.to_thread(retrieval.sync)
            except (AppError, SQLAlchemyError, ValueError, RuntimeError) as exc:
                logger.error("worker_failed", extra={"error_type": type(exc).__name__})
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except TimeoutError:
                continue

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        settings.sqlite_database_path.parent.mkdir(parents=True, exist_ok=True)
        initialize_database(engine)
        configure_logging()
        stop.clear()
        background = asyncio.create_task(worker()) if settings.agent_enabled or settings.semantic_index_enabled else None
        try:
            yield
        finally:
            stop.set()
            if background:
                await background
            engine.dispose()

    app = FastAPI(
        title="Open Tennis API",
        description="Private source-grounded tennis wiki and training journal.",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.wiki_store = store
    app.state.workspace_service = WorkspaceService(store, settings, gateway, retrieval)
    app.state.retrieval = retrieval
    app.state.agent = agent

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_plan_generation_service] = lambda: PlanGenerationService(
        vector_service=VectorService(settings), llm_service=LLMService(settings)
    )

    def failure(request: Request, status: int, code: str, message: str, headers=None):
        return JSONResponse(
            status_code=status,
            content={"detail": message, "code": code, "request_id": request.state.request_id},
            headers=headers,
        )

    @app.middleware("http")
    async def private_access(request: Request, call_next):
        request.state.request_id = uuid4().hex
        started = time.monotonic()
        if not settings.owner_password:
            response = failure(request, 503, "OWNER_NOT_CONFIGURED", "Configure private owner access before using this server.")
        elif not owner_authorized(request.headers.get("authorization"), settings.owner_username, settings.owner_password):
            response = failure(
                request, 401, "OWNER_REQUIRED", "Owner authentication is required.",
                {"WWW-Authenticate": 'Basic realm="Open Tennis", charset="UTF-8"'},
            )
        elif request.method in {"POST", "PATCH", "PUT", "DELETE"} and (
            request.headers.get("sec-fetch-site") == "cross-site"
            or (
                request.headers.get("origin")
                and request.headers["origin"].rstrip("/")
                != (settings.public_origin or str(request.base_url)).rstrip("/")
            )
        ):
            response = failure(request, 403, "ORIGIN_REJECTED", "Cross-site writes are not allowed.")
        elif request.method in {"POST", "PATCH", "PUT"} and not request.headers.get("content-type", "").startswith("application/json"):
            response = failure(request, 415, "JSON_REQUIRED", "Use application/json for write requests.")
        else:
            response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        logger.info(
            "http_request",
            extra={
                "request_id": request.state.request_id,
                "method": request.method, "status": response.status_code,
                "duration_ms": round((time.monotonic() - started) * 1000),
            },
        )
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        logger.warning("request_failed", extra={"request_id": request.state.request_id, "error_code": exc.code})
        return failure(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return failure(request, 422, "INVALID_INPUT", "The request did not pass validation; check the field values.")

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logger.error("database_request_failed", extra={
            "request_id": request.state.request_id, "error_type": type(exc).__name__
        })
        return failure(request, 503, "DATABASE_UNAVAILABLE", "The database operation failed; retry with the same submission identifier.")

    @app.exception_handler(ResponseValidationError)
    async def response_error(request: Request, exc: ResponseValidationError):
        logger.error("response_invalid", extra={"request_id": request.state.request_id})
        return failure(request, 500, "RESPONSE_INVALID", "The result could not be validated; do not assume the operation completed.")

    app.include_router(workspace_router, prefix="/api/v1")
    app.include_router(plans_router, prefix="/api/v1")

    @app.get("/health")
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
