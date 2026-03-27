from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import Mission, Incident, Drone

router = APIRouter(prefix="/missions", tags=["missions"])


class MissionStatusEnum(str, Enum):
    planned = "planned"
    preparing = "preparing"
    executing = "executing"
    paused = "paused"
    completed = "completed"
    failed = "failed"


class MissionCreate(BaseModel):
    incident_id: int
    drone_id: Optional[int] = None
    type: str
    search_pattern: Optional[str] = None
    area_polygon: Optional[dict] = None


class MissionResponse(BaseModel):
    id: int
    incident_id: int
    drone_id: Optional[int] = None
    type: str
    status: str
    search_pattern: Optional[str] = None
    wayline_data: Optional[dict] = None
    area_polygon: Optional[dict] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MissionActionResponse(BaseModel):
    id: int
    status: str
    message: str


async def _get_mission_or_404(mission_id: int, db: AsyncSession) -> Mission:
    result = await db.execute(select(Mission).where(Mission.id == mission_id))
    mission = result.scalar_one_or_none()
    if mission is None:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} not found")
    return mission


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
async def create_mission(payload: MissionCreate, db: AsyncSession = Depends(get_db)):
    inc = await db.execute(select(Incident).where(Incident.id == payload.incident_id))
    if inc.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Incident {payload.incident_id} not found")
    mission = Mission(
        incident_id=payload.incident_id,
        drone_id=payload.drone_id,
        type=payload.type,
        status="planned",
        search_pattern=payload.search_pattern,
        area_polygon=payload.area_polygon,
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)
    return mission


@router.get("", response_model=list[MissionResponse])
async def list_missions(
    incident_id: Optional[int] = Query(None),
    status_filter: Optional[MissionStatusEnum] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Mission)
    if incident_id is not None:
        stmt = stmt.where(Mission.incident_id == incident_id)
    if status_filter is not None:
        stmt = stmt.where(Mission.status == status_filter.value)
    stmt = stmt.order_by(Mission.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    return await _get_mission_or_404(mission_id, db)


@router.post("/{mission_id}/execute", response_model=MissionActionResponse)
async def execute_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    mission = await _get_mission_or_404(mission_id, db)
    if mission.status != "planned":
        raise HTTPException(status_code=409, detail=f"Mission must be 'planned', got '{mission.status}'")
    mission.status = "executing"
    mission.started_at = datetime.utcnow()
    await db.commit()
    return MissionActionResponse(id=mission.id, status=mission.status, message="Mission execution started")


@router.post("/{mission_id}/pause", response_model=MissionActionResponse)
async def pause_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    mission = await _get_mission_or_404(mission_id, db)
    if mission.status != "executing":
        raise HTTPException(status_code=409, detail=f"Mission must be 'executing', got '{mission.status}'")
    mission.status = "paused"
    await db.commit()
    return MissionActionResponse(id=mission.id, status=mission.status, message="Mission paused")


@router.post("/{mission_id}/resume", response_model=MissionActionResponse)
async def resume_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    mission = await _get_mission_or_404(mission_id, db)
    if mission.status != "paused":
        raise HTTPException(status_code=409, detail=f"Mission must be 'paused', got '{mission.status}'")
    mission.status = "executing"
    await db.commit()
    return MissionActionResponse(id=mission.id, status=mission.status, message="Mission resumed")
