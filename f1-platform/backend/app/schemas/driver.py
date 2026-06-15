from typing import Optional

from pydantic import BaseModel, ConfigDict


class DriverBase(BaseModel):
    driver_number: int
    full_name: str
    abbreviation: str
    nationality: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class DriverResponse(DriverBase):
    id: int
    driver_id: str
    team_id: Optional[int]
