"""Schéma de données (M03). SQLAlchemy 2, SQLite en première intention."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSON, list[Any]: JSON}


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Organizer(Base, TimestampMixin):
    __tablename__ = "organizers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300))
    normalized_name: Mapped[str] = mapped_column(String(300), index=True, unique=True)
    website: Mapped[str | None] = mapped_column(String(500))
    country: Mapped[str | None] = mapped_column(String(2))
    legal_id: Mapped[str | None] = mapped_column(String(100))  # SIREN/RCS si trouvé
    reputation: Mapped[int] = mapped_column(Integer, default=0)  # -100..100, signalements
    contests: Mapped[list[Contest]] = relationship(back_populates="organizer")


class SourceConnector(Base, TimestampMixin):
    """Type de connecteur disponible (plugin) et sa configuration par défaut."""
    __tablename__ = "source_connectors"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    default_config: Mapped[dict[str, Any]] = mapped_column(default=dict)


class Source(Base, TimestampMixin):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(50))  # rss | html | aggregator:<slug>
    url: Mapped[str] = mapped_column(String(1000), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str | None] = mapped_column(String(5))
    country: Mapped[str | None] = mapped_column(String(2))
    config: Mapped[dict[str, Any]] = mapped_column(default=dict)
    tos_note: Mapped[str | None] = mapped_column(Text)
    trust: Mapped[int] = mapped_column(Integer, default=50)  # 0..100
    last_scan_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_status: Mapped[str | None] = mapped_column(String(200))
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    last_content_hash: Mapped[str | None] = mapped_column(String(64))


class Contest(Base, TimestampMixin):
    __tablename__ = "contests"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(String(1000))
    canonical_url: Mapped[str] = mapped_column(String(1000), index=True)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)  # dédup titre+organisateur
    organizer_id: Mapped[int | None] = mapped_column(ForeignKey("organizers.id"))
    description: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20), default="new", index=True)
    category: Mapped[str | None] = mapped_column(String(30), index=True)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, index=True)
    entry_limit: Mapped[str | None] = mapped_column(String(200))
    entry_method: Mapped[str | None] = mapped_column(String(50))  # form, social, email, sms, mail, instant
    game_type: Mapped[str | None] = mapped_column(String(20), index=True)  # instant_win, creative, quiz, social, draw
    free_status: Mapped[str] = mapped_column(String(20), default="unknown")
    fr_eligible: Mapped[str] = mapped_column(String(10), default="unknown")
    participation_mode: Mapped[str] = mapped_column(String(10), default="manual")
    reliability_score: Mapped[int | None] = mapped_column(Integer)
    interest_score: Mapped[int | None] = mapped_column(Integer)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(default=dict)
    justifications: Mapped[list[Any]] = mapped_column(default=list)
    needs_human_reason: Mapped[str | None] = mapped_column(Text)
    flags: Mapped[list[Any]] = mapped_column(default=list)  # captcha, login_required, social_only...
    total_prize_value_eur: Mapped[float | None] = mapped_column(Float)
    prize_summary: Mapped[str | None] = mapped_column(String(500))
    personal_interest: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
    merged_into_id: Mapped[int | None] = mapped_column(ForeignKey("contests.id"))
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime)

    organizer: Mapped[Organizer | None] = relationship(back_populates="contests")
    rules: Mapped[list[ContestRule]] = relationship(back_populates="contest", cascade="all, delete-orphan", order_by="ContestRule.id.desc()")
    eligibility: Mapped[Eligibility | None] = relationship(back_populates="contest", cascade="all, delete-orphan", uselist=False)
    prizes: Mapped[list[Prize]] = relationship(back_populates="contest", cascade="all, delete-orphan")
    answers: Mapped[list[Answer]] = relationship(back_populates="contest", cascade="all, delete-orphan")
    sightings: Mapped[list[ContestSighting]] = relationship(back_populates="contest", cascade="all, delete-orphan")
    participations: Mapped[list[Participation]] = relationship(back_populates="contest")
    policy: Mapped[AutomationPolicy | None] = relationship(back_populates="contest", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (Index("ix_contests_status_end", "status", "end_date"),)


class ContestSighting(Base):
    """Provenance : chaque fois qu'une source a présenté ce concours."""
    __tablename__ = "contest_sightings"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"))
    source_url: Mapped[str] = mapped_column(String(1000))
    raw: Mapped[dict[str, Any]] = mapped_column(default=dict)
    seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    contest: Mapped[Contest] = relationship(back_populates="sightings")
    source: Mapped[Source | None] = relationship()
    __table_args__ = (UniqueConstraint("contest_id", "source_id", "source_url"),)


class ContestRule(Base):
    __tablename__ = "contest_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"), index=True)
    url: Mapped[str | None] = mapped_column(String(1000))
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    origin: Mapped[str] = mapped_column(String(20), default="fetched")  # fetched | user | page
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    analysis: Mapped[dict[str, Any]] = mapped_column(default=dict)  # cache d'analyse
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime)
    analyzer_version: Mapped[str | None] = mapped_column(String(20))
    contest: Mapped[Contest] = relationship(back_populates="rules")


class Eligibility(Base):
    __tablename__ = "eligibility"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"), unique=True)
    min_age: Mapped[int | None] = mapped_column(Integer)
    countries_allowed: Mapped[list[Any]] = mapped_column(default=list)
    countries_excluded: Mapped[list[Any]] = mapped_column(default=list)
    residence_required: Mapped[bool | None] = mapped_column(Boolean)
    fr_eligible: Mapped[str] = mapped_column(String(10), default="unknown")
    evidence: Mapped[str | None] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(50), default="rule")
    contest: Mapped[Contest] = relationship(back_populates="eligibility")


