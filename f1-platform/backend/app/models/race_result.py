from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.driver import Driver
from app.models.team import Team


class RaceResult(Base):
    __tablename__ = "race_results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_race_results_race_driver"),
        Index("ix_race_results_race_finishing_position", "race_id", "finishing_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    grid_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    finishing_position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    classified_position: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    points: Mapped[float] = mapped_column(Float, nullable=False)
    sprint_points: Mapped[float] = mapped_column(Float, default=0.0, server_default="0", nullable=False)
    laps_completed: Mapped[int] = mapped_column(Integer, nullable=False)
    fastest_lap: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    fastest_lap_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fastest_lap_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    driver: Mapped[Driver] = relationship("Driver")
    team: Mapped[Team] = relationship("Team")

    def __repr__(self) -> str:
        return f"RaceResult(id={self.id!r}, race_id={self.race_id!r}, driver_id={self.driver_id!r})"
