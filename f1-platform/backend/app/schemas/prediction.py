from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.race import RaceResponse

PredictionContext = Literal["pre_qualifying", "post_qualifying"]
PredictionContextRequest = Literal["auto", "pre_qualifying", "post_qualifying"]


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
    prediction_context: PredictionContext
    model_context: PredictionContext
    feature_context: PredictionContext
    generated_at: datetime
    driver: PredictionDriverResponse
    team: PredictionTeamResponse
    grid_position: Optional[float]
    qualifying_position: Optional[float]
    gap_to_pole_ms: Optional[float]
    uses_current_qualifying: bool
    data_cutoff_date: date
    feature_generated_at: datetime
    predicted_position: Optional[float]
    predicted_rank: int
    top10_probability: Optional[float]
    podium_probability: Optional[float]
    winner_probability: Optional[float]
    predicted_position_gain: Optional[float]
    confidence_score: Optional[float]
    model_version: str

    model_config = ConfigDict(from_attributes=True)


class NextRacePredictionContextResponse(BaseModel):
    race: RaceResponse
    recommended_context: PredictionContext
    qualifying_available: bool
    race_date: date
    days_until_race: int


class NextRacePredictionGenerateRequest(BaseModel):
    context: PredictionContextRequest = "auto"
    force_regenerate: bool = False


class PredictionComparisonSummary(BaseModel):
    mae: float
    rmse: float
    top10_accuracy: float
    podium_accuracy: float
    winner_correct: bool
    average_position_error: float


class PredictionDriverComparisonResponse(BaseModel):
    driver: PredictionDriverResponse
    team: PredictionTeamResponse
    predicted_position: Optional[float]
    predicted_rank: int
    actual_position: Optional[int]
    actual_rank: Optional[int]
    position_error: Optional[float]
    predicted_top10: bool
    actual_top10: bool
    predicted_podium: bool
    actual_podium: bool
    points: float
    status: str


class PredictionComparisonResponse(BaseModel):
    race: RaceResponse
    context: PredictionContext
    model_version: str
    summary: PredictionComparisonSummary
    drivers: list[PredictionDriverComparisonResponse]
