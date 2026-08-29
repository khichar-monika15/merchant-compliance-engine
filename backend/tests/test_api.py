"""API contract tests, including the durability path.

Completed scans used to live only in an unbounded in-memory dict: they 404'd after a restart
even though the run had been written to SQLite.
"""
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api import routes
from backend.main import create_app
from backend.models.schemas import ReadinessReport, ScoreComponent

_MERCHANT = {
    "website_url": "https://example.com",
    "pan_name": "Acme Private Limited",
    "gst_legal_name": "ACME PRIVATE LIMITED",
    "bank_account_name": "Acme Private Limited",
    "business_type": "ecommerce",
}


@pytest.fixture
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_jobs():
    routes._jobs.clear()
    yield
    routes._jobs.clear()


class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestScanValidation:
    def test_rejects_non_url(self, client):
        r = client.post("/api/scan", json={**_MERCHANT, "website_url": "not-a-url"})
        assert r.status_code == 422
        assert r.json()["detail"], "validation error must carry a detail the UI can show"

    def test_rejects_missing_field(self, client):
        payload = {k: v for k, v in _MERCHANT.items() if k != "pan_name"}
        assert client.post("/api/scan", json=payload).status_code == 422


class TestScanLookup:
    def test_unknown_job_is_404(self, client):
        assert client.get("/api/scan/does-not-exist").status_code == 404

    def test_in_memory_job_is_served(self, client):
        routes._jobs["job-1"] = {
            "status": "running", "report": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        body = client.get("/api/scan/job-1").json()
        assert body["status"] == "running"
        assert body["report"] is None

    def test_failed_scan_reports_its_reason(self, client):
        """A failed scan must say why over REST, not only on the WebSocket.

        The reason was stored server side and never returned, so reloading the page or opening
        the report URL directly turned 'Could not reach the site' into a bare 'failed'.
        """
        routes._jobs["job-failed"] = {
            "status": "failed",
            "error": "Could not reach http://127.0.0.1:4999/, net::ERR_CONNECTION_REFUSED",
            "report": None,
        }
        body = client.get("/api/scan/job-failed").json()

        assert body["status"] == "failed"
        assert body["report"] is None
        assert "ERR_CONNECTION_REFUSED" in body["error"]

    def test_successful_scan_has_no_error(self, client):
        routes._jobs["job-ok"] = {"status": "running", "report": None}
        assert client.get("/api/scan/job-ok").json()["error"] is None

    async def test_completed_scan_survives_eviction(self, client):
        """A scan dropped from memory must still be served from SQLite, not 404."""
        report = ReadinessReport(
            overall_score=72, grade="C",
            score_breakdown=[ScoreComponent(label="RBI Compliance", score=72, weight=1.0)],
            estimated_fix_time="1-2 days",
        )
        await routes._persist_run(
            "job-persisted",
            routes.MerchantInput(**_MERCHANT),
            type("S", (), {"readiness_report": report})(),
        )
        assert "job-persisted" not in routes._jobs  # never was in memory

        body = client.get("/api/scan/job-persisted").json()
        assert body["status"] == "completed"
        assert body["report"]["overall_score"] == 72
        assert body["report"]["grade"] == "C"

    async def test_failed_scan_reason_survives_eviction(self, client):
        """The reason a scan failed must outlive the in-memory job.

        Failures were never persisted, so an evicted failed scan 404'd and the reason was lost,
        while ScanResponse.error carried a comment promising it survived a reload.
        """
        await routes._persist_run(
            "job-failed-persisted",
            routes.MerchantInput(**_MERCHANT),
            None,
            status="failed",
            error="Could not reach http://127.0.0.1:4999, ERR_CONNECTION_REFUSED",
        )
        assert "job-failed-persisted" not in routes._jobs

        body = client.get("/api/scan/job-failed-persisted").json()
        assert body["status"] == "failed"
        assert body["report"] is None
        assert "ERR_CONNECTION_REFUSED" in body["error"]


class TestJobEviction:
    def test_finished_jobs_are_evicted_but_running_ones_survive(self):
        for i in range(routes._MAX_IN_MEMORY_JOBS + 10):
            routes._jobs[f"done-{i}"] = {
                "status": "completed", "report": None,
                "created_at": f"2026-01-01T00:{i:02d}:00",
            }
        routes._jobs["live"] = {
            "status": "running", "report": None, "created_at": "2020-01-01T00:00:00",
        }
        routes._evict_old_jobs()

        assert len(routes._jobs) <= routes._MAX_IN_MEMORY_JOBS + 1
        assert "live" in routes._jobs, "in-flight scan must never be evicted"

    def test_eviction_stops_at_an_in_flight_job(self):
        routes._jobs["oldest-running"] = {
            "status": "running", "report": None, "created_at": "2020-01-01T00:00:00",
        }
        for i in range(routes._MAX_IN_MEMORY_JOBS + 5):
            routes._jobs[f"done-{i}"] = {
                "status": "completed", "report": None, "created_at": f"2026-01-01T00:{i:02d}:00",
            }
        routes._evict_old_jobs()
        assert "oldest-running" in routes._jobs
