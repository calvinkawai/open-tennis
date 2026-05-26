from pathlib import Path

from sqlmodel import SQLModel, Session, create_engine

from app.core.config import get_settings

settings = get_settings()
Path(settings.sqlite_database_path).parent.mkdir(parents=True, exist_ok=True)

# connect_args={"check_same_thread": False} is required for SQLite + FastAPI
# because FastAPI can handle requests in multiple threads.
engine = create_engine(
    settings.sqlite_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


def create_db_and_tables() -> None:
    from app.models import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    """
    FastAPI Dependency: Yields a new session for every request and
    closes it when the request is done.
    """
    with Session(engine) as session:
        yield session
