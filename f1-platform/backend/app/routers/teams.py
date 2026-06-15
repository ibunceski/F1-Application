from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.team import TeamResponse
from app.services.team_service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])


def get_team_service(db: AsyncSession = Depends(get_db)) -> TeamService:
    return TeamService(db)


@router.get("", response_model=list[TeamResponse])
async def get_teams(
    season: Annotated[int | None, Query(description="Optional season year filter")] = None,
    service: TeamService = Depends(get_team_service),
) -> list[TeamResponse]:
    teams = await service.get_teams_by_season(season) if season is not None else await service.get_all_teams()
    return [TeamResponse.model_validate(team) for team in teams]


@router.get("/{team_id}", response_model=TeamResponse)
async def get_team(
    team_id: Annotated[int, Path(description="Team database identifier")],
    service: TeamService = Depends(get_team_service),
) -> TeamResponse:
    team = await service.get_team_by_id(team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return TeamResponse.model_validate(team)


@router.get("/{team_id}/stats")
async def get_team_stats(
    team_id: Annotated[int, Path(description="Team database identifier")],
    season: Annotated[int, Query(description="Season year for team statistics")],
    service: TeamService = Depends(get_team_service),
) -> dict[str, Any]:
    team = await service.get_team_by_id(team_id)
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return await service.get_team_season_stats(team_id, season)
