from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models import Alert

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertSeverityEnum(str, Enum):
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"


class AlertResponse(BaseModel):
    id: int
    detection_id: int
    incident_id: int
    severity: str
    message: str
    acknowledged: bool
    auto_action_taken: Optional[str] = None
    created_at: datetime
    acknowledged_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AcknowledgeResponse(BaseModel):
    id: int
    acknowledged: bool
    acknowledged_at: datetime


@router.get("/active", response_model=list[AlertResponse])
async def list_active_alerts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Alert)
        .where(Alert.acknowledged == False)
        .order_by(Alert.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("", response_model=list[AlertResponse])
async def list_alerts(
    severity: Optional[AlertSeverityEnum] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Alert)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity.value)
    if acknowledged is not None:
        stmt = stmt.where(Alert.acknowledged == acknowledged)
    stmt = stmt.order_by(Alert.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{alert_id}/acknowledge", response_model=AcknowledgeResponse)
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Alert).where(Alert.id == alert_id))
    alert = result.scalar_one_or_none()
    if alert is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    if alert.acknowledged:
        raise HTTPException(status_code=409, detail=f"Alert {alert_id} already acknowledged")
    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    await db.commit()
    await db.refresh(alert)
    return AcknowledgeResponse(id=alert.id, acknowledged=True, acknowledged_at=alert.acknowledged_at)
