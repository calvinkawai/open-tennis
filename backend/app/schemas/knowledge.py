from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Space = Literal["technical", "personal"]
EvidenceKind = Literal["technical", "journal"]
SectionKind = Literal["source_supported", "personal_observation", "model_supplement"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Evidence(StrictModel):
    id: str
    kind: EvidenceKind
    title: str
    excerpt: str
    source_url: str | None = None
    revision: str


class EvidenceDetail(Evidence):
    content: str

    def citation(self) -> Evidence:
        return Evidence.model_validate(self.model_dump(exclude={"content"}))


class EvidenceSection(StrictModel):
    kind: SectionKind
    text: str = Field(min_length=1, max_length=20000)
    citation_ids: list[str] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def require_matching_provenance(self) -> "EvidenceSection":
        if not self.text.strip():
            raise ValueError("Section text cannot be blank.")
        if self.kind == "model_supplement" and self.citation_ids:
            raise ValueError("An unverified supplement cannot claim supporting citations.")
        if self.kind != "model_supplement" and not self.citation_ids:
            raise ValueError("Supported content must cite its original evidence.")
        return self


class WikiPatch(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    sections: list[EvidenceSection] = Field(min_length=1, max_length=32)
    change_summary: str = Field(min_length=1, max_length=1000)


class WikiDocument(WikiPatch):
    content: str
    citations: list[Evidence]


class WikiSummary(StrictModel):
    id: str
    space: Space
    title: str
    topic: str
    version: int
    updated_at: str
    has_draft: bool
    index_status: Literal["pending", "ready", "failed"]
    record_count: int = 0


class WikiDetail(WikiSummary):
    version_id: str | None
    status: Literal["draft", "published", "empty"]
    content: str
    sections: list[EvidenceSection]
    citations: list[Evidence]
    change_summary: str


class WikiVersionRead(StrictModel):
    id: str
    page_id: str
    number: int
    status: Literal["draft", "published"]
    content: str
    sections: list[EvidenceSection]
    citations: list[Evidence]
    created_at: str
    change_summary: str


class JournalCreate(StrictModel):
    client_id: str
    plan_id: int | None = Field(default=None, gt=0)
    page_id: str | None = None
    content: str = Field(default="", max_length=10000)
    context: str | None = Field(default=None, max_length=500)
    feeling: str | None = Field(default=None, max_length=500)
    completed_drill_ids: list[int] = Field(default_factory=list, max_length=30)

    @field_validator("client_id")
    @classmethod
    def canonical_client_id(cls, value: str) -> str:
        if str(UUID(value)) != value:
            raise ValueError("Use a canonical UUID as the submission identifier.")
        return value

    @model_validator(mode="after")
    def validate_record(self) -> "JournalCreate":
        if not self.content.strip() and not self.completed_drill_ids:
            raise ValueError("A record needs an observation or a completed exercise.")
        if len(set(self.completed_drill_ids)) != len(self.completed_drill_ids):
            raise ValueError("Completed exercises must be unique.")
        if any(identifier <= 0 for identifier in self.completed_drill_ids):
            raise ValueError("Exercise identifiers must be positive.")
        return self


class JournalRead(JournalCreate):
    id: str
    created_at: str
    run_id: str | None


class RunRead(StrictModel):
    id: str
    kind: str
    status: Literal["queued", "running", "succeeded", "failed", "needs_input"]
    page_id: str | None
    entry_id: str | None
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str
    result_version_id: str | None


class RunLease(StrictModel):
    run: RunRead
    claim_token: str


class RunContext(StrictModel):
    run: RunRead
    page: WikiDetail
    instructions: str
    evidence: list[EvidenceDetail]
    omitted_records: int = 0


class AnswerDraft(StrictModel):
    sections: list[EvidenceSection] = Field(min_length=1, max_length=16)


class AnswerRead(AnswerDraft):
    citations: list[Evidence]
    run_id: str
    warning: str | None = None


class Question(StrictModel):
    query: str = Field(min_length=3, max_length=2000)
    page_id: str | None = None
    include_personal: bool = False


class VersionAction(StrictModel):
    version_id: str
    expected_version: int = Field(ge=0)


class ProposalCreate(StrictModel):
    instructions: str = Field(min_length=3, max_length=2000)


def render_sections(title: str, sections: list[EvidenceSection]) -> str:
    labels = {
        "source_supported": "资料支持",
        "personal_observation": "本人记录 · 主观观察",
        "model_supplement": "模型补充 · 未经知识库核验",
    }
    parts = [f"# {title}"]
    for section in sections:
        parts.extend([f"## {labels[section.kind]}", section.text])
        if section.citation_ids:
            parts.append("来源编号：" + ", ".join(section.citation_ids))
    return "\n\n".join(parts)
