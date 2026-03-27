import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class MissionType(str, enum.Enum):
    SEARCH_PATTERN = "search_pattern"
    INSPECTION = "inspection"
    MONITORING = "monitoring"
    CUSTOM = "custom"


class MissionStatus(str, enum.Enum):
    PLANNED = "planned"
    PREPARING = "preparing"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchPattern(str, enum.Enum):
    LAWNMOWER = "lawnmower"
    EXPANDING_SQUARE = "expanding_square"
    SECTOR = "sector"
    CREEPING_LINE = "creeping_line"
    PARALLEL_TRACK = "parallel_track"


class Mission(Base):
    __tablename__ = "missions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    drone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drones.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[MissionType] = mapped_column(
        Enum(MissionType, name="mission_type"), nullable=False
    )
    status: Mapped[MissionStatus] = mapped_column(
        Enum(MissionStatus, name="mission_status"),
        nullable=False,
        default=MissionStatus.PLANNED,
    )
    wayline_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    search_pattern: Mapped[SearchPattern | None] = mapped_column(
        Enum(SearchPattern, name="search_pattern"), nullable=True
    )
    area_polygon: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
