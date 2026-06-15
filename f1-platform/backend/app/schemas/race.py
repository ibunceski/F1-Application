from datetime import date

from pydantic import BaseModel, ConfigDict


class RaceBase(BaseModel):
    round_number: int
    circuit_name: str
    circuit_location: str
    circuit_country: str
    race_name: str
    race_date: date

    model_config = ConfigDict(from_attributes=True)


class RaceResponse(RaceBase):
    id: int
    season_id: int


class RaceListResponse(BaseModel):
    total: int
    items: list[RaceResponse]

    model_config = ConfigDict(from_attributes=True)
