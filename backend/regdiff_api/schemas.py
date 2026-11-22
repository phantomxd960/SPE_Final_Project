"""Request and response models of the REST API."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DocType = Literal["regulation", "policy", "guideline"]


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---- auth
class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$")
    password: str = Field(min_length=1, max_length=255)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(_Orm):
    id: int
    email: str
    role: str


# ---- documents
class VersionOut(_Orm):
    id: int
    version_label: str
    effective_date: date | None
    file_name: str
    status: str
    error: str | None
    uploaded_at: datetime
    clause_count: int = 0


class DocumentOut(_Orm):
    id: int
    doc_code: str
    title: str
    doc_type: str
    authority: str | None
    versions: list[VersionOut] = []


class UploadResponse(BaseModel):
    document: DocumentOut
    version: VersionOut
    job_id: int


class ClauseOut(_Orm):
    id: int
    clause_number: str
    section: str | None
    page: int
    text: str


class ClauseDetail(ClauseOut):
    doc_code: str
    doc_title: str
    doc_type: str
    version_label: str


# ---- comparisons
class ComparisonCreate(BaseModel):
    old_version_id: int
    new_version_id: int


class ComparisonOut(BaseModel):
    id: int
    status: str
    error: str | None
    doc_code: str
    doc_title: str
    old_version: str
    new_version: str
    created_at: datetime
    finished_at: datetime | None
    counts: dict[str, int] = {}
    job_id: int | None = None


class ChangeOut(BaseModel):
    id: int
    change_type: str
    similarity: float
    confidence: float
    numeric_changes: list[dict]
    text_diff: list[list[str]]
    old_clause: ClauseOut | None
    new_clause: ClauseOut | None
    report_id: int | None


# ---- reports, search, jobs
class ReportOut(_Orm):
    id: int
    comparison_id: int
    change_id: int
    summary: str
    confirmed: dict
    affected: list[dict]
    impacts: list[dict]
    actions: list[dict]
    evidence: list[dict]
    verified: bool
    model: str
    created_at: datetime


class SearchHitOut(BaseModel):
    clause_id: int
    doc_code: str
    doc_title: str
    doc_type: str
    version_label: str
    clause_number: str
    section: str | None
    page: int
    text: str
    score: float


class JobOut(_Orm):
    id: int
    type: str
    status: str
    attempts: int
    error: str | None
    created_at: datetime
    finished_at: datetime | None


class VersionInfo(BaseModel):
    service: str
    build_number: str
    git_commit: str
    build_time: str
