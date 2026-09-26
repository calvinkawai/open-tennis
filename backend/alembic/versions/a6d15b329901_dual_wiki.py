"""Add immutable sources, dual wikis, durable runs, and plan provenance."""

from alembic import op
import sqlalchemy as sa


revision = "a6d15b329901"
down_revision = "6828c22a1516"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sourcesnapshot",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("document_key", sa.String(), nullable=False, index=True),
        sa.Column("revision", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
        sa.Column("source_url", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("document_key", "revision"),
    )
    op.create_table(
        "sourcechunk",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("source_id", sa.String(), sa.ForeignKey("sourcesnapshot.id"), nullable=False, index=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.String(), nullable=False),
    )
    op.create_table(
        "wikipage",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("space", sa.String(), nullable=False),
        sa.Column("topic_key", sa.String(), nullable=False),
        sa.Column("topic", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("current_version_id", sa.String()),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("related_page_id", sa.String()),
        sa.Column("index_status", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
        sa.UniqueConstraint("space", "topic_key"),
    )
    op.create_table(
        "wikiversion",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("page_id", sa.String(), sa.ForeignKey("wikipage.id"), nullable=False, index=True),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("document_json", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.UniqueConstraint("page_id", "number"),
    )
    op.create_table(
        "journalentry",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("client_id", sa.String(), nullable=False, unique=True, index=True),
        sa.Column("topic_page_id", sa.String(), sa.ForeignKey("wikipage.id"), nullable=False, index=True),
        sa.Column("payload_json", sa.String(), nullable=False),
        sa.Column("run_id", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "agentrun",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, index=True),
        sa.Column("page_id", sa.String(), sa.ForeignKey("wikipage.id"), index=True),
        sa.Column("entry_id", sa.String()),
        sa.Column("input_json", sa.String(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        sa.Column("epoch", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.Float(), nullable=False),
        sa.Column("claim_token", sa.String()),
        sa.Column("error_code", sa.String()),
        sa.Column("error_message", sa.String()),
        sa.Column("result_version_id", sa.String()),
        sa.Column("created_at", sa.String(), nullable=False),
        sa.Column("updated_at", sa.String(), nullable=False),
    )
    op.create_table(
        "planpreviewrecord",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("page_id", sa.String()),
        sa.Column("document_json", sa.String(), nullable=False),
        sa.Column("adopted_plan_id", sa.Integer(), sa.ForeignKey("trainingplan.id")),
        sa.Column("created_at", sa.String(), nullable=False),
    )
    op.create_table(
        "planprovenance",
        sa.Column("plan_id", sa.Integer(), sa.ForeignKey("trainingplan.id"), primary_key=True),
        sa.Column("page_id", sa.String()),
        sa.Column("document_json", sa.String(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "planprovenance", "planpreviewrecord", "agentrun", "journalentry",
        "wikiversion", "wikipage", "sourcechunk", "sourcesnapshot",
    ):
        op.drop_table(table)
