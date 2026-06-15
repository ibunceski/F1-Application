from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.driver import DriverResponse
from app.schemas.season import SeasonResponse
from app.schemas.team import TeamResponse
from app.services.season_service import SeasonService

router = APIRouter(prefix="/seasons", tags=["Seasons"])


def get_season_service(db: AsyncSession = Depends(get_db)) -> SeasonService:
    return SeasonService(db)


@router.get("", response_model=list[SeasonResponse])
async def get_seasons(service: SeasonService = Depends(get_season_service)) -> list[SeasonResponse]:
    seasons = await service.get_all_seasons()
    return [SeasonResponse.model_validate(season) for season in seasons]


@router.get("/{year}", response_model=SeasonResponse)
async def get_season(
    year: Annotated[int, Path(description="F1 season year")],
    service: SeasonService = Depends(get_season_service),
) -> SeasonResponse:
    season = await service.get_season_by_year(year)
    if season is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return SeasonResponse.model_validate(season)


@router.get("/{year}/stats")
async def get_season_stats(
    year: Annotated[int, Path(description="F1 season year")],
    service: SeasonService = Depends(get_season_service),
) -> dict[str, Any]:
    stats = await service.get_season_with_stats(year)
    if stats is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Season not found")
    return {
        "season": SeasonResponse.model_validate(stats["season"]).model_dump(mode="json"),
        "race_count": stats["race_count"],
        "teams": [TeamResponse.model_validate(team).model_dump(mode="json") for team in stats["teams"]],
        "drivers": [DriverResponse.model_validate(driver).model_dump(mode="json") for driver in stats["drivers"]],
    }
