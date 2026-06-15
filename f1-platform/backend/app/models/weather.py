from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WeatherData(Base):
    __tablename__ = "weather_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    session_type: Mapped[str] = mapped_column(String, nullable=False)
    timestamp_offset_s: Mapped[float] = mapped_column(Float, nullable=False)
    air_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    track_temp_c: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    humidity_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rainfall: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    wind_speed_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    wind_direction_deg: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"WeatherData(id={self.id!r}, race_id={self.race_id!r}, session_type={self.session_type!r})"
