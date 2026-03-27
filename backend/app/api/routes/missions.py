from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.mission import Mission, MissionType, MissionStatus, SearchPattern

router = APIRouter(prefix="/missions", tags=["missions"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class MissionCreate(BaseModel):
    incident_id: int
    drone_id: int | None = None
    type: MissionType
    wayline_data: dict | None = None
    search_pattern: SearchPattern | None = None
    area_polygon: dict | None = None


class MissionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    incident_id: int
    drone_id: int | None
    type: MissionType
    status: MissionStatus
    wayline_data: dict | None
    search_pattern: SearchPattern | None
    area_polygon: dict | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


# ── Routes ───────────────────────────────────────────────────────────────────


@router.post("", response_model=MissionRead, status_code=201)
async def create_mission(body: MissionCreate, db: AsyncSession = Depends(get_db)):
    mission = Mission(**body.model_dump())
    db.add(mission)
    await db.flush()
    await db.refresh(mission)
    return mission


@router.get("", response_model=list[MissionRead])
async def list_missions(
    incident_id: int | None = Query(None),
    status: MissionStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Mission)
    if incident_id is not None:
        stmt = stmt.where(Mission.incident_id == incident_id)
    if status is not None:
        stmt = stmt.where(Mission.status == status)
    stmt = stmt.order_by(Mission.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{mission_id}", response_model=MissionRead)
async def get_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    mission = await db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.post("/{mission_id}/execute", response_model=MissionRead)
async def execute_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    mission = await db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status not in (MissionStatus.PLANNED, MissionStatus.PREPARING):
        raise HTTPException(status_code=400, detail="Mission cannot be executed from current status")
    mission.status = MissionStatus.EXECUTING
    mission.started_at = datetime.utcnow()
    await db.flush()
    await db.refresh(mission)
    return mission


@router.post("/{mission_id}/pause", response_model=MissionRead)
async def pause_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    mission = await db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status != MissionStatus.EXECUTING:
        raise HTTPException(status_code=400, detail="Only executing missions can be paused")
    mission.status = MissionStatus.PAUSED
    await db.flush()
    await db.refresh(mission)
    return mission


@router.post("/{mission_id}/resume", response_model=MissionRead)
async def resume_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    mission = await db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status_code=404, detail="Mission not found")
    if mission.status != MissionStatus.PAUSED:
        raise HTTPException(status_code=400, detail="Only paused missions can be resumed")
    mission.status = MissionStatus.EXECUTING
    await db.flush()
    await db.refresh(mission)
    return mission
