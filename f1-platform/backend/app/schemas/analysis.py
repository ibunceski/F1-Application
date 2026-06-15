from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class DriverLapSummary(BaseModel):
    driver_id: int
    driver_name: str
    abbreviation: str
    team_name: str
    avg_lap_time_ms: Optional[float]
    best_lap_time_ms: Optional[float]
    median_lap_time_ms: Optional[float]
    total_laps: int
    total_clean_laps: int

    model_config = ConfigDict(from_attributes=True)


class TyreStintInfo(BaseModel):
    compound: Optional[str]
    stint_number: Optional[int]
    start_lap: int
    end_lap: int
    laps_on_tyre: int
    avg_lap_time_ms: Optional[float]

    model_config = ConfigDict(from_attributes=True)


class DriverTyreStrategy(BaseModel):
    driver_id: int
    driver_name: str
    abbreviation: str
    team_name: str
    stints: list[TyreStintInfo]

    model_config = ConfigDict(from_attributes=True)


class DriverComparisonResponse(BaseModel):
    race_id: int
    driver1: DriverLapSummary
    driver2: DriverLapSummary
    sector_comparison: dict[str, Any]
    qualifying_comparison: dict[str, Any]
    race_result_comparison: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