class Prize(Base):
    __tablename__ = "prizes"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(30), default="other")
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    value: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(3))
    value_eur: Mapped[float | None] = mapped_column(Float)
    fees_note: Mapped[str | None] = mapped_column(Text)
    contest: Mapped[Contest] = relationship(back_populates="prizes")


class Answer(Base, TimestampMixin):
    """Base de réponses aux questionnaires, avec provenance et vérification."""
    __tablename__ = "answers"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int | None] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"), index=True)
    question: Mapped[str] = mapped_column(Text)
    question_norm: Mapped[str] = mapped_column(String(500), index=True)
    answer: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(200))  # nom de la source / "user"
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    votes: Mapped[int] = mapped_column(Integer, default=1)  # nb de sources concordantes
    contest: Mapped[Contest | None] = relationship(back_populates="answers")


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profile"
    id: Mapped[int] = mapped_column(primary_key=True)
    encrypted_data: Mapped[str] = mapped_column(Text)  # JSON chiffré Fernet


class Consent(Base, TimestampMixin):
    __tablename__ = "consents"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str | None] = mapped_column(Text)  # texte accepté (preuve)


class AutomationPolicy(Base, TimestampMixin):
    __tablename__ = "automation_policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id", ondelete="CASCADE"), unique=True)
    mode: Mapped[str] = mapped_column(String(10), default="manual")
    reasons: Mapped[list[Any]] = mapped_column(default=list)
    automation_forbidden_by_rules: Mapped[bool | None] = mapped_column(Boolean)
    max_entries: Mapped[int | None] = mapped_column(Integer)
    period: Mapped[str | None] = mapped_column(String(20))  # once | daily | weekly
    contest: Mapped[Contest] = relationship(back_populates="policy")


class BrowserSession(Base, TimestampMixin):
    __tablename__ = "browser_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    domain: Mapped[str] = mapped_column(String(300), index=True)
    profile_dir: Mapped[str] = mapped_column(String(500))  # profil Playwright isolé par domaine
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime)


class Participation(Base, TimestampMixin):
    __tablename__ = "participations"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int] = mapped_column(ForeignKey("contests.id"), index=True)
    mode: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="prepared", index=True)
    period_key: Mapped[str] = mapped_column(String(20))  # anti double participation : "once" / "2026-11-20" / "2026-W47"
    prepared_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)
    error: Mapped[str | None] = mapped_column(Text)
    time_spent_minutes: Mapped[float | None] = mapped_column(Float)
    contest: Mapped[Contest] = relationship(back_populates="participations")
    proofs: Mapped[list[ParticipationProof]] = relationship(back_populates="participation", cascade="all, delete-orphan")
    __table_args__ = (Index("ix_part_contest_period", "contest_id", "period_key"),)


class ParticipationProof(Base):
    __tablename__ = "participation_proofs"
    id: Mapped[int] = mapped_column(primary_key=True)
    participation_id: Mapped[int] = mapped_column(ForeignKey("participations.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # screenshot | note | email | html
    path: Mapped[str | None] = mapped_column(String(500))
    sha256: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    participation: Mapped[Participation] = relationship(back_populates="proofs")


class Result(Base, TimestampMixin):
    __tablename__ = "results"
    id: Mapped[int] = mapped_column(primary_key=True)
    contest_id: Mapped[int | None] = mapped_column(ForeignKey("contests.id"), index=True)
    participation_id: Mapped[int | None] = mapped_column(ForeignKey("participations.id"))
    outcome: Mapped[str] = mapped_column(String(10), default="pending")
    message_text: Mapped[str | None] = mapped_column(Text)
    sender: Mapped[str | None] = mapped_column(String(300))
    received_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    phishing_score: Mapped[int] = mapped_column(Integer, default=0)
    phishing_flags: Mapped[list[Any]] = mapped_column(default=list)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    contest: Mapped[Contest | None] = relationship()


class Claim(Base, TimestampMixin):
    __tablename__ = "claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[int] = mapped_column(ForeignKey("results.id", ondelete="CASCADE"), index=True)
    prize_name: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default="to_claim")
    deadline: Mapped[date | None] = mapped_column(Date)
    fees_eur: Mapped[float | None] = mapped_column(Float)
    value_eur: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    result: Mapped[Result] = relationship()


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), default="scan")
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|ok|error|skipped|interrupted
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    found: Mapped[int] = mapped_column(Integer, default=0)
    new: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(default=dict)  # reprise après interruption
    source: Mapped[Source | None] = relationship()


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str | None] = mapped_column(Text)
    contest_id: Mapped[int | None] = mapped_column(ForeignKey("contests.id", ondelete="SET NULL"))
    dedup_key: Mapped[str | None] = mapped_column(String(200), unique=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(50))  # user | scheduler | discovery | llm | system
    action: Mapped[str] = mapped_column(String(100))
    detail: Mapped[dict[str, Any]] = mapped_column(default=dict)


class AppSetting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(default=dict)


class FetchCache(Base):
    """Cache HTTP / détection de changement des pages (règlements, listes)."""
    __tablename__ = "fetch_cache"
    url: Mapped[str] = mapped_column(String(1000), primary_key=True)
    status: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    etag: Mapped[str | None] = mapped_column(String(300))
    last_modified: Mapped[str | None] = mapped_column(String(100))
    body_path: Mapped[str | None] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
