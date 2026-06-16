from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.prediction import PredictionContext


class MLFeatureResponse(BaseModel):
    id: int
    race_id: int
    driver_id: int
    feature_context: PredictionContext
    grid_position: Optional[float]
    qualifying_position: Optional[float]
    gap_to_pole_ms: Optional[float]
    avg_race_pace_ms: Optional[float]
    driver_recent_form: Optional[float]
    team_recent_form: Optional[float]
    circuit_history_avg_finish: Optional[float]
    circuit_history_dnf_rate: Optional[float]
    dnf_rate_recent: Optional[float]
    weather_is_wet: bool
    avg_track_temp_c: Optional[float]
    generated_at: datetime
    uses_current_qualifying: bool
    data_cutoff_date: date

    model_config = ConfigDict(from_attributes=True)
