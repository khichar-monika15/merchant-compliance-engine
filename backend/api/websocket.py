from __future__ import annotations

import asyncio
import json
from collections import OrderedDict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

_PING_INTERVAL_SECONDS = 30
_MAX_TRACKED_JOBS = 50
# How long one listener may hold up a broadcast before it is skipped for this message. Sends stay
# awaited, rather than fired and forgotten, so a client still receives progress events in order;
# this only bounds what a stalled one can cost the scan.
_SEND_TIMEOUT_SECONDS = 2

# job_id → ordered progress history, replayed to clients that connect mid-scan or after it
progress_history: "OrderedDict[str, list[dict]]" = OrderedDict()

# job_id → active WebSocket connections
_connections: dict[str, list[WebSocket]] = {}

# Jobs that have finished — the socket loop exits instead of pinging forever
_finished: set[str] = set()

# Serialises "append to history" against "replay then subscribe" so no event is lost or doubled
_locks: dict[str, asyncio.Lock] = {}


def _lock(job_id: str) -> asyncio.Lock:
    return _locks.setdefault(job_id, asyncio.Lock())


def _drop_lock_if_untracked(job_id: str) -> None:
    """Release the lock for a job nothing is tracking any more.

    `_lock` creates an entry for any job id a caller mentions, and only `register_job` eviction
    ever removed one, sweeping only ids it had itself registered. Anything connecting or
    broadcasting with stale ids grew this dict for the lifetime of the process.
    """
    if job_id not in progress_history and not _connections.get(job_id):
        _locks.pop(job_id, None)
        _finished.discard(job_id)


def register_job(job_id: str) -> None:
    """Start tracking a job, evicting the oldest once the retention cap is reached."""
    progress_history[job_id] = []
    while len(progress_history) > _MAX_TRACKED_JOBS:
        old_id, _ = progress_history.popitem(last=False)
        _connections.pop(old_id, None)
        _locks.pop(old_id, None)
        _finished.discard(old_id)


def finish_job(job_id: str) -> None:
    """Mark a job terminal so open sockets stop pinging and close."""
    _finished.add(job_id)


async def broadcast_progress(job_id: str, message: dict) -> None:
    """Record a progress message and push it to every live listener.

    Delivery is concurrent and bounded. This awaited each socket in turn, and the progress
    callback is awaited from inside every graph node, so one suspended browser tab whose TCP
    window had filled stopped `send_text` from returning and stalled the scan itself until the
    pipeline timeout killed it. Every listener after the stalled one missed the event too.

    A listener that cannot keep up loses this message rather than the scan losing the listener:
    the socket stays open and the client catches up from `progress_history` on reconnect.
    """
    async with _lock(job_id):
        if job_id in progress_history:
            progress_history[job_id].append(message)
        listeners = list(_connections.get(job_id, []))

    if not listeners:
        _drop_lock_if_untracked(job_id)
        return

    payload = json.dumps(message)

    async def _send(ws: WebSocket) -> None:
        try:
            await asyncio.wait_for(ws.send_text(payload), timeout=_SEND_TIMEOUT_SECONDS)
        except Exception:
            pass  # slow or gone; the socket's own finally block removes it

    await asyncio.gather(*(_send(ws) for ws in listeners))


@router.websocket("/ws/scan/{job_id}")
async def scan_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()

    # Replay history and subscribe atomically, so an event arriving in between is neither
    # dropped nor delivered twice
    async with _lock(job_id):
        backlog = list(progress_history.get(job_id, []))
        _connections.setdefault(job_id, []).append(websocket)

    try:
        for msg in backlog:
            await websocket.send_text(json.dumps(msg))

        # An id nobody registered is never marked finished, so this used to ping it forever.
        if job_id not in progress_history:
            await websocket.send_text(json.dumps({"type": "error", "message": "unknown job"}))
            return

        while job_id not in _finished:
            await asyncio.sleep(_PING_INTERVAL_SECONDS)
            if job_id in _finished:
                break
            await websocket.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        pass
    finally:
        connections = _connections.get(job_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            _connections.pop(job_id, None)
        _drop_lock_if_untracked(job_id)
