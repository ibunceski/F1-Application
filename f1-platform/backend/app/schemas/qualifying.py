from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.driver import DriverResponse
from app.schemas.team import TeamResponse


class QualifyingResultResponse(BaseModel):
    id: int
    driver_id: int
    team_id: int
    position: Optional[int]
    q1_time_ms: Optional[float]
    q2_time_ms: Optional[float]
    q3_time_ms: Optional[float]
    best_time_ms: Optional[float]
    gap_to_pole_ms: Optional[float]
    driver: DriverResponse
    team: TeamResponse

    model_config = ConfigDict(from_attributes=True)
