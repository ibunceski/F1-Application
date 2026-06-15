from __future__ import annotations

from typing import Optional

from sqlalchemy import Float, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.driver import Driver
from app.models.team import Team


class QualifyingResult(Base):
    __tablename__ = "qualifying_results"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", name="uq_qualifying_results_race_driver"),
        Index("ix_qualifying_results_race_position", "race_id", "position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    q1_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    q2_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    q3_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    best_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gap_to_pole_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    driver: Mapped[Driver] = relationship("Driver")
    team: Mapped[Team] = relationship("Team")

    def __repr__(self) -> str:
        return f"QualifyingResult(id={self.id!r}, race_id={self.race_id!r}, driver_id={self.driver_id!r})"
