from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.plans import router as plans_router
from app.db.session import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="Open Tennis API",
    description="RAG-powered tennis training plan generation backend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(plans_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
