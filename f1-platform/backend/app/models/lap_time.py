from typing import Optional

from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, Index, Integer, String, UniqueConstraint, false
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LapTime(Base):
    __tablename__ = "lap_times"
    __table_args__ = (
        UniqueConstraint("race_id", "driver_id", "lap_number", name="uq_lap_times_race_driver_lap"),
        Index("ix_lap_times_race_compound", "race_id", "compound"),
        Index("ix_lap_times_compound", "compound"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    lap_number: Mapped[int] = mapped_column(Integer, nullable=False)
    lap_time_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector1_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector2_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sector3_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    compound: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    tyre_age_laps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stint_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_pit_out_lap: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    is_pit_in_lap: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    is_personal_best: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false(), nullable=False)

    def __repr__(self) -> str:
        return f"LapTime(id={self.id!r}, race_id={self.race_id!r}, driver_id={self.driver_id!r}, lap={self.lap_number!r})"
