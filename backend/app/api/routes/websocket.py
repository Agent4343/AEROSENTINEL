from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from redis.asyncio import Redis

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

TELEMETRY_CHANNEL = "aerosentinel:telemetry"
DETECTIONS_CHANNEL = "aerosentinel:detections"
ALERTS_CHANNEL = "aerosentinel:alerts"

REDIS_URL = settings.redis_url


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(
            "WebSocket client connected. Total connections: %d",
            len(self._connections),
        )

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.remove(websocket)
        logger.info(
            "WebSocket client disconnected. Total connections: %d",
            len(self._connections),
        )

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
    """Subscribe to Redis pub-sub channels and broadcast messages to all
    connected WebSocket clients."""
    redis: Redis | None = None
    try:
        redis = Redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(*channels)
        logger.info("Redis pub-sub listener started on channels: %s", channels)

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
        logger.info("Redis listener cancelled")
    except Exception:
        logger.exception("Redis listener error")
    finally:
        if redis is not None:
            await redis.aclose()


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket) -> None:
    """Stream real-time drone telemetry and detection alerts to clients via
    Redis pub-sub."""
    await manager.connect(websocket)

    # Start the Redis listener if this is the first connection
    listener_task: asyncio.Task | None = None
    if manager.active_count == 1:
        listener_task = asyncio.create_task(
            _redis_listener(
                [TELEMETRY_CHANNEL, DETECTIONS_CHANNEL, ALERTS_CHANNEL]
            )
        )

    try:
        while True:
            # Keep the connection alive; handle incoming client messages
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                # Clients can send ping / subscribe messages
                if payload.get("type") == "ping":
                    await websocket.send_json({"event": "pong"})
            except json.JSONDecodeError:
                await websocket.send_json(
                    {"event": "error", "data": {"message": "Invalid JSON"}}
                )
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        if manager.active_count == 0 and listener_task is not None:
            listener_task.cancel()
    except Exception:
        manager.disconnect(websocket)
        if manager.active_count == 0 and listener_task is not None:
            listener_task.cancel()
