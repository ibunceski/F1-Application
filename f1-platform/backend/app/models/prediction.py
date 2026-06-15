from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Prediction(Base):
    __tablename__ = "predictions"
    __table_args__ = (
        UniqueConstraint(
            "race_id",
            "driver_id",
            "model_version",
            name="uq_predictions_race_driver_model_version",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    race_id: Mapped[int] = mapped_column(ForeignKey("races.id", ondelete="CASCADE"), nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    predicted_position: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    top10_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    podium_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    winner_probability: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_position_gain: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"Prediction(id={self.id!r}, race_id={self.race_id!r}, driver_id={self.driver_id!r}, model_version={self.model_version!r})"
