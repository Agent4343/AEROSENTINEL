"""
AeroSentinel Demo Simulator
Seeds the database with realistic emergency response data and runs a
background task that continuously updates drone positions, battery levels,
and generates new detections / alerts.
"""

from __future__ import annotations

import asyncio
import math
import random
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter
from sqlalchemy import delete, select

from app.db.database import async_session_factory
from app.models.alert import Alert, AlertSeverity
from app.models.detection import Detection, DetectionCategory, DetectionSeverity
from app.models.drone import Drone, DroneStatus, DroneTelemetry
from app.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType
from app.models.mission import Mission, MissionStatus, MissionType, SearchPattern

router = APIRouter(prefix="/simulator", tags=["simulator"])

_simulation_task: asyncio.Task | None = None
_simulation_running: bool = False
_drone_angles: dict[int, float] = {}
_drone_batteries: dict[int, float] = {}
_tick: int = 0


def _jitter(value: float, pct: float = 0.0005) -> float:
    return value + random.uniform(-pct, pct)


def _random_point_near(lat: float, lon: float, radius_m: float) -> tuple[float, float]:
    r_deg = radius_m / 111_320.0
    angle = random.uniform(0, 2 * math.pi)
    dist = random.uniform(0.2, 1.0) * r_deg
    return lat + dist * math.sin(angle), lon + dist * math.cos(angle)


