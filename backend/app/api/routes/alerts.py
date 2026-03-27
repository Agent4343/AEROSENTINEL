from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.alert import Alert, AlertSeverity

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class AlertOut(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    detection_id: int
    incident_id: int
    severity: AlertSeverity
    message: str
    acknowledged: bool
    auto_action_taken: str | None
    created_at: datetime
    acknowledged_at: datetime | None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", response_model=list[AlertOut])
async def list_alerts(
    severity: AlertSeverity | None = Query(None),
    acknowledged: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Alert)
    if severity is not None:
        stmt = stmt.where(Alert.severity == severity)
    if acknowledged is not None:
        stmt = stmt.where(Alert.acknowledged == acknowledged)
    stmt = stmt.order_by(Alert.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/active", response_model=list[AlertOut])
async def list_active_alerts(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(Alert)
        .where(Alert.acknowledged == False)  # noqa: E712
        .order_by(Alert.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(alert_id: int, db: AsyncSession = Depends(get_db)):
    alert = await db.get(Alert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.acknowledged:
        raise HTTPException(status_code=400, detail="Alert already acknowledged")
    alert.acknowledged = True
    alert.acknowledged_at = datetime.utcnow()
    await db.flush()
    await db.refresh(alert)
    return alert
