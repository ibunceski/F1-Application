from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SeasonBase(BaseModel):
    year: int
    total_races: int
    champion_driver: Optional[str]
    champion_team: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class SeasonResponse(SeasonBase):
    id: int
    created_at: datetime
