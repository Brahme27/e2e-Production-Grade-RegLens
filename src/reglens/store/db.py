"""Relational store (SQLite locally, Postgres in docker compose / AWS RDS).

Holds what must be queried, joined and updated: document versions and their validity,
the supersession graph, and (later phases) obligations, gap judgements, feedback.
Paragraph text lives in the processed JSON + the vector index.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    key: Mapped[str] = mapped_column(String(160), primary_key=True)  # "<doc_id>@<version>"
    doc_id: Mapped[str] = mapped_column(String(120), index=True)
    version: Mapped[str] = mapped_column(String(40))
    regulator: Mapped[str] = mapped_column(String(10), index=True)
    doc_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(Text)
    doc_number: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(Text)
    topics: Mapped[list[str]] = mapped_column(JSON)
    applies_to: Mapped[list[str]] = mapped_column(JSON)
    issue_date: Mapped[date | None] = mapped_column(Date)
    valid_from: Mapped[date | None] = mapped_column(Date, index=True)
    valid_to: Mapped[date | None] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(12), index=True)
    superseded_by: Mapped[str | None] = mapped_column(String(120))
    paragraph_count: Mapped[int] = mapped_column(Integer)
    content_sha: Mapped[str] = mapped_column(String(64))
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SupersessionEdge(Base):
    __tablename__ = "supersession_edges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(120), index=True)
    target: Mapped[str] = mapped_column(String(160), index=True)
    type: Mapped[str] = mapped_column(String(12))
    method: Mapped[str] = mapped_column(String(8))
    effective: Mapped[date | None] = mapped_column(Date)
    evidence: Mapped[str] = mapped_column(Text, default="")


class Obligation(Base):
    __tablename__ = "obligations"

    # "<run id>:<obligation key>": the same rule analysed in two runs (or for two firms)
    # must never share rows, reviews or overrides
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    obligation_key: Mapped[str] = mapped_column(String(64), index=True)
    impact_run: Mapped[str] = mapped_column(String(64), index=True)
    doc_key: Mapped[str] = mapped_column(String(160), index=True)
    source_ref: Mapped[str] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    actor: Mapped[str] = mapped_column(Text, default="")
    action: Mapped[str] = mapped_column(Text, default="")
    condition: Mapped[str] = mapped_column(Text, default="")
    deadline: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(12), default="medium")


class GapJudgement(Base):
    __tablename__ = "gap_judgements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    obligation_id: Mapped[str] = mapped_column(ForeignKey("obligations.id"), index=True)
    entity: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(20))  # covered | partially_covered | not_covered
    rationale: Mapped[str] = mapped_column(Text, default="")
    policy_refs: Mapped[list[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    review_status: Mapped[str] = mapped_column(String(12), default="pending")  # human review
    reviewer_note: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(String(64), index=True)
    score: Mapped[int] = mapped_column(Integer)  # +1 / -1
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(engine: Engine) -> Iterator[Session]:
    """A transaction: commit on success, roll back on any error."""
    factory = sessionmaker(engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
