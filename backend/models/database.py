from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class AuditRun(Base):
    __tablename__ = "audit_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    website_url: Mapped[str] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    overall_score: Mapped[int] = mapped_column(Integer, default=0)
    grade: Mapped[str] = mapped_column(String(2), default="F")
    report_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Why a failed run failed. Failures were not persisted at all, so a scan that could not
    # reach the site returned 404 once its in-memory job was evicted, and ScanResponse.error
    # only worked inside that window despite a comment promising it survived a reload.
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
