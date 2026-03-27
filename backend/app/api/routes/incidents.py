from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.incident import Incident, IncidentSeverity, IncidentStatus, IncidentType

router = APIRouter(prefix="/incidents", tags=["incidents"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class IncidentCreate(BaseModel):
    title: str
    type: IncidentType
    latitude: float
    longitude: float
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    status: IncidentStatus = IncidentStatus.REPORTED
    radius_meters: float = 500.0
    description: str | None = None


class IncidentUpdate(BaseModel):
    title: str | None = None
    type: IncidentType | None = None
    status: IncidentStatus | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_meters: float | None = None
    description: str | None = None
    severity: IncidentSeverity | None = None


class IncidentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    type: IncidentType
    status: IncidentStatus
    latitude: float
    longitude: float
    radius_meters: float
    description: str | None
    severity: IncidentSeverity
    created_at: datetime
    updated_at: datetime


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("", response_model=IncidentRead, status_code=201)
async def create_incident(body: IncidentCreate, db: AsyncSession = Depends(get_db)):
    incident = Incident(**body.model_dump())
    db.add(incident)
    await db.flush()
    await db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentRead])
async def list_incidents(
    status: IncidentStatus | None = Query(None),
    type: IncidentType | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Incident)
    if status is not None:
        stmt = stmt.where(Incident.status == status)
    if type is not None:
        stmt = stmt.where(Incident.type == type)
    stmt = stmt.order_by(Incident.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: int, db: AsyncSession = Depends(get_db)):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.put("/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: int, body: IncidentUpdate, db: AsyncSession = Depends(get_db)
):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(incident, field, value)
    await db.flush()
    await db.refresh(incident)
    return incident


@router.delete("/{incident_id}", status_code=204)
async def delete_incident(incident_id: int, db: AsyncSession = Depends(get_db)):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    await db.delete(incident)
    await db.flush()
