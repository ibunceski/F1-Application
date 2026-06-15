from typing import Optional

from pydantic import BaseModel, ConfigDict

class PredictionDriverResponse(BaseModel):
    id: int
    full_name: str
    abbreviation: str
    driver_number: int


class PredictionTeamResponse(BaseModel):
    id: int
    name: str
    short_name: str


class PredictionResponse(BaseModel):
    id: int
    driver_id: int
    driver: PredictionDriverResponse
    team: PredictionTeamResponse
    grid_position: Optional[float]
    predicted_position: Optional[float]
    predicted_rank: int
    top10_probability: Optional[float]
    podium_probability: Optional[float]
    winner_probability: Optional[float]
    predicted_position_gain: Optional[float]
    confidence_score: Optional[float]
    model_version: str

    model_config = ConfigDict(from_attributes=True)
