from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from claimsight_api.db import engine


class Base(DeclarativeBase):
    pass


class ClaimRow(Base):
    __tablename__ = "claims"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(String)
    provider_id: Mapped[str] = mapped_column(String)
    icd10: Mapped[str] = mapped_column(Text, default="[]")
    cpt: Mapped[str] = mapped_column(Text, default="[]")
    amount_usd: Mapped[float] = mapped_column(Float, default=0)
    service_date: Mapped[str] = mapped_column(String, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String, default="queued")
    recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    route: Mapped[str | None] = mapped_column(String, nullable=True)
    packet_json: Mapped[str] = mapped_column(Text, default="{}")
    phi_mapping: Mapped[str] = mapped_column(Text, default="{}")
    model_name: Mapped[str] = mapped_column(String, default="")
    prompt_version: Mapped[str] = mapped_column(String, default="")
    decided_by: Mapped[str | None] = mapped_column(String, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))
    token_used: Mapped[int] = mapped_column(Integer, default=0)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str] = mapped_column(String)
    entity_id: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[str] = mapped_column(Text, default="{}")


class EvalLabel(Base):
    __tablename__ = "eval_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    claim_id: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    actor: Mapped[str] = mapped_column(String)
    override: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )


def init_db() -> None:
    Base.metadata.create_all(engine)
