from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.agents.orchestrator import run_pipeline
from backend.api.websocket import broadcast_progress, progress_queues
from backend.config import get_settings
from backend.models.database import AuditRun, Base
from backend.models.schemas import MerchantInput, ScanRequest, ScanResponse

router = APIRouter(prefix="/api")

# In-memory job store (production would use Redis/DB)
_jobs: dict[str, dict] = {}


async def _get_engine():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    return engine


async def _run_scan_job(job_id: str, merchant_input: MerchantInput) -> None:
    """Background task: run the pipeline and store result."""
    _jobs[job_id]["status"] = "running"

    async def progress_callback(agent: str, message: str, pct: int, event_type: str = "progress"):
        await broadcast_progress(job_id, {
            "type": event_type,
            "agent": agent,
            "message": message,
            "progress": pct,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    await progress_callback("Orchestrator", "Starting compliance scan", 5)

    try:
        state = await run_pipeline(merchant_input, progress_fn=progress_callback)

        _jobs[job_id]["status"] = "completed"
        _jobs[job_id]["report"] = state.readiness_report
        _jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Persist to SQLite
        try:
            engine = await _get_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with async_session() as session:
                run = AuditRun(
                    job_id=job_id,
                    website_url=str(merchant_input.website_url),
                    status="completed",
                    overall_score=state.readiness_report.overall_score if state.readiness_report else 0,
                    grade=state.readiness_report.grade if state.readiness_report else "F",
                    report_json=json.dumps(state.readiness_report.model_dump()) if state.readiness_report else None,
                    completed_at=datetime.now(timezone.utc),
                )
                session.add(run)
                await session.commit()
            await engine.dispose()
        except Exception:
            pass  # DB persistence is non-critical

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
    progress_queues[job_id] = asyncio.Queue()
    asyncio.create_task(_run_scan_job(job_id, merchant_input))
    return ScanResponse(job_id=job_id, status="queued")


@router.get("/scan/{job_id}", response_model=ScanResponse)
async def get_scan(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    # Normalize legacy "error" status to "failed" for frontend compatibility
    status = job["status"]
    if status == "error":
        status = "failed"
    return ScanResponse(
        job_id=job_id,
        status=status,
        report=job.get("report"),
    )
