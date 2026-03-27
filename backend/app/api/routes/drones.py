from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import Drone, DroneTelemetry

router = APIRouter(prefix="/drones", tags=["drones"])


class DroneStatusEnum(str, Enum):
    online = "online"
    offline = "offline"
    flying = "flying"
    returning = "returning"
    charging = "charging"


class DroneResponse(BaseModel):
    id: int
    serial_number: str
    model: str
    name: str
    status: str
    dock_serial: Optional[str] = None
    last_telemetry_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TelemetryResponse(BaseModel):
    id: int
    latitude: float
    longitude: float
    altitude: float
    speed: float
    heading: float
    battery_percent: float
    gimbal_pitch: float
    gimbal_yaw: float
    timestamp: datetime

    model_config = {"from_attributes": True}


class DroneDetailResponse(DroneResponse):
    latest_telemetry: Optional[TelemetryResponse] = None


class DroneCommand(str, Enum):
    takeoff = "takeoff"
    land = "land"
    return_to_home = "return_to_home"
    hover = "hover"
    emergency_stop = "emergency_stop"


class CommandRequest(BaseModel):
    command: DroneCommand
    parameters: Optional[dict] = Field(default_factory=dict)


class CommandResponse(BaseModel):
    serial_number: str
    command: str
    accepted: bool
    message: str


@router.get("", response_model=list[DroneResponse])
async def list_drones(
    status_filter: Optional[DroneStatusEnum] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Drone)
    if status_filter is not None:
        stmt = stmt.where(Drone.status == status_filter.value)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{serial_number}", response_model=DroneDetailResponse)
async def get_drone(serial_number: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Drone).where(Drone.serial_number == serial_number))
    drone = result.scalar_one_or_none()
    if drone is None:
        raise HTTPException(status_code=404, detail=f"Drone {serial_number} not found")
    telemetry_result = await db.execute(
        select(DroneTelemetry)
        .where(DroneTelemetry.drone_id == drone.id)
        .order_by(DroneTelemetry.timestamp.desc())
        .limit(1)
    )
    latest = telemetry_result.scalar_one_or_none()
    return DroneDetailResponse(
        **{c.name: getattr(drone, c.name) for c in drone.__table__.columns},
        latest_telemetry=latest,
    )


@router.post("/{serial_number}/command", response_model=CommandResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_command(
    serial_number: str, payload: CommandRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Drone).where(Drone.serial_number == serial_number))
    drone = result.scalar_one_or_none()
    if drone is None:
        raise HTTPException(status_code=404, detail=f"Drone {serial_number} not found")
    if drone.status == "offline":
        raise HTTPException(status_code=409, detail=f"Drone {serial_number} is offline")
    return CommandResponse(
        serial_number=serial_number,
        command=payload.command.value,
        accepted=True,
        message=f"Command '{payload.command.value}' dispatched to {serial_number}",
    )
