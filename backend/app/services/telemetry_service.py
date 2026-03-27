"""TelemetryService -- ingest MQTT telemetry, cache, and fan-out via Redis."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

import redis.asyncio as redis

logger = logging.getLogger("aerosentinel.telemetry")


# ---------------------------------------------------------------------------
# Telemetry record
# ---------------------------------------------------------------------------

@dataclass
class DroneTelemetry:
    """Structured snapshot of a drone's OSD telemetry."""

    gateway_sn: str
    device_sn: str
    timestamp: float = 0.0

    # Position
    latitude: float = 0.0
    longitude: float = 0.0
    altitude: float = 0.0  # AGL metres
    height: float = 0.0  # ellipsoid height

    # Attitude
    heading: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0

    # Velocity
    speed_x: float = 0.0
    speed_y: float = 0.0
    speed_z: float = 0.0
    horizontal_speed: float = 0.0

    # Gimbal
    gimbal_pitch: float = 0.0
    gimbal_yaw: float = 0.0
    gimbal_roll: float = 0.0

    # Battery
    battery_percent: int = 100
    battery_voltage: float = 0.0
    battery_temperature: float = 0.0

    # Status
    flight_mode: int = 0
    gps_signal_level: int = 0
    satellites: int = 0
    wind_speed: float = 0.0
    wind_direction: float = 0.0
    is_flying: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DroneStatus:
    """Tracks high-level status for a single drone."""

    ONLINE = "online"
    OFFLINE = "offline"
    IN_FLIGHT = "in_flight"
    RETURNING = "returning"
    IDLE = "idle"

    def __init__(self, device_sn: str) -> None:
        self.device_sn = device_sn
        self.status: str = self.OFFLINE
        self.last_seen: float = 0.0
        self.mission_id: Optional[str] = None

    def update_from_telemetry(self, telem: DroneTelemetry) -> None:
        self.last_seen = time.time()
        if telem.is_flying:
            self.status = self.IN_FLIGHT
        else:
            self.status = self.IDLE


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

_OSD_KEY_MAP = {
    "latitude": "latitude",
    "longitude": "longitude",
    "height": "altitude",
    "elevation": "height",
    "attitude_head": "heading",
    "attitude_pitch": "pitch",
    "attitude_roll": "roll",
    "vx": "speed_x",
    "vy": "speed_y",
    "vz": "speed_z",
    "horizontal_speed": "horizontal_speed",
    "gimbal_pitch": "gimbal_pitch",
    "gimbal_yaw": "gimbal_yaw",
    "gimbal_roll": "gimbal_roll",
    "battery_percentage": "battery_percent",
    "voltage": "battery_voltage",
    "battery_temperature": "battery_temperature",
    "mode_code": "flight_mode",
    "gear": "is_flying",
    "gps_signal": "gps_signal_level",
    "satellites_number": "satellites",
    "wind_speed": "wind_speed",
    "wind_direction": "wind_direction",
}


class TelemetryService:
    """Processes raw DJI Cloud API telemetry, caches the latest state, and
    publishes updates to Redis for WebSocket fan-out."""

    REDIS_CHANNEL = "aerosentinel:telemetry"
    STALE_THRESHOLD_S = 30.0

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis: Optional[redis.Redis] = None
        self._redis_url = redis_url
        # In-memory caches keyed by device_sn
        self._latest: Dict[str, DroneTelemetry] = {}
        self._status: Dict[str, DroneStatus] = {}

    async def start(self) -> None:
        """Initialise the Redis connection."""
        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        logger.info("TelemetryService started (redis=%s)", self._redis_url)

    async def stop(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        logger.info("TelemetryService stopped")

    # -- core ingestion -----------------------------------------------------

    async def process_osd(
        self,
        gateway_sn: str,
        payload: Dict[str, Any],
    ) -> Optional[DroneTelemetry]:
        """Parse a raw OSD payload dict into a ``DroneTelemetry`` record.

        Returns the record or ``None`` if the payload was unparseable.
        """
        try:
            device_sn = payload.get("device_sn", gateway_sn)
            telem = DroneTelemetry(
                gateway_sn=gateway_sn,
                device_sn=device_sn,
                timestamp=time.time(),
            )

            osd_data: Dict[str, Any] = payload.get("data", payload)
            for raw_key, attr in _OSD_KEY_MAP.items():
                if raw_key in osd_data:
                    val = osd_data[raw_key]
                    if attr == "is_flying":
                        val = val == 1 or val is True
                    setattr(telem, attr, val)

            # cache & status
            self._latest[device_sn] = telem
            if device_sn not in self._status:
                self._status[device_sn] = DroneStatus(device_sn)
            self._status[device_sn].update_from_telemetry(telem)

            # publish to Redis
            await self._publish(telem)

            logger.debug(
                "Processed OSD for %s [%.6f, %.6f] alt=%.1f",
                device_sn,
                telem.latitude,
                telem.longitude,
                telem.altitude,
            )
            return telem
        except Exception:
            logger.exception("Failed to process OSD for gateway=%s", gateway_sn)
            return None

    # -- queries ------------------------------------------------------------

    def get_latest(self, device_sn: str) -> Optional[DroneTelemetry]:
        return self._latest.get(device_sn)

    def get_all_latest(self) -> Dict[str, DroneTelemetry]:
        return dict(self._latest)

    def get_status(self, device_sn: str) -> Optional[DroneStatus]:
        return self._status.get(device_sn)

    def get_online_drones(self) -> list[str]:
        now = time.time()
        return [
            sn
            for sn, st in self._status.items()
            if now - st.last_seen < self.STALE_THRESHOLD_S
        ]

    # -- internal -----------------------------------------------------------

    async def _publish(self, telem: DroneTelemetry) -> None:
        if self._redis is None:
            return
        try:
            message = json.dumps(telem.to_dict(), default=str)
            await self._redis.publish(self.REDIS_CHANNEL, message)
        except Exception:
            logger.exception("Redis publish failed for %s", telem.device_sn)
