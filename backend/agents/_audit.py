"""Shared audit-log helpers.

Every agent times its work and appends exactly one AuditLogEntry, and every agent degrades to an
error entry rather than raising, so one failure cannot take down the parallel phase. Both are
project conventions; keeping the construction here means an agent cannot quietly skip either.
"""
from __future__ import annotations

from datetime import datetime, timezone

from backend.models.schemas import AuditLogEntry


def elapsed_ms(t0: datetime) -> float:
    return round((datetime.now(timezone.utc) - t0).total_seconds() * 1000, 1)


def audit_entry(t0: datetime, agent: str, action: str, result: str) -> AuditLogEntry:
    return AuditLogEntry(
        timestamp=t0.isoformat(),
        agent=agent,
        action=action,
        result=result,
        duration_ms=elapsed_ms(t0),
    )


def failure(t0: datetime, agent: str, action: str, exc: Exception) -> dict:
    """The partial state update an agent returns when it cannot complete."""
    return {
        "errors": [f"{agent} failed: {exc}"],
        "audit_log": [audit_entry(t0, agent, action, f"ERROR: {exc}")],
    }
