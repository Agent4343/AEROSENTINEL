from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import Incident

router = APIRouter(prefix="/incidents", tags=["incidents"])


class IncidentStatus(str, Enum):
    reported = "reported"
    active = "active"
    contained = "contained"
    resolved = "resolved"


class IncidentType(str, Enum):
    wildfire = "wildfire"
    flood = "flood"
    earthquake = "earthquake"
    search_and_rescue = "search_and_rescue"
    hazmat = "hazmat"
    infrastructure = "infrastructure"
    other = "other"


class IncidentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    incident_type: IncidentType
    severity: int = Field(..., ge=1, le=5)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    radius_meters: Optional[float] = Field(None, gt=0)


class IncidentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    incident_type: Optional[IncidentType] = None
    status: Optional[IncidentStatus] = None
    severity: Optional[int] = Field(None, ge=1, le=5)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    radius_meters: Optional[float] = Field(None, gt=0)


class IncidentResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    type: str
    status: str
    severity: str
    latitude: float
    longitude: float
    radius_meters: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=IncidentResponse, status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentCreate, db: AsyncSession = Depends(get_db)
):
    incident = Incident(
        title=payload.title,
        description=payload.description,
        type=payload.incident_type.value,
        status=IncidentStatus.reported.value,
        severity=payload.severity,
        latitude=payload.latitude,
        longitude=payload.longitude,
        radius_meters=payload.radius_meters or 500.0,
    )
    db.add(incident)
    await db.commit()
    await db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentResponse])
async def list_incidents(
    status_filter: Optional[IncidentStatus] = Query(None, alias="status"),
    incident_type: Optional[IncidentType] = Query(None, alias="type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Incident)
    if status_filter is not None:
        stmt = stmt.where(Incident.status == status_filter.value)
    if incident_type is not None:
        stmt = stmt.where(Incident.type == incident_type.value)
    stmt = stmt.order_by(Incident.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{incident_id}", response_model=IncidentResponse)
async def get_incident(incident_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incident


@router.put("/{incident_id}", response_model=IncidentResponse)
async def update_incident(
    incident_id: int, payload: IncidentUpdate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, Enum):
            value = value.value
        setattr(incident, field, value)
    await db.commit()
    await db.refresh(incident)
    return incident


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(incident_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if incident is None:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    await db.delete(incident)
    await db.commit()
