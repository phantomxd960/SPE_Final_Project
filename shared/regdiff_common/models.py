"""SQLAlchemy models (data design, Section 6).

The backend owns the schema through Alembic migrations; the ai-worker uses
the same models to read jobs and write results.
"""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

EMBEDDING_DIM = 384


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="admin")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    doc_code: Mapped[str] = mapped_column(String(64), unique=True)
    title: Mapped[str] = mapped_column(String(255))
    doc_type: Mapped[str] = mapped_column(String(32))  # regulation | policy | guideline
    authority: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document", order_by="DocumentVersion.uploaded_at"
    )


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_label"),
        UniqueConstraint("document_id", "sha256"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    version_label: Mapped[str] = mapped_column(String(64))
    effective_date: Mapped[date | None] = mapped_column(Date)
    file_name: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|processing|ready|failed
    error: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(255))  # title found in the file
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)  # header metadata: regulation, process, control
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="versions")
    clauses: Mapped[list["Clause"]] = relationship(back_populates="version", order_by="Clause.position")


class Clause(Base):
    __tablename__ = "clauses"

    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    clause_number: Mapped[str] = mapped_column(String(64))
    section: Mapped[str | None] = mapped_column(String(255))
    page: Mapped[int] = mapped_column(Integer, default=1)
    text: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    ocr_flag: Mapped[bool] = mapped_column(Boolean, default=False)

    version: Mapped[DocumentVersion] = relationship(back_populates="clauses")


class Comparison(Base):
    __tablename__ = "comparisons"

    id: Mapped[int] = mapped_column(primary_key=True)
    old_version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"))
    new_version_id: Mapped[int] = mapped_column(ForeignKey("document_versions.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed
    error: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    old_version: Mapped[DocumentVersion] = relationship(foreign_keys=[old_version_id])
    new_version: Mapped[DocumentVersion] = relationship(foreign_keys=[new_version_id])
    changes: Mapped[list["ClauseChange"]] = relationship(back_populates="comparison", order_by="ClauseChange.id")


class ClauseChange(Base):
    __tablename__ = "clause_changes"

    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(ForeignKey("comparisons.id", ondelete="CASCADE"))
    old_clause_id: Mapped[int | None] = mapped_column(ForeignKey("clauses.id", ondelete="SET NULL"))
    new_clause_id: Mapped[int | None] = mapped_column(ForeignKey("clauses.id", ondelete="SET NULL"))
    change_type: Mapped[str] = mapped_column(String(32))
    text_diff: Mapped[list] = mapped_column(JSONB, default=list)  # [[op, text], ...] word-level diff
    similarity: Mapped[float] = mapped_column(Float)
    numeric_changes: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)

    comparison: Mapped[Comparison] = relationship(back_populates="changes")
    old_clause: Mapped[Clause | None] = relationship(foreign_keys=[old_clause_id])
    new_clause: Mapped[Clause | None] = relationship(foreign_keys=[new_clause_id])


class GraphNode(Base):
    __tablename__ = "graph_nodes"
    __table_args__ = (UniqueConstraint("node_type", "ref_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    node_type: Mapped[str] = mapped_column(String(32))  # reg_clause|policy|policy_clause|process|control
    ref_id: Mapped[str] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(512))


class GraphEdge(Base):
    """`src` depends on `dst`; impact therefore flows from dst to src."""

    __tablename__ = "graph_edges"
    __table_args__ = (UniqueConstraint("src", "dst", "rel_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    src: Mapped[int] = mapped_column(ForeignKey("graph_nodes.id", ondelete="CASCADE"))
    dst: Mapped[int] = mapped_column(ForeignKey("graph_nodes.id", ondelete="CASCADE"))
    rel_type: Mapped[str] = mapped_column(String(32))  # REFERENCES|IMPLEMENTS|DEPENDS_ON|AFFECTS|MODIFIES
    status: Mapped[str] = mapped_column(String(16))  # confirmed | inferred
    confidence: Mapped[float] = mapped_column(Float)
    evidence_clause_id: Mapped[int | None] = mapped_column(ForeignKey("clauses.id", ondelete="SET NULL"))


class ImpactReport(Base):
    __tablename__ = "impact_reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    comparison_id: Mapped[int] = mapped_column(ForeignKey("comparisons.id", ondelete="CASCADE"))
    change_id: Mapped[int] = mapped_column(ForeignKey("clause_changes.id", ondelete="CASCADE"))
    summary: Mapped[str] = mapped_column(Text)
    confirmed: Mapped[dict] = mapped_column(JSONB, default=dict)  # deterministic facts of the change
    affected: Mapped[list] = mapped_column(JSONB, default=list)
    impacts: Mapped[list] = mapped_column(JSONB, default=list)
    actions: Mapped[list] = mapped_column(JSONB, default=list)
    evidence: Mapped[list] = mapped_column(JSONB, default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))  # ingest_version | compare
    status: Mapped[str] = mapped_column(String(16), default="queued")  # queued|running|done|failed
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
