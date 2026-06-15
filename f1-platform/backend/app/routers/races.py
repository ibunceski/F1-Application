from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.qualifying import QualifyingResultResponse
from app.schemas.race import RaceResponse
from app.schemas.race_result import RaceResultResponse
from app.services.race_service import RaceService

router = APIRouter(prefix="/races", tags=["Races"])


def get_race_service(db: AsyncSession = Depends(get_db)) -> RaceService:
    return RaceService(db)


@router.get("", response_model=list[RaceResponse])
async def get_races(
    season: Annotated[int, Query(description="Season year to list races for")],
    service: RaceService = Depends(get_race_service),
) -> list[RaceResponse]:
    races = await service.get_races_by_season(season)
    return [RaceResponse.model_validate(race) for race in races]


@router.get("/next", response_model=RaceResponse)
async def get_next_race(service: RaceService = Depends(get_race_service)) -> RaceResponse:
    race = await service.get_next_race(date.today())
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")
    return RaceResponse.model_validate(race)


@router.get("/{race_id}", response_model=RaceResponse)
async def get_race(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: RaceService = Depends(get_race_service),
) -> RaceResponse:
    race = await service.get_race_by_id(race_id)
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")
    return RaceResponse.model_validate(race)


@router.get("/{race_id}/qualifying", response_model=list[QualifyingResultResponse])
async def get_race_qualifying(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: RaceService = Depends(get_race_service),
) -> list[QualifyingResultResponse]:
    race = await service.get_race_by_id(race_id)
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")
    results = await service.get_qualifying_results(race_id)
    return [QualifyingResultResponse.model_validate(result) for result in results]


@router.get("/{race_id}/results", response_model=list[RaceResultResponse])
async def get_race_results(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: RaceService = Depends(get_race_service),
) -> list[RaceResultResponse]:
    race = await service.get_race_by_id(race_id)
    if race is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")
    results = await service.get_race_results(race_id)
    return [RaceResultResponse.model_validate(result) for result in results]
