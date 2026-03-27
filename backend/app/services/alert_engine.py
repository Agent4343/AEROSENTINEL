"""AlertEngine -- triage, deduplication, and automated action dispatch.

Evaluates AI detections against configurable triage rules, assigns severity
levels, deduplicates alerts within a spatiotemporal window, and triggers
automated actions (notifications via Redis pub-sub, auto-dispatch flags).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any, Callable, Coroutine, Dict, List, Optional

import redis.asyncio as redis

from app.core.geo import haversine_distance
from app.services.ai_pipeline import Detection

logger = logging.getLogger("aerosentinel.alert_engine")


class Severity(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class TriageRule:
    class_name: str
    min_confidence: float = 0.5
    severity: Severity = Severity.MEDIUM
    auto_dispatch: bool = False
    description: str = ""


@dataclass
class Alert:
    alert_id: str = ""
    severity: Severity = Severity.MEDIUM
    class_name: str = ""
    confidence: float = 0.0
    latitude: float = 0.0
    longitude: float = 0.0
    drone_sn: str = ""
    timestamp: float = field(default_factory=time.time)
    rule_description: str = ""
    auto_dispatch: bool = False
    acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["severity"] = self.severity.name.lower()
        return d


ActionCallback = Callable[[Alert], Coroutine[Any, Any, None]]


DEFAULT_RULES: List[TriageRule] = [
    TriageRule("fire", 0.50, Severity.CRITICAL, auto_dispatch=True, description="Active fire detected"),
    TriageRule("smoke", 0.55, Severity.HIGH, auto_dispatch=True, description="Smoke plume detected"),
    TriageRule("stranded_person", 0.45, Severity.CRITICAL, auto_dispatch=True, description="Stranded person detected"),
    TriageRule("person", 0.50, Severity.MEDIUM, description="Person detected in search area"),
    TriageRule("collapsed_structure", 0.50, Severity.HIGH, auto_dispatch=True, description="Structural collapse detected"),
    TriageRule("flooding", 0.50, Severity.HIGH, description="Flooding detected"),
    TriageRule("hazmat_spill", 0.55, Severity.CRITICAL, auto_dispatch=True, description="Hazardous material spill"),
    TriageRule("landslide", 0.50, Severity.HIGH, description="Landslide detected"),
    TriageRule("power_line_damage", 0.50, Severity.MEDIUM, description="Power line damage"),
    TriageRule("road_blockage", 0.45, Severity.MEDIUM, description="Road blockage detected"),
    TriageRule("vehicle", 0.50, Severity.LOW, description="Vehicle detected"),
    TriageRule("boat", 0.50, Severity.LOW, description="Boat detected"),
    TriageRule("crowd", 0.45, Severity.MEDIUM, description="Crowd gathered"),
    TriageRule("debris", 0.45, Severity.LOW, description="Debris field detected"),
    TriageRule("animal", 0.50, Severity.LOW, description="Animal detected"),
]


class AlertEngine:
    """Evaluates detections against triage rules, deduplicates, and triggers
    automated actions."""

    REDIS_CHANNEL = "aerosentinel:alerts"
    DEFAULT_DEDUP_RADIUS_M = 30.0
    DEFAULT_DEDUP_WINDOW_S = 300.0

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        rules: Optional[List[TriageRule]] = None,
        dedup_radius_m: float = DEFAULT_DEDUP_RADIUS_M,
        dedup_window_s: float = DEFAULT_DEDUP_WINDOW_S,
    ) -> None:
        self._redis_url = redis_url
        self._redis: Optional[redis.Redis] = None
        self._rules: Dict[str, TriageRule] = {}
        for rule in (rules or DEFAULT_RULES):
            self._rules[rule.class_name] = rule
        self._dedup_radius = dedup_radius_m
        self._dedup_window = dedup_window_s
        self._recent_alerts: List[Alert] = []
        self._detection_counts: Dict[str, List[float]] = {}
        self._rate_window_s = 60.0
        self._action_callbacks: List[ActionCallback] = []
        self._alert_counter = 0

    async def start(self) -> None:
        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        logger.info("AlertEngine started")

    async def stop(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    def register_action(self, callback: ActionCallback) -> None:
        self._action_callbacks.append(callback)

    async def evaluate(self, detections: List[Detection]) -> List[Alert]:
        now = time.time()
        self._prune_old_alerts(now)
        alerts: List[Alert] = []

        for det in detections:
            rule = self._rules.get(det.class_name)
            if rule is None:
                continue
            if det.confidence < rule.min_confidence:
                continue
            if self._is_duplicate(det, now):
                continue

            severity = self._compute_severity(det, rule, now)
            self._alert_counter += 1
            alert = Alert(
                alert_id=f"ALR-{self._alert_counter:06d}",
                severity=severity,
                class_name=det.class_name,
                confidence=det.confidence,
                latitude=det.latitude,
                longitude=det.longitude,
                drone_sn=det.drone_sn or "",
                timestamp=now,
                rule_description=rule.description,
                auto_dispatch=rule.auto_dispatch and severity >= Severity.HIGH,
            )
            alerts.append(alert)
            self._recent_alerts.append(alert)
            logger.info(
                "Alert %s: %s [%s] conf=%.2f @ (%.6f, %.6f)",
                alert.alert_id, alert.class_name, alert.severity.name,
                alert.confidence, alert.latitude, alert.longitude,
            )
            await self._publish_alert(alert)
            if severity >= Severity.HIGH:
                await self._trigger_actions(alert)

        return alerts

    def _is_duplicate(self, det: Detection, now: float) -> bool:
        for prev in self._recent_alerts:
            if prev.class_name != det.class_name:
                continue
            if now - prev.timestamp > self._dedup_window:
                continue
            dist = haversine_distance(prev.latitude, prev.longitude, det.latitude, det.longitude)
            if dist < self._dedup_radius:
                return True
        return False

    def _prune_old_alerts(self, now: float) -> None:
        cutoff = now - self._dedup_window * 2
        self._recent_alerts = [a for a in self._recent_alerts if a.timestamp > cutoff]

    def _compute_severity(self, det: Detection, rule: TriageRule, now: float) -> Severity:
        severity = rule.severity
        if det.confidence > 0.85 and severity < Severity.CRITICAL:
            severity = Severity(severity + 1)
        timestamps = self._detection_counts.setdefault(det.class_name, [])
        timestamps.append(now)
        self._detection_counts[det.class_name] = [t for t in timestamps if now - t < self._rate_window_s]
        rate = len(self._detection_counts[det.class_name])
        if rate >= 10 and severity < Severity.CRITICAL:
            severity = Severity(min(severity + 1, Severity.CRITICAL))
        return severity

    async def _trigger_actions(self, alert: Alert) -> None:
        for callback in self._action_callbacks:
            try:
                await callback(alert)
            except Exception:
                logger.exception("Action callback failed for alert %s", alert.alert_id)

    async def _publish_alert(self, alert: Alert) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.publish(self.REDIS_CHANNEL, json.dumps(alert.to_dict(), default=str))
        except Exception:
            logger.exception("Redis publish failed for alert %s", alert.alert_id)

    def get_recent_alerts(self, severity_min: Severity = Severity.LOW, limit: int = 100) -> List[Alert]:
        filtered = [a for a in self._recent_alerts if a.severity >= severity_min]
        filtered.sort(key=lambda a: a.timestamp, reverse=True)
        return filtered[:limit]

    def acknowledge_alert(self, alert_id: str) -> bool:
        for alert in self._recent_alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False
