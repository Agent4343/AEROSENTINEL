import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class DetectionCategory(str, enum.Enum):
    FIRE = "fire"
    SMOKE = "smoke"
    PERSON = "person"
    VEHICLE = "vehicle"
    STRUCTURAL_DAMAGE = "structural_damage"
    FLOOD_WATER = "flood_water"
    HAZMAT = "hazmat"


class DetectionSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mission_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("missions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    drone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[DetectionCategory] = mapped_column(
        Enum(DetectionCategory, name="detection_category"), nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float] = mapped_column(Float, nullable=False)
    bbox: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    severity: Mapped[DetectionSeverity] = mapped_column(
        Enum(DetectionSeverity, name="detection_severity"),
        nullable=False,
        default=DetectionSeverity.MEDIUM,
    )
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
