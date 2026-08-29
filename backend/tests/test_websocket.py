"""Progress broadcast must not let one listener hold up a scan."""
import asyncio
import json

import pytest

from backend.api import websocket as ws


@pytest.fixture(autouse=True)
def fast_send_timeout(monkeypatch):
    """Drive the bound rather than waiting it out, so the guard stays real and the suite stays fast."""
    monkeypatch.setattr(ws, "_SEND_TIMEOUT_SECONDS", 0.2)


@pytest.fixture(autouse=True)
def clean():
    ws.progress_history.clear()
    ws._connections.clear()
    ws._finished.clear()
    ws._locks.clear()
    yield
    ws.progress_history.clear()
    ws._connections.clear()
    ws._finished.clear()
    ws._locks.clear()


class _Socket:
    def __init__(self, stall: float = 0.0):
        self.stall = stall
        self.sent: list[str] = []

    async def send_text(self, text: str):
        if self.stall:
            await asyncio.sleep(self.stall)
        self.sent.append(text)


class TestOneStalledClientCannotBlockTheScan:
    """`broadcast_progress` awaited each socket in turn, from inside every graph node.

    A suspended browser tab whose TCP window is full makes `send_text` stop returning, so the
    LangGraph run itself stalled behind one dead reader until the pipeline timeout killed the
    scan. Every other listener also missed the event, because the loop never reached them.
    """

    async def test_a_healthy_listener_is_not_held_up_by_a_stalled_one(self):
        ws.register_job("job-1")
        stalled, healthy = _Socket(stall=10.0), _Socket()
        ws._connections["job-1"] = [stalled, healthy]

        await asyncio.wait_for(ws.broadcast_progress("job-1", {"type": "progress"}), timeout=2)

        assert healthy.sent, "the healthy listener never received the event"

    async def test_broadcast_returns_promptly(self):
        ws.register_job("job-2")
        ws._connections["job-2"] = [_Socket(stall=10.0)]

        loop = asyncio.get_running_loop()
        start = loop.time()
        await asyncio.wait_for(ws.broadcast_progress("job-2", {"type": "progress"}), timeout=2)
        assert loop.time() - start < 1, "broadcast waited on a stalled socket"

    async def test_history_is_still_recorded(self):
        ws.register_job("job-3")
        ws._connections["job-3"] = [_Socket(stall=10.0)]
        await asyncio.wait_for(ws.broadcast_progress("job-3", {"type": "progress"}), timeout=2)
        assert len(ws.progress_history["job-3"]) == 1


class TestLocksDoNotGrowForever:
    """`_lock` created an entry for any job id a client connected with, and only
    `register_job` eviction ever removed one, sweeping only ids it had registered."""

    async def test_an_unregistered_job_leaves_no_lock_behind(self):
        for i in range(ws._MAX_TRACKED_JOBS * 3):
            await ws.broadcast_progress(f"never-registered-{i}", {"type": "progress"})

        assert len(ws._locks) <= ws._MAX_TRACKED_JOBS, (
            f"_locks holds {len(ws._locks)} entries for jobs that were never registered"
        )
