from typing import Optional

from pydantic import BaseModel, ConfigDict


class TeamBase(BaseModel):
    name: str
    short_name: str
    nationality: Optional[str]
    constructor_id: str

    model_config = ConfigDict(from_attributes=True)


class TeamResponse(TeamBase):
    id: int
