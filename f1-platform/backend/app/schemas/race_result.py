from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.driver import DriverResponse
from app.schemas.team import TeamResponse


class RaceResultResponse(BaseModel):
    id: int
    driver_id: int
    team_id: int
    grid_position: Optional[int]
    finishing_position: Optional[int]
    classified_position: Optional[str]
    status: str
    points: float
    laps_completed: int
    fastest_lap: bool
    fastest_lap_time_ms: Optional[float]
    driver: DriverResponse
    team: TeamResponse

    model_config = ConfigDict(from_attributes=True)
