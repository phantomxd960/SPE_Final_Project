"""Initial schema (Section 6).

Revision ID: 0001
Revises:
Create Date: 2026-11-21
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.Integer, primary_key=True)


def _now(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        _id(),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        _now("created_at"),
    )
    op.create_table(
        "documents",
        _id(),
        sa.Column("doc_code", sa.String(64), nullable=False, unique=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("authority", sa.String(255)),
        _now("created_at"),
    )
    op.create_table(
        "document_versions",
        _id(),
        sa.Column("document_id", sa.Integer, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_label", sa.String(64), nullable=False),
        sa.Column("effective_date", sa.Date),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("title", sa.String(255)),
        sa.Column("meta", JSONB, nullable=False, server_default="{}"),
        sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("users.id")),
        _now("uploaded_at"),
        sa.UniqueConstraint("document_id", "version_label"),
        sa.UniqueConstraint("document_id", "sha256"),
    )
    op.create_table(
        "clauses",
        _id(),
        sa.Column("version_id", sa.Integer, sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("clause_number", sa.String(64), nullable=False),
        sa.Column("section", sa.String(255)),
        sa.Column("page", sa.Integer, nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("text_hash", sa.String(64), nullable=False),
        sa.Column("embedding", Vector(384)),
        sa.Column("ocr_flag", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_clauses_version_number", "clauses", ["version_id", "clause_number"])
    op.execute("CREATE INDEX ix_clauses_embedding ON clauses USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX ix_clauses_fulltext ON clauses USING gin (to_tsvector('english', text))")

    op.create_table(
        "comparisons",
        _id(),
        sa.Column("old_version_id", sa.Integer, sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("new_version_id", sa.Integer, sa.ForeignKey("document_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id")),
        _now("created_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "clause_changes",
        _id(),
        sa.Column("comparison_id", sa.Integer, sa.ForeignKey("comparisons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("old_clause_id", sa.Integer, sa.ForeignKey("clauses.id", ondelete="SET NULL")),
        sa.Column("new_clause_id", sa.Integer, sa.ForeignKey("clauses.id", ondelete="SET NULL")),
        sa.Column("change_type", sa.String(32), nullable=False),
        sa.Column("text_diff", JSONB, nullable=False),
        sa.Column("similarity", sa.Float, nullable=False),
        sa.Column("numeric_changes", JSONB, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("reviewed", sa.Boolean, nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_clause_changes_comparison", "clause_changes", ["comparison_id"])

    op.create_table(
        "graph_nodes",
        _id(),
        sa.Column("node_type", sa.String(32), nullable=False),
        sa.Column("ref_id", sa.String(255), nullable=False),
        sa.Column("label", sa.String(512), nullable=False),
        sa.UniqueConstraint("node_type", "ref_id"),
    )
    op.create_table(
        "graph_edges",
        _id(),
        sa.Column("src", sa.Integer, sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("dst", sa.Integer, sa.ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rel_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("evidence_clause_id", sa.Integer, sa.ForeignKey("clauses.id", ondelete="SET NULL")),
        sa.UniqueConstraint("src", "dst", "rel_type"),
    )
    op.create_table(
        "impact_reports",
        _id(),
        sa.Column("comparison_id", sa.Integer, sa.ForeignKey("comparisons.id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_id", sa.Integer, sa.ForeignKey("clause_changes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("confirmed", JSONB, nullable=False),
        sa.Column("affected", JSONB, nullable=False),
        sa.Column("impacts", JSONB, nullable=False),
        sa.Column("actions", JSONB, nullable=False),
        sa.Column("evidence", JSONB, nullable=False),
        sa.Column("verified", sa.Boolean, nullable=False),
        sa.Column("model", sa.String(128), nullable=False),
        _now("created_at"),
    )
    op.create_index("ix_impact_reports_comparison", "impact_reports", ["comparison_id"])

    op.create_table(
        "jobs",
        _id(),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        _now("run_after"),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        _now("created_at"),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_jobs_status_created", "jobs", ["status", "created_at"])


def downgrade() -> None:
    for table in (
        "jobs", "impact_reports", "graph_edges", "graph_nodes", "clause_changes",
        "comparisons", "clauses", "document_versions", "documents", "users",
    ):
        op.drop_table(table)
