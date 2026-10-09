"""Persistence. JSON columns keep the audit trail simple and work on sqlite (dev) and Postgres (demo).

Embeddings are computed in memory at match time (dozens of evidence records), so pgvector is not needed yet;
add a vector column to SupplierEvidence if the evidence set grows.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from .config import get_settings
from .enums import JobStatus


def _id() -> str:
    return uuid.uuid4().hex[:12]


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analysis"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    status: Mapped[str] = mapped_column(String, default=JobStatus.PENDING.value)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    supplier_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # warnings, timings, coverage
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    documents: Mapped[list["Document"]] = relationship(cascade="all, delete-orphan")
    requirements: Mapped[list["RequirementRow"]] = relationship(cascade="all, delete-orphan")
    risks: Mapped[list["RiskRow"]] = relationship(cascade="all, delete-orphan")
    contradictions: Mapped[list["ContradictionRow"]] = relationship(cascade="all, delete-orphan")
    score: Mapped["ScoreRow | None"] = relationship(cascade="all, delete-orphan", uselist=False)
    model_runs: Mapped[list["ModelRun"]] = relationship(cascade="all, delete-orphan")


class Document(Base):
    __tablename__ = "document"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis.id"))
    filename: Mapped[str] = mapped_column(String)
    size: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String)
    storage_path: Mapped[str] = mapped_column(String)
    chunks: Mapped[list["DocumentChunk"]] = relationship(cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunk"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("document.id"))
    page_number: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    extraction_method: Mapped[str] = mapped_column(String)


class RequirementRow(Base):
    """Requirement + its compliance result in one row; `data` holds the canonical Requirement JSON."""
    __tablename__ = "requirement"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis.id"))
    requirement_id: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    mandatory_level: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)  # Requirement
    result: Mapped[dict] = mapped_column(JSON)  # ComplianceResult
    evidence_candidates: Mapped[list] = mapped_column(JSON, default=list)  # [{evidence, score}]


class RiskRow(Base):
    __tablename__ = "risk_item"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis.id"))
    data: Mapped[dict] = mapped_column(JSON)


class ContradictionRow(Base):
    __tablename__ = "contradiction"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis.id"))
    data: Mapped[dict] = mapped_column(JSON)


class ScoreRow(Base):
    __tablename__ = "score_snapshot"
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis.id"), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)


class ModelRun(Base):
    __tablename__ = "model_run"
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analysis.id"))
    stage: Mapped[str] = mapped_column(String)
    data: Mapped[dict] = mapped_column(JSON)  # model, prompt_version, request_id, usage, response


_engine = None
_Session = None


def get_session():
    global _engine, _Session
    if _engine is None:
        url = get_settings().database_url
        _engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {})
        Base.metadata.create_all(_engine)
        _Session = sessionmaker(_engine, expire_on_commit=False)
    return _Session()
