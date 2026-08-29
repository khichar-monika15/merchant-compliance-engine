from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.agents.orchestrator import run_pipeline
from backend.api import websocket
from backend.api.websocket import broadcast_progress, finish_job, register_job
from backend.config import get_settings
from backend.models.database import AuditRun, Base
from backend.models.schemas import MerchantInput, ReadinessReport, ScanRequest, ScanResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# In-memory job store for live scans; completed runs also persist to SQLite (production
# would use Redis/DB for both)
_jobs: dict[str, dict] = {}
# Matched to the websocket module's history cap. These disagreed at 100 and 50, so a job could
# still be in `_jobs` with its progress history already evicted, and a client reconnecting to it
# replayed nothing while the job looked live.
_MAX_IN_MEMORY_JOBS = websocket._MAX_TRACKED_JOBS

# Strong references to running scans — the event loop only holds weak ones,
# so without this a task can be garbage collected mid-scan
_running_tasks: set[asyncio.Task] = set()

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, echo=False)
    return _engine


async def _run_scan_job(job_id: str, merchant_input: MerchantInput) -> None:
    """Background task: run the pipeline and store result."""
    _jobs[job_id]["status"] = "running"

    async def progress_callback(
        agent: str, message: str, pct: int, event_type: str = "progress", done: bool = False
    ):
        await broadcast_progress(job_id, {
            "type": event_type,
            "agent": agent,
            "message": message,
            "progress": pct,
            "done": done,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    await progress_callback("Orchestrator", "Starting compliance scan", 5)

    try:
        state = await run_pipeline(merchant_input, progress_fn=progress_callback)

        # A pipeline that ran to the end without producing a report is a failure, not a success
        if state.readiness_report is None:
            reason = "; ".join(state.errors) or "Pipeline produced no report"
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = reason
            await _persist_run(job_id, merchant_input, state, status="failed", error=reason)
            await progress_callback("Orchestrator", f"Error: {reason}", -1, event_type="error")
            return

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["report"] = state.readiness_report
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

        await _persist_run(job_id, merchant_input, state)
        await progress_callback("Complete", "Scan complete", 100, event_type="complete")

    except Exception as e:
        _jobs[job_id]["status"] = "failed"
        _jobs[job_id]["error"] = str(e)
        await _persist_run(job_id, merchant_input, None, status="failed", error=str(e))
        await broadcast_progress(job_id, {
            "type": "error",
            "agent": "Orchestrator",
            "message": f"Error: {e}",
            "progress": -1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    finally:
        finish_job(job_id)


async def _persist_run(
    job_id: str,
    merchant_input: MerchantInput,
    state,
    status: str = "completed",
    error: str | None = None,
) -> None:
    """Write the run to SQLite. Non-critical: a failure here must not fail the scan.

    Failed runs are written too. They used not to be, so once the in-memory job was evicted a
    failed scan returned 404 rather than the reason it failed.
    """
    try:
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        report = state.readiness_report if state is not None else None
        async with async_session() as session:
            session.add(AuditRun(
                job_id=job_id,
                website_url=str(merchant_input.website_url),
                status=status,
                overall_score=report.overall_score if report else 0,
                grade=report.grade if report else "F",
                report_json=json.dumps(report.model_dump(mode="json")) if report else None,
                error=error,
                completed_at=datetime.now(timezone.utc),
            ))
            await session.commit()
    except Exception as e:
        logger.warning("Audit trail persistence failed for job %s: %s", job_id, e)


def _evict_old_jobs() -> None:
    """Bound the in-memory store, oldest finished scan first.

    In-flight scans are skipped rather than stopping the sweep, so one long-running job cannot
    block eviction entirely. Evicted scans are still served from SQLite.
    """
    finished = sorted(
        (j for j, v in _jobs.items() if v["status"] not in ("queued", "running")),
        key=lambda j: _jobs[j]["created_at"],
    )
    for job_id in finished:
        if len(_jobs) <= _MAX_IN_MEMORY_JOBS:
            return
        del _jobs[job_id]


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/knowledge")
async def knowledge_base():
    """The rules the engine applies, served from the files the agents load.

    The public checks page renders this rather than restating the rules, so the documentation
    cannot drift from the behaviour the way a hand written page would.
    """
    from backend import knowledge
    from backend.agents.report_generator import _GRADE_THRESHOLDS, _SCORE_LABELS, _WEIGHTS

    rbi, pci = knowledge.rbi_document(), knowledge.pci_document()
    scripts, stacks = knowledge.script_risk_document(), knowledge.tech_stack_document()
    return {
        "rbi": {
            "version": rbi["version"],
            "source": rbi["source"],
            "checks": knowledge.rbi_checks(),
        },
        "pci": {
            "version": pci["version"],
            "source": pci["source"],
            "checks": knowledge.pci_checks(),
            "payment_page_patterns": knowledge.payment_page_patterns(),
        },
        # PCI-003 classifies third-party scripts by domain. Serving the taxonomy is what makes
        # that check inspectable rather than a card with a severity badge and nothing behind it.
        "script_risk": {
            "version": scripts["version"],
            "last_updated": scripts["last_updated"],
            "notes": scripts["notes"],
            "low_risk": scripts["low_risk"],
            "medium_risk": scripts["medium_risk"],
            "high_risk_indicators": scripts["high_risk_indicators"],
        },
        "stacks": stacks["stacks"],
        "scoring": {
            # Labels come from the scorer so the published weights cannot be attached to
            # different names than the ones the report uses.
            "weights": {_SCORE_LABELS[key]: weight for key, weight in _WEIGHTS.items()},
            "grades": [{"grade": g, "min_score": t} for t, g in _GRADE_THRESHOLDS],
        },
    }


@router.post("/scan", response_model=ScanResponse)
async def start_scan(request: ScanRequest):
    job_id = str(uuid.uuid4())
    merchant_input = MerchantInput(
        website_url=request.website_url,
        pan_name=request.pan_name,
        gst_legal_name=request.gst_legal_name,
        bank_account_name=request.bank_account_name,
        business_type=request.business_type,
    )
    _jobs[job_id] = {
        "status": "queued",
        "merchant_input": merchant_input,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "report": None,
    }
    _evict_old_jobs()
    register_job(job_id)
    task = asyncio.create_task(_run_scan_job(job_id, merchant_input))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return ScanResponse(job_id=job_id, status="queued")


async def _load_persisted_report(job_id: str) -> ScanResponse | None:
    """Serve a completed scan from SQLite when it is no longer in memory.

    Without this, every completed scan 404s after a restart or once evicted, even though the
    run was persisted.
    """
    try:
        async_session = sessionmaker(_get_engine(), class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            row = (await session.execute(
                select(AuditRun).where(AuditRun.job_id == job_id)
            )).scalar_one_or_none()
    except Exception as e:
        logger.warning("Audit trail lookup failed for job %s: %s", job_id, e)
        return None

    if row is None:
        return None
    report = ReadinessReport.model_validate(json.loads(row.report_json)) if row.report_json else None
    return ScanResponse(job_id=job_id, status=row.status, report=report, error=row.error)


@router.get("/scan/{job_id}", response_model=ScanResponse)
async def get_scan(job_id: str):
    job = _jobs.get(job_id)
    if job:
        return ScanResponse(
            job_id=job_id,
            status=job["status"],
            report=job.get("report"),
            error=job.get("error"),
        )

    persisted = await _load_persisted_report(job_id)
    if persisted:
        return persisted

    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
