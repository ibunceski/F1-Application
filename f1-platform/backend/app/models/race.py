from datetime import date
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Race(Base):
    __tablename__ = "races"
    __table_args__ = (
        UniqueConstraint("season_id", "round_number", name="uq_races_season_round"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    circuit_name: Mapped[str] = mapped_column(String, nullable=False)
    circuit_location: Mapped[str] = mapped_column(String, nullable=False)
    circuit_country: Mapped[str] = mapped_column(String, nullable=False)
    race_name: Mapped[str] = mapped_column(String, nullable=False)
    race_date: Mapped[date] = mapped_column(nullable=False)
    session_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    def __repr__(self) -> str:
        return f"Race(id={self.id!r}, season_id={self.season_id!r}, round={self.round_number!r})"
