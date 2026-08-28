from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# job_id → asyncio.Queue of progress dicts
progress_queues: dict[str, asyncio.Queue] = {}

# job_id → list of active WebSocket connections
_connections: dict[str, list[WebSocket]] = {}


async def broadcast_progress(job_id: str, message: dict) -> None:
    """Push a progress message to all WebSocket listeners and the queue for latecomers."""
    queue = progress_queues.get(job_id)
    if queue:
        await queue.put(message)

    for ws in _connections.get(job_id, []):
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            pass


@router.websocket("/ws/scan/{job_id}")
async def scan_progress_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()

    if job_id not in _connections:
        _connections[job_id] = []
    _connections[job_id].append(websocket)

    # Drain any existing queue messages (for reconnecting clients)
    queue = progress_queues.get(job_id)
    if queue:
        while not queue.empty():
            try:
                msg = queue.get_nowait()
                await websocket.send_text(json.dumps(msg))
            except Exception:
                break

    try:
        while True:
            # Keep connection alive; messages arrive via broadcast_progress
            await asyncio.sleep(1)
            try:
                await websocket.send_text(json.dumps({"type": "ping"}))
            except Exception:
                break
    except WebSocketDisconnect:
        pass
    finally:
        connections = _connections.get(job_id, [])
        if websocket in connections:
            connections.remove(websocket)
