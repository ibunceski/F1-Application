from typing import Optional

from pydantic import BaseModel, ConfigDict


class LapTimeResponse(BaseModel):
    id: int
    lap_number: int
    lap_time_ms: Optional[float]
    sector1_ms: Optional[float]
    sector2_ms: Optional[float]
    sector3_ms: Optional[float]
    compound: Optional[str]
    tyre_age_laps: Optional[int]
    stint_number: Optional[int]
    is_pit_out_lap: bool
    is_pit_in_lap: bool
    is_personal_best: bool
    deleted: bool

    model_config = ConfigDict(from_attributes=True)
