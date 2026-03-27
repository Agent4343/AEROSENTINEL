import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class DroneStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    FLYING = "flying"
    RETURNING = "returning"
    CHARGING = "charging"


class Drone(Base):
    __tablename__ = "drones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    serial_number: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DroneStatus] = mapped_column(
        Enum(DroneStatus, name="drone_status"),
        nullable=False,
        default=DroneStatus.OFFLINE,
    )
    dock_serial: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_telemetry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    telemetry: Mapped[list["DroneTelemetry"]] = relationship(
        back_populates="drone", lazy="selectin"
    )


class DroneTelemetry(Base):
    __tablename__ = "drone_telemetry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    drone_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("drones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    altitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    heading: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    battery_percent: Mapped[float] = mapped_column(Float, nullable=False)
    gimbal_pitch: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    gimbal_yaw: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    drone: Mapped["Drone"] = relationship(back_populates="telemetry")

    __table_args__ = (
        # TimescaleDB hypertable hint -- run after table creation:
        # SELECT create_hypertable('drone_telemetry', 'timestamp');
        {"comment": "TimescaleDB hypertable on timestamp column"},
    )