@router.post("/seed")
async def seed_database() -> dict:
    async with async_session_factory() as session:
        async with session.begin():
            await session.execute(delete(Alert))
            await session.execute(delete(Detection))
            await session.execute(delete(Mission))
            await session.execute(delete(DroneTelemetry))
            await session.execute(delete(Drone))
            await session.execute(delete(Incident))

        async with session.begin():
            wildfire = Incident(
                title="Wildfire - Santa Monica Mountains",
                type=IncidentType.WILDFIRE, status=IncidentStatus.ACTIVE,
                severity=IncidentSeverity.CRITICAL,
                latitude=34.0259, longitude=-118.7798, radius_meters=2000,
                description="Active wildfire spreading through chaparral. Multiple hotspots. Winds 35 mph.",
            )
            flood = Incident(
                title="Flood Assessment - Houston Bayou",
                type=IncidentType.FLOOD, status=IncidentStatus.ACTIVE,
                severity=IncidentSeverity.HIGH,
                latitude=29.7604, longitude=-95.3698, radius_meters=1500,
                description="Flash flooding along Buffalo Bayou. Water levels rising. Multiple neighborhoods affected.",
            )
            structural = Incident(
                title="Structural Damage - Miami Beach",
                type=IncidentType.STRUCTURAL, status=IncidentStatus.REPORTED,
                severity=IncidentSeverity.MEDIUM,
                latitude=25.7907, longitude=-80.1300, radius_meters=800,
                description="Partial building collapse after tropical storm. Structural assessment required.",
            )
            session.add_all([wildfire, flood, structural])
            await session.flush()

            now = datetime.now(timezone.utc)
            drones_spec = [
                ("ALPHA-01", "DJI-M4T-A01", "DJI Matrice 4T", DroneStatus.FLYING, wildfire),
                ("ALPHA-02", "DJI-M4T-A02", "DJI Matrice 4T", DroneStatus.FLYING, wildfire),
                ("ALPHA-03", "DJI-M4T-A03", "DJI Matrice 4T", DroneStatus.FLYING, wildfire),
                ("BRAVO-01", "DJI-M4E-B01", "DJI Matrice 4E", DroneStatus.FLYING, flood),
                ("BRAVO-02", "DJI-M4E-B02", "DJI Matrice 4E", DroneStatus.FLYING, flood),
                ("CHARLIE-01", "DJI-MV3E-C01", "DJI Mavic 3E", DroneStatus.FLYING, None),
                ("CHARLIE-02", "DJI-MV3E-C02", "DJI Mavic 3E", DroneStatus.FLYING, None),
                ("DELTA-01", "DJI-M4T-D01", "DJI Matrice 4T", DroneStatus.ONLINE, None),
                ("DELTA-02", "DJI-M30T-D02", "DJI Matrice 30T", DroneStatus.OFFLINE, None),
            ]

            drones: list[Drone] = []
            for name, serial, model, status, _ in drones_spec:
                d = Drone(name=name, serial_number=serial, model=model, status=status,
                          last_telemetry_at=now if status != DroneStatus.OFFLINE else None)
                drones.append(d)
            session.add_all(drones)
            await session.flush()

            patrol_centres = {"CHARLIE-01": (34.05, -118.25), "CHARLIE-02": (33.95, -118.40)}
            telemetry_records: list[DroneTelemetry] = []
            for idx, (name, serial, model, status, inc) in enumerate(drones_spec):
                drone = drones[idx]
                if status == DroneStatus.OFFLINE:
                    continue
                if inc is not None:
                    lat, lon = _random_point_near(inc.latitude, inc.longitude, inc.radius_meters * 0.5)
                    alt = random.uniform(80, 150)
                elif name in patrol_centres:
                    lat, lon = patrol_centres[name]
                    alt = random.uniform(60, 100)
                else:
                    lat, lon = 34.0522, -118.2437
                    alt = 0.0
                batt = random.uniform(72, 98) if status == DroneStatus.FLYING else 100.0
                telemetry_records.append(DroneTelemetry(
                    drone_id=drone.id, latitude=lat, longitude=lon, altitude=alt,
                    speed=random.uniform(8, 16) if status == DroneStatus.FLYING else 0.0,
                    heading=random.uniform(0, 360), battery_percent=batt,
                    gimbal_pitch=-45.0, gimbal_yaw=random.uniform(-90, 90), timestamp=now,
                ))
                _drone_batteries[drone.id] = batt
                _drone_angles[drone.id] = random.uniform(0, 2 * math.pi)
            session.add_all(telemetry_records)

            m1 = Mission(incident_id=wildfire.id, drone_id=drones[0].id, type=MissionType.SEARCH_PATTERN,
                         status=MissionStatus.EXECUTING, search_pattern=SearchPattern.EXPANDING_SQUARE,
                         started_at=now - timedelta(minutes=42))
            m2 = Mission(incident_id=flood.id, drone_id=drones[3].id, type=MissionType.MONITORING,
                         status=MissionStatus.EXECUTING, search_pattern=SearchPattern.PARALLEL_TRACK,
                         started_at=now - timedelta(minutes=28))
            m3 = Mission(incident_id=structural.id, drone_id=drones[5].id, type=MissionType.INSPECTION,
                         status=MissionStatus.EXECUTING, search_pattern=SearchPattern.SECTOR,
                         started_at=now - timedelta(minutes=15))
            session.add_all([m1, m2, m3])
            await session.flush()

            det_specs = []
            for i in range(3):
                lat, lon = _random_point_near(wildfire.latitude, wildfire.longitude, wildfire.radius_meters)
                det_specs.append(dict(mission_id=m1.id, drone_id=drones[i].id,
                    category=DetectionCategory.FIRE if i < 2 else DetectionCategory.SMOKE,
                    confidence=round(random.uniform(0.82, 0.97), 2), latitude=lat, longitude=lon,
                    altitude=random.uniform(80, 130),
                    severity=DetectionSeverity.CRITICAL if i == 0 else DetectionSeverity.HIGH,
                    bbox={"x": 200, "y": 150, "w": 120, "h": 100}, processed=True))

            for i in range(2):
                lat, lon = _random_point_near(flood.latitude, flood.longitude, flood.radius_meters)
                det_specs.append(dict(mission_id=m2.id, drone_id=drones[3 + i].id,
                    category=DetectionCategory.FLOOD_WATER,
                    confidence=round(random.uniform(0.88, 0.96), 2), latitude=lat, longitude=lon,
                    altitude=random.uniform(60, 100), severity=DetectionSeverity.HIGH,
                    bbox={"x": 100, "y": 80, "w": 300, "h": 250}, processed=True))

            lat, lon = _random_point_near(flood.latitude, flood.longitude, flood.radius_meters * 0.6)
            det_specs.append(dict(mission_id=m2.id, drone_id=drones[3].id,
                category=DetectionCategory.PERSON, confidence=round(random.uniform(0.75, 0.92), 2),
                latitude=lat, longitude=lon, altitude=70, severity=DetectionSeverity.CRITICAL,
                bbox={"x": 310, "y": 180, "w": 45, "h": 90}, processed=True))

            for i in range(3):
                lat, lon = _random_point_near(structural.latitude, structural.longitude, structural.radius_meters)
                cat = DetectionCategory.STRUCTURAL_DAMAGE if i < 2 else DetectionCategory.PERSON
                det_specs.append(dict(mission_id=m3.id, drone_id=drones[5 + i % 2].id,
                    category=cat, confidence=round(random.uniform(0.70, 0.93), 2),
                    latitude=lat, longitude=lon, altitude=random.uniform(40, 70),
                    severity=DetectionSeverity.MEDIUM if cat == DetectionCategory.STRUCTURAL_DAMAGE else DetectionSeverity.HIGH,
                    bbox={"x": 150, "y": 120, "w": 180, "h": 160}, processed=True))

            det_objs = [Detection(**d) for d in det_specs]
            session.add_all(det_objs)
            await session.flush()

            alerts_data = [
                (0, wildfire, AlertSeverity.CRITICAL, "Active fire hotspot detected"),
                (1, wildfire, AlertSeverity.HIGH, "Dense smoke plume identified"),
                (3, flood, AlertSeverity.HIGH, "Flood water encroaching residential zone"),
                (5, flood, AlertSeverity.CRITICAL, "Person detected in flood zone — rescue required"),
                (6, structural, AlertSeverity.MEDIUM, "Structural crack pattern detected"),
                (8, structural, AlertSeverity.HIGH, "Person near damaged structure — evacuate"),
            ]
            for det_idx, inc, sev, msg in alerts_data:
                session.add(Alert(detection_id=det_objs[det_idx].id, incident_id=inc.id,
                                  severity=sev, message=msg))

    return {"status": "seeded", "incidents": 3, "drones": 9, "missions": 3,
            "detections": len(det_specs), "alerts": 6}


