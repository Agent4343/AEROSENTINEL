from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.drone import Drone, DroneTelemetry, DroneStatus

router = APIRouter(prefix="/drones", tags=["drones"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class TelemetryRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    drone_id: int
    latitude: float
    longitude: float
    altitude: float
    speed: float
    heading: float
    battery_percent: float
    gimbal_pitch: float
    gimbal_yaw: float
    timestamp: datetime


class DroneRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    serial_number: str
    model: str
    name: str
    status: DroneStatus
    dock_serial: str | None
    last_telemetry_at: datetime | None


class DroneWithTelemetry(DroneRead):
    latest_telemetry: TelemetryRead | None = None


class DroneCommand(BaseModel):
    command: str
    params: dict | None = None


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("", response_model=list[DroneRead])
async def list_drones(
    status: DroneStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Drone)
    if status is not None:
        stmt = stmt.where(Drone.status == status)
    stmt = stmt.order_by(Drone.id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{serial_number}", response_model=DroneWithTelemetry)
async def get_drone_by_serial(serial_number: str, db: AsyncSession = Depends(get_db)):
    stmt = select(Drone).where(Drone.serial_number == serial_number)
    result = await db.execute(stmt)
    drone = result.scalar_one_or_none()
    if drone is None:
        raise HTTPException(status_code=404, detail="Drone not found")

    # Fetch latest telemetry
    tel_stmt = (
        select(DroneTelemetry)
        .where(DroneTelemetry.drone_id == drone.id)
        .order_by(DroneTelemetry.timestamp.desc())
        .limit(1)
    )
    tel_result = await db.execute(tel_stmt)
    latest = tel_result.scalar_one_or_none()

    return DroneWithTelemetry(
        id=drone.id,
        serial_number=drone.serial_number,
        model=drone.model,
        name=drone.name,
        status=drone.status,
        dock_serial=drone.dock_serial,
        last_telemetry_at=drone.last_telemetry_at,
        latest_telemetry=latest,
    )


@router.post("/{serial_number}/command", status_code=202)
async def send_drone_command(
    serial_number: str, body: DroneCommand, db: AsyncSession = Depends(get_db)
):
    stmt = select(Drone).where(Drone.serial_number == serial_number)
    result = await db.execute(stmt)
    drone = result.scalar_one_or_none()
    if drone is None:
        raise HTTPException(status_code=404, detail="Drone not found")
    return {"status": "accepted", "drone_id": drone.id, "command": body.command}
