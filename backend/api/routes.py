from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.agents.orchestrator import run_pipeline
from backend.api.websocket import broadcast_progress, finish_job, register_job
from backend.config import get_settings
from backend.models.database import AuditRun, Base
from backend.models.schemas import MerchantInput, ScanRequest, ScanResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# In-memory job store (production would use Redis/DB)
_jobs: dict[str, dict] = {}

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
        await broadcast_progress(job_id, {
            "type": "error",
            "agent": "Orchestrator",
            "message": f"Error: {e}",
            "progress": -1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    finally:
        finish_job(job_id)


async def _persist_run(job_id: str, merchant_input: MerchantInput, state) -> None:
    """Write the completed run to SQLite. Non-critical — a failure must not fail the scan."""
    try:
        engine = _get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with async_session() as session:
            session.add(AuditRun(
                job_id=job_id,
                website_url=str(merchant_input.website_url),
                status="completed",
                overall_score=state.readiness_report.overall_score,
                grade=state.readiness_report.grade,
                report_json=json.dumps(state.readiness_report.model_dump(mode="json")),
                completed_at=datetime.now(timezone.utc),
            ))
            await session.commit()
    except Exception as e:
        logger.warning("Audit trail persistence failed for job %s: %s", job_id, e)


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


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
    register_job(job_id)
    task = asyncio.create_task(_run_scan_job(job_id, merchant_input))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return ScanResponse(job_id=job_id, status="queued")


@router.get("/scan/{job_id}", response_model=ScanResponse)
async def get_scan(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return ScanResponse(
        job_id=job_id,
        status=job["status"],
        report=job.get("report"),
    )
