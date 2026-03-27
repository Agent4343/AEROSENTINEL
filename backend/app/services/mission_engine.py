"""MissionEngine -- search-pattern generation, WPML conversion, and mission dispatch.

Orchestrates the full lifecycle of autonomous wayline missions:
  1. Generate a search pattern (expanding square, parallel track, sector).
  2. Convert the pattern to DJI WPML XML.
  3. Upload the wayline file and dispatch via MQTT.
  4. Track progress and handle breakpoint resume.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.core.geo import (
    GeoBounds,
    GeoPoint,
    generate_expanding_square,
    generate_parallel_tracks,
    generate_sector_search,
    haversine_distance,
)
from app.core.wpml import (
    FinishAction,
    MissionSettings,
    Waypoint,
    WaypointAction,
    ActionType,
    generate_mission_id,
    generate_wpml,
)
from app.services.mqtt_service import MQTTService

logger = logging.getLogger("aerosentinel.mission_engine")


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class SearchPattern(str, Enum):
    EXPANDING_SQUARE = "expanding_square"
    PARALLEL_TRACK = "parallel_track"
    SECTOR_SEARCH = "sector_search"


class MissionStatus(str, Enum):
    PENDING = "pending"
    PREPARING = "preparing"
    READY = "ready"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class MissionRecord:
    """Internal bookkeeping for an active mission."""

    mission_id: str
    gateway_sn: str
    flight_id: str
    pattern: SearchPattern
    status: MissionStatus = MissionStatus.PENDING
    wpml_xml: str = ""
    waypoints: List[Tuple[float, float]] = field(default_factory=list)
    progress_percent: float = 0.0
    breakpoint_index: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    auto_dispatch_followup: bool = False
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MissionEngine:
    """Generates search patterns, builds WPML waylines, and dispatches
    missions to DJI docks via MQTT."""

    def __init__(
        self,
        mqtt_service: MQTTService,
        wayline_upload_url_base: str = "https://storage.example.com/waylines",
    ) -> None:
        self._mqtt = mqtt_service
        self._upload_url_base = wayline_upload_url_base.rstrip("/")

        # Active missions keyed by mission_id
        self._missions: Dict[str, MissionRecord] = {}

        # Register MQTT handlers for progress
        self._mqtt.on_method("flighttask_progress", self._on_flighttask_progress)
        self._mqtt.on_services_reply(self._on_services_reply)

    # -- pattern generation -------------------------------------------------

    def generate_search_pattern(
        self,
        pattern: SearchPattern,
        center_lat: float,
        center_lon: float,
        radius_m: float = 500.0,
        spacing_m: float = 50.0,
        altitude: float = 60.0,
        legs: int = 20,
        sectors: int = 3,
    ) -> List[Tuple[float, float]]:
        """Return a list of ``(lat, lon)`` coordinates for the requested pattern."""
        if pattern == SearchPattern.EXPANDING_SQUARE:
            return generate_expanding_square(center_lat, center_lon, spacing_m, legs)

        if pattern == SearchPattern.PARALLEL_TRACK:
            from app.core.geo import destination_point

            sw = destination_point(center_lat, center_lon, 225.0, radius_m)
            ne = destination_point(center_lat, center_lon, 45.0, radius_m)
            bounds = GeoBounds(
                min_lat=sw[0], min_lon=sw[1], max_lat=ne[0], max_lon=ne[1]
            )
            points = generate_parallel_tracks(bounds, spacing_m, altitude)
            return [(p.lat, p.lon) for p in points]

        if pattern == SearchPattern.SECTOR_SEARCH:
            return generate_sector_search(center_lat, center_lon, radius_m, sectors)

        raise ValueError(f"Unknown search pattern: {pattern}")

    # -- WPML conversion ----------------------------------------------------

    def pattern_to_wpml(
        self,
        coords: List[Tuple[float, float]],
        altitude: float = 60.0,
        speed: float = 5.0,
        gimbal_pitch: float = -90.0,
        take_photos: bool = True,
    ) -> str:
        """Convert coordinate list to a DJI WPML XML string."""
        waypoints: List[Waypoint] = []
        for lat, lon in coords:
            actions: List[WaypointAction] = []
            if take_photos:
                actions.append(WaypointAction(ActionType.TAKE_PHOTO))
            waypoints.append(
                Waypoint(
                    lat=lat,
                    lon=lon,
                    altitude=altitude,
                    speed=speed,
                    gimbal_pitch=gimbal_pitch,
                    actions=actions,
                )
            )

        settings = MissionSettings(
            auto_flight_speed=speed,
            max_flight_speed=max(speed * 2, 15.0),
            finish_action=FinishAction.GO_HOME,
        )
        return generate_wpml(waypoints, settings)

    # -- mission dispatch ---------------------------------------------------

    async def create_and_dispatch(
        self,
        gateway_sn: str,
        pattern: SearchPattern,
        center_lat: float,
        center_lon: float,
        radius_m: float = 500.0,
        spacing_m: float = 50.0,
        altitude: float = 60.0,
        speed: float = 5.0,
        auto_followup: bool = False,
    ) -> MissionRecord:
        """End-to-end: generate pattern, build WPML, upload, and dispatch."""
        mission_id = generate_mission_id()
        flight_id = uuid.uuid4().hex[:16]

        coords = self.generate_search_pattern(
            pattern, center_lat, center_lon, radius_m, spacing_m, altitude
        )
        wpml_xml = self.pattern_to_wpml(coords, altitude, speed)

        record = MissionRecord(
            mission_id=mission_id,
            gateway_sn=gateway_sn,
            flight_id=flight_id,
            pattern=pattern,
            wpml_xml=wpml_xml,
            waypoints=coords,
            auto_dispatch_followup=auto_followup,
        )
        self._missions[mission_id] = record

        try:
            await self._dispatch(record)
        except Exception as exc:
            record.status = MissionStatus.FAILED
            record.error_message = str(exc)
            logger.exception("Mission dispatch failed: %s", mission_id)

        return record

    async def _dispatch(self, record: MissionRecord) -> None:
        """Upload wayline and send prepare + execute commands."""
        record.status = MissionStatus.PREPARING
        record.updated_at = time.time()

        file_url = f"{self._upload_url_base}/{record.flight_id}.kmz"
        file_md5 = hashlib.md5(record.wpml_xml.encode()).hexdigest()

        await self._mqtt.send_flighttask_prepare(
            record.gateway_sn,
            record.flight_id,
            file_url,
            file_md5,
        )
        logger.info("Mission %s: flighttask_prepare sent", record.mission_id)

    async def execute_mission(self, mission_id: str) -> None:
        """Trigger execution of a previously prepared mission."""
        record = self._missions.get(mission_id)
        if record is None:
            raise ValueError(f"Unknown mission: {mission_id}")
        if record.status not in (MissionStatus.READY, MissionStatus.PREPARING):
            raise RuntimeError(
                f"Mission {mission_id} cannot be executed in state {record.status}"
            )

        record.status = MissionStatus.EXECUTING
        record.updated_at = time.time()

        await self._mqtt.send_flighttask_execute(
            record.gateway_sn, record.flight_id
        )
        logger.info("Mission %s: flighttask_execute sent", record.mission_id)

    async def cancel_mission(self, mission_id: str) -> None:
        """Cancel a mission."""
        record = self._missions.get(mission_id)
        if record is None:
            raise ValueError(f"Unknown mission: {mission_id}")
        record.status = MissionStatus.CANCELLED
        record.updated_at = time.time()
        logger.info("Mission %s cancelled", mission_id)

    async def resume_from_breakpoint(self, mission_id: str) -> None:
        """Resume a paused mission from the last known breakpoint."""
        record = self._missions.get(mission_id)
        if record is None:
            raise ValueError(f"Unknown mission: {mission_id}")
        if record.status != MissionStatus.PAUSED:
            raise RuntimeError(f"Mission {mission_id} is not paused")

        remaining = record.waypoints[record.breakpoint_index:]
        if not remaining:
            record.status = MissionStatus.COMPLETED
            record.updated_at = time.time()
            return

        resume_wpml = self.pattern_to_wpml(remaining)
        record.wpml_xml = resume_wpml
        record.updated_at = time.time()

        await self._dispatch(record)
        logger.info(
            "Mission %s resuming from waypoint %d",
            mission_id,
            record.breakpoint_index,
        )

    # -- MQTT callbacks -----------------------------------------------------

    async def _on_flighttask_progress(
        self, gateway_sn: str, payload: Dict[str, Any]
    ) -> None:
        """Handle flighttask_progress events."""
        data = payload.get("data", {})
        flight_id = data.get("flight_id", "")
        progress = data.get("progress", {})
        percent = progress.get("percent", 0)
        waypoint_index = progress.get("waypoint_index", 0)
        status_str = data.get("status", "")

        record = self._find_by_flight_id(flight_id)
        if record is None:
            logger.debug("Progress for unknown flight_id=%s", flight_id)
            return

        record.progress_percent = percent
        record.breakpoint_index = waypoint_index
        record.updated_at = time.time()

        if status_str == "ok" and percent >= 100:
            record.status = MissionStatus.COMPLETED
            logger.info("Mission %s completed", record.mission_id)
            if record.auto_dispatch_followup:
                asyncio.create_task(self._auto_followup(record))
        elif status_str == "paused":
            record.status = MissionStatus.PAUSED
            logger.info(
                "Mission %s paused at waypoint %d",
                record.mission_id,
                waypoint_index,
            )
        elif status_str in ("failed", "error"):
            record.status = MissionStatus.FAILED
            record.error_message = data.get("reason", "unknown")
            logger.error("Mission %s failed: %s", record.mission_id, record.error_message)

    async def _on_services_reply(
        self, gateway_sn: str, payload: Dict[str, Any]
    ) -> None:
        """Handle replies to flighttask_prepare / execute."""
        method = payload.get("method", "")
        data = payload.get("data", {})
        result = data.get("result", -1)
        flight_id = data.get("flight_id", "")

        record = self._find_by_flight_id(flight_id)
        if record is None:
            return

        if method == "flighttask_prepare":
            if result == 0:
                record.status = MissionStatus.READY
                record.updated_at = time.time()
                logger.info("Mission %s prepared successfully", record.mission_id)
                # Auto-execute
                await self.execute_mission(record.mission_id)
            else:
                record.status = MissionStatus.FAILED
                record.error_message = f"Prepare failed with result={result}"
                logger.error("Mission %s prepare failed: result=%d", record.mission_id, result)

    # -- helpers ------------------------------------------------------------

    def _find_by_flight_id(self, flight_id: str) -> Optional[MissionRecord]:
        for record in self._missions.values():
            if record.flight_id == flight_id:
                return record
        return None

    async def _auto_followup(self, completed: MissionRecord) -> None:
        """Dispatch a follow-up inspection mission over the same area."""
        try:
            if not completed.waypoints:
                return
            center_lat = sum(p[0] for p in completed.waypoints) / len(completed.waypoints)
            center_lon = sum(p[1] for p in completed.waypoints) / len(completed.waypoints)

            logger.info(
                "Auto-dispatching follow-up inspection for mission %s",
                completed.mission_id,
            )
            await self.create_and_dispatch(
                gateway_sn=completed.gateway_sn,
                pattern=SearchPattern.PARALLEL_TRACK,
                center_lat=center_lat,
                center_lon=center_lon,
                radius_m=200.0,
                spacing_m=25.0,
                altitude=40.0,
                speed=3.0,
                auto_followup=False,
            )
        except Exception:
            logger.exception("Auto follow-up dispatch failed for mission %s", completed.mission_id)

    def get_mission(self, mission_id: str) -> Optional[MissionRecord]:
        return self._missions.get(mission_id)

    def get_active_missions(self) -> List[MissionRecord]:
        active = {MissionStatus.PREPARING, MissionStatus.READY, MissionStatus.EXECUTING, MissionStatus.PAUSED}
        return [m for m in self._missions.values() if m.status in active]

    def get_missions_for_gateway(self, gateway_sn: str) -> List[MissionRecord]:
        return [m for m in self._missions.values() if m.gateway_sn == gateway_sn]
