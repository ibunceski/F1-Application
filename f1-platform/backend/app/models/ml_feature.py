from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MLFeature(Base):
    __tablename__ = "ml_features"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_ml_features_race_driver"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    grid_position: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    qualifying_position: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gap_to_pole_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_race_pace_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    driver_recent_form: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    team_recent_form: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    circuit_history_avg_finish: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    circuit_history_dnf_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dnf_rate_recent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weather_is_wet: Mapped[bool] = mapped_column(Boolean, nullable=False)
    avg_track_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"MLFeature(id={self.id!r}, race_id={self.race_id!r}, driver_id={self.driver_id!r})"
