from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.detection import Detection, DetectionCategory, DetectionSeverity

router = APIRouter(prefix="/detections", tags=["detections"])


# ── Schemas ──────────────────────────────────────────────────────────────────


class DetectionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    mission_id: int
    drone_id: int
    category: DetectionCategory
    confidence: float
    latitude: float
    longitude: float
    altitude: float
    bbox: dict | None
    image_url: str | None
    severity: DetectionSeverity
    processed: bool
    created_at: datetime


class DetectionStats(BaseModel):
    total: int
    by_category: dict[str, int]
    by_severity: dict[str, int]


# ── Routes ───────────────────────────────────────────────────────────────────


@router.get("/stats", response_model=DetectionStats)
async def detection_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count(Detection.id)))
    total = total_result.scalar() or 0

    cat_stmt = select(Detection.category, func.count(Detection.id)).group_by(Detection.category)
    cat_result = await db.execute(cat_stmt)
    by_category = {row[0].value: row[1] for row in cat_result.all()}

    sev_stmt = select(Detection.severity, func.count(Detection.id)).group_by(Detection.severity)
    sev_result = await db.execute(sev_stmt)
    by_severity = {row[0].value: row[1] for row in sev_result.all()}

    return DetectionStats(total=total, by_category=by_category, by_severity=by_severity)


@router.get("", response_model=list[DetectionRead])
async def list_detections(
    mission_id: int | None = Query(None),
    category: DetectionCategory | None = Query(None),
    severity: DetectionSeverity | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Detection)
    if mission_id is not None:
        stmt = stmt.where(Detection.mission_id == mission_id)
    if category is not None:
        stmt = stmt.where(Detection.category == category)
    if severity is not None:
        stmt = stmt.where(Detection.severity == severity)
    stmt = stmt.order_by(Detection.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{detection_id}", response_model=DetectionRead)
async def get_detection(detection_id: int, db: AsyncSession = Depends(get_db)):
    detection = await db.get(Detection, detection_id)
    if detection is None:
        raise HTTPException(status_code=404, detail="Detection not found")
    return detection
