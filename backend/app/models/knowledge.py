from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def new_id() -> str:
    return uuid4().hex


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


class SourceSnapshot(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("document_key", "revision"),)

    id: str = Field(default_factory=new_id, primary_key=True)
    document_key: str = Field(index=True)
    revision: str
    title: str
    content: str
    source_url: str | None = None
    created_at: str = Field(default_factory=timestamp)


class SourceChunk(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    source_id: str = Field(foreign_key="sourcesnapshot.id", index=True)
    title: str
    content: str


class WikiPage(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("space", "topic_key"),)

    id: str = Field(default_factory=new_id, primary_key=True)
    space: str
    topic_key: str
    topic: str
    title: str
    version: int = 0
    current_version_id: str | None = None
    epoch: int = 0
    related_page_id: str | None = None
    index_status: str = "pending"
    updated_at: str = Field(default_factory=timestamp)


class WikiVersion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("page_id", "number"),)

    id: str = Field(default_factory=new_id, primary_key=True)
    page_id: str = Field(foreign_key="wikipage.id", index=True)
    number: int
    base_version: int
    epoch: int = 0
    status: str = "draft"
    document_json: str
    run_id: str | None = None
    created_at: str = Field(default_factory=timestamp)


class JournalEntry(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    client_id: str = Field(unique=True, index=True)
    topic_page_id: str = Field(foreign_key="wikipage.id", index=True)
    payload_json: str
    run_id: str | None = None
    created_at: str = Field(default_factory=timestamp)


class AgentRun(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    kind: str
    status: str = Field(default="queued", index=True)
    page_id: str | None = Field(default=None, foreign_key="wikipage.id", index=True)
    entry_id: str | None = None
    input_json: str = "{}"
    base_version: int = 0
    epoch: int = 0
    attempts: int = 0
    lease_until: float = 0
    claim_token: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    result_version_id: str | None = None
    created_at: str = Field(default_factory=timestamp)
    updated_at: str = Field(default_factory=timestamp)


class PlanPreviewRecord(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    run_id: str
    page_id: str | None = None
    document_json: str
    adopted_plan_id: int | None = Field(default=None, foreign_key="trainingplan.id")
    created_at: str = Field(default_factory=timestamp)


class PlanProvenance(SQLModel, table=True):
    plan_id: int = Field(primary_key=True, foreign_key="trainingplan.id")
    page_id: str | None = None
    document_json: str
