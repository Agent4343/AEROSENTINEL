from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

TELEMETRY_CHANNEL = "aerosentinel:telemetry"
DETECTIONS_CHANNEL = "aerosentinel:detections"
ALERTS_CHANNEL = "aerosentinel:alerts"
REDIS_URL = "redis://redis:6379/0"


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_json(message)
            except Exception:
                stale.append(ws)
        for ws in stale:
            self._connections.remove(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


async def _redis_listener(channels: list[str]) -> None:
    redis: Redis | None = None
    try:
        redis = Redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(*channels)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                data = {"raw": message["data"]}
            channel = message["channel"]
            event_type = "unknown"
            if channel == TELEMETRY_CHANNEL:
                event_type = "telemetry"
            elif channel == DETECTIONS_CHANNEL:
                event_type = "detection"
            elif channel == ALERTS_CHANNEL:
                event_type = "alert"
            await manager.broadcast({"event": event_type, "data": data})
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Redis listener error")
    finally:
        if redis is not None:
            await redis.aclose()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    listener_task: asyncio.Task | None = None
    if manager.active_count == 1:
        listener_task = asyncio.create_task(
            _redis_listener([TELEMETRY_CHANNEL, DETECTIONS_CHANNEL, ALERTS_CHANNEL])
        )
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("type") == "ping":
                    await websocket.send_json({"event": "pong"})
            except json.JSONDecodeError:
                await websocket.send_json({"event": "error", "data": {"message": "Invalid JSON"}})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if manager.active_count == 0 and listener_task is not None:
            listener_task.cancel()
    except Exception:
        manager.disconnect(websocket)
        if manager.active_count == 0 and listener_task is not None:
            listener_task.cancel()