async def _simulation_loop() -> None:
    global _tick, _simulation_running

    async with async_session_factory() as session:
        incidents = (await session.execute(select(Incident))).scalars().all()
        missions = (await session.execute(
            select(Mission).where(Mission.status == MissionStatus.EXECUTING))).scalars().all()
        drones = (await session.execute(
            select(Drone).where(Drone.status == DroneStatus.FLYING))).scalars().all()

    incident_map = {i.id: i for i in incidents}
    drone_incident: dict[int, Incident] = {}
    drone_mission: dict[int, Mission] = {}
    for m in missions:
        if m.drone_id and m.incident_id in incident_map:
            drone_incident[m.drone_id] = incident_map[m.incident_id]
            drone_mission[m.drone_id] = m

    drone_name_map = {d.id: d.name for d in drones}
    for d in drones:
        if d.id not in drone_incident:
            prefix = d.name.split("-")[0]
            for oid, inc in list(drone_incident.items()):
                if drone_name_map.get(oid, "").startswith(prefix):
                    drone_incident[d.id] = inc
                    break

    patrol_centres = {"CHARLIE-01": (34.05, -118.25), "CHARLIE-02": (33.95, -118.40)}
    orbit_radius = 0.003

    while _simulation_running:
        _tick += 1
        now = datetime.now(timezone.utc)

        async with async_session_factory() as session:
            async with session.begin():
                for d in drones:
                    angle = _drone_angles.get(d.id, 0.0)
                    batt = _drone_batteries.get(d.id, 85.0)

                    if d.id in drone_incident:
                        inc = drone_incident[d.id]
                        clat, clon = inc.latitude, inc.longitude
                    elif d.name in patrol_centres:
                        clat, clon = patrol_centres[d.name]
                    else:
                        continue

                    angle += 0.08 + (d.id % 5) * 0.015
                    if angle > 2 * math.pi:
                        angle -= 2 * math.pi

                    r = orbit_radius * (0.7 + 0.3 * math.sin(angle * 0.3))
                    new_lat = clat + r * math.sin(angle) + random.uniform(-0.0001, 0.0001)
                    new_lon = clon + r * math.cos(angle) + random.uniform(-0.0001, 0.0001)
                    batt = max(5.0, batt - random.uniform(0.05, 0.15))
                    _drone_angles[d.id] = angle
                    _drone_batteries[d.id] = batt

                    session.add(DroneTelemetry(
                        drone_id=d.id, latitude=round(new_lat, 6), longitude=round(new_lon, 6),
                        altitude=round(random.uniform(70, 140), 1),
                        speed=round(random.uniform(8, 18), 1),
                        heading=round(math.degrees(angle) % 360, 1),
                        battery_percent=round(batt, 1),
                        gimbal_pitch=-45.0 + random.uniform(-5, 5),
                        gimbal_yaw=random.uniform(-90, 90), timestamp=now,
                    ))
                    drone_obj = await session.get(Drone, d.id)
                    if drone_obj:
                        drone_obj.last_telemetry_at = now

                if _tick % random.randint(3, 5) == 0:
                    active = [i for i in incidents if i.status == IncidentStatus.ACTIVE]
                    if active:
                        inc = random.choice(active)
                        cands = [d for d in drones if drone_incident.get(d.id) == inc]
                        if cands:
                            dd = random.choice(cands)
                            lat, lon = _random_point_near(inc.latitude, inc.longitude, inc.radius_meters)
                            cat_map = {
                                IncidentType.WILDFIRE: [DetectionCategory.FIRE, DetectionCategory.SMOKE],
                                IncidentType.FLOOD: [DetectionCategory.FLOOD_WATER, DetectionCategory.PERSON],
                                IncidentType.STRUCTURAL: [DetectionCategory.STRUCTURAL_DAMAGE, DetectionCategory.PERSON],
                            }
                            cat = random.choice(cat_map.get(inc.type, [DetectionCategory.PERSON]))
                            conf = round(random.uniform(0.60, 0.98), 2)
                            sev_map = {
                                DetectionCategory.FIRE: DetectionSeverity.CRITICAL,
                                DetectionCategory.SMOKE: DetectionSeverity.HIGH,
                                DetectionCategory.PERSON: DetectionSeverity.HIGH,
                                DetectionCategory.FLOOD_WATER: DetectionSeverity.HIGH,
                                DetectionCategory.STRUCTURAL_DAMAGE: DetectionSeverity.MEDIUM,
                            }
                            sev = sev_map.get(cat, DetectionSeverity.MEDIUM)
                            mid = drone_mission.get(dd.id)
                            mission_id = mid.id if isinstance(mid, Mission) else missions[0].id if missions else 1

                            det = Detection(mission_id=mission_id, drone_id=dd.id, category=cat,
                                confidence=conf, latitude=round(lat, 6), longitude=round(lon, 6),
                                altitude=round(random.uniform(50, 130), 1), severity=sev,
                                bbox={"x": random.randint(50, 500), "y": random.randint(50, 400),
                                      "w": random.randint(40, 200), "h": random.randint(40, 200)},
                                processed=True)
                            session.add(det)
                            await session.flush()

                            if conf >= 0.78:
                                msg_map = {
                                    DetectionCategory.FIRE: f"Fire hotspot — {conf:.0%} confidence",
                                    DetectionCategory.SMOKE: f"Smoke plume — {conf:.0%} confidence",
                                    DetectionCategory.FLOOD_WATER: f"Flood expansion — {conf:.0%} confidence",
                                    DetectionCategory.PERSON: f"Person in hazard zone — {conf:.0%} confidence",
                                    DetectionCategory.STRUCTURAL_DAMAGE: f"Structural damage — {conf:.0%} confidence",
                                }
                                a_sev = {DetectionSeverity.CRITICAL: AlertSeverity.CRITICAL,
                                         DetectionSeverity.HIGH: AlertSeverity.HIGH,
                                         DetectionSeverity.MEDIUM: AlertSeverity.MEDIUM,
                                         DetectionSeverity.LOW: AlertSeverity.LOW}
                                session.add(Alert(detection_id=det.id, incident_id=inc.id,
                                    severity=a_sev[sev],
                                    message=msg_map.get(cat, f"Detection — {conf:.0%}")))

        await asyncio.sleep(2)


@router.post("/start")
async def start_simulation() -> dict:
    global _simulation_task, _simulation_running
    if _simulation_running and _simulation_task and not _simulation_task.done():
        return {"status": "already_running"}
    _simulation_running = True
    _tick = 0
    _simulation_task = asyncio.create_task(_simulation_loop())
    return {"status": "started"}


@router.post("/stop")
async def stop_simulation() -> dict:
    global _simulation_task, _simulation_running
    if not _simulation_running:
        return {"status": "not_running"}
    _simulation_running = False
    if _simulation_task:
        _simulation_task.cancel()
        try:
            await _simulation_task
        except asyncio.CancelledError:
            pass
        _simulation_task = None
    return {"status": "stopped"}


@router.get("/status")
async def simulation_status() -> dict:
    running = _simulation_running and _simulation_task is not None and not _simulation_task.done()
    return {"running": running, "tick": _tick}
