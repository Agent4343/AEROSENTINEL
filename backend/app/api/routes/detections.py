from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import Detection

router = APIRouter(prefix="/detections", tags=["detections"])


class DetectionCategoryEnum(str, Enum):
    fire = "fire"
    smoke = "smoke"
    person = "person"
    vehicle = "vehicle"
    structural_damage = "structural_damage"
    flood_water = "flood_water"
    hazmat = "hazmat"


class DetectionSeverityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class DetectionResponse(BaseModel):
    id: int
    mission_id: int
    drone_id: int
    category: str
    confidence: float
    latitude: float
    longitude: float
    altitude: float
    bbox: Optional[dict] = None
    image_url: Optional[str] = None
    severity: str
    processed: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class CategoryCount(BaseModel):
    category: str
    count: int


class SeverityCount(BaseModel):
    severity: str
    count: int


class DetectionStatsResponse(BaseModel):
    total: int
    by_category: list[CategoryCount]
    by_severity: list[SeverityCount]


@router.get("/stats", response_model=DetectionStatsResponse)
async def get_detection_stats(
    mission_id: Optional[int] = Query(None), db: AsyncSession = Depends(get_db)
):
    base_filter = []
    if mission_id is not None:
        base_filter.append(Detection.mission_id == mission_id)

    total_stmt = select(func.count(Detection.id))
    if base_filter:
        total_stmt = total_stmt.where(*base_filter)
    total = (await db.execute(total_stmt)).scalar() or 0

    cat_stmt = select(Detection.category, func.count(Detection.id).label("count")).group_by(Detection.category)
    if base_filter:
        cat_stmt = cat_stmt.where(*base_filter)
    by_category = [{"category": r.category, "count": r.count} for r in (await db.execute(cat_stmt)).all()]

    sev_stmt = select(Detection.severity, func.count(Detection.id).label("count")).group_by(Detection.severity)
    if base_filter:
        sev_stmt = sev_stmt.where(*base_filter)
    by_severity = [{"severity": r.severity, "count": r.count} for r in (await db.execute(sev_stmt)).all()]

    return {"total": total, "by_category": by_category, "by_severity": by_severity}


@router.get("", response_model=list[DetectionResponse])
async def list_detections(
    mission_id: Optional[int] = Query(None),
    category: Optional[DetectionCategoryEnum] = Query(None),
    severity: Optional[DetectionSeverityEnum] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Detection)
    if mission_id is not None:
        stmt = stmt.where(Detection.mission_id == mission_id)
    if category is not None:
        stmt = stmt.where(Detection.category == category.value)
    if severity is not None:
        stmt = stmt.where(Detection.severity == severity.value)
    stmt = stmt.order_by(Detection.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{detection_id}", response_model=DetectionResponse)
async def get_detection(detection_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Detection).where(Detection.id == detection_id))
    detection = result.scalar_one_or_none()
    if detection is None:
        raise HTTPException(status_code=404, detail=f"Detection {detection_id} not found")
    return detection
