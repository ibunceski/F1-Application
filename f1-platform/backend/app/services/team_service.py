import logging
from typing import Any

from sqlalchemy import select

from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.team import Team
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class TeamService(BaseService):
    async def get_all_teams(self) -> list[Team]:
        try:
            result = await self.db.execute(select(Team).order_by(Team.name.asc()))
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get all teams")
            raise

    async def get_team_by_id(self, team_id: int) -> Team | None:
        try:
            result = await self.db.execute(select(Team).where(Team.id == team_id))
            return result.scalar_one_or_none()
        except Exception:
            logger.exception("Failed to get team_id=%s", team_id)
            raise

    async def get_teams_by_season(self, season_year: int) -> list[Team]:
        try:
            result = await self.db.execute(
                select(Team)
                .join(RaceResult, RaceResult.team_id == Team.id)
                .join(Race, RaceResult.race_id == Race.id)
                .join(Season, Race.season_id == Season.id)
                .where(Season.year == season_year)
                .distinct()
                .order_by(Team.name.asc())
            )
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get teams for season_year=%s", season_year)
            raise

    async def get_team_season_stats(self, team_id: int, season_year: int) -> dict[str, Any]:
        try:
            result = await self.db.execute(
                select(RaceResult)
                .join(Race, RaceResult.race_id == Race.id)
                .join(Season, Race.season_id == Season.id)
                .where(RaceResult.team_id == team_id, Season.year == season_year)
            )
            rows = list(result.scalars().all())
            finishes = [row.finishing_position for row in rows if row.finishing_position is not None]
            race_ids = {row.race_id for row in rows}
            return {
                "team_id": team_id,
                "season": season_year,
                "races": len(race_ids),
                "total_points": sum(row.points for row in rows),
                "avg_finish": sum(finishes) / len(finishes) if finishes else None,
                "wins": sum(1 for row in rows if row.finishing_position == 1),
                "podiums": sum(1 for row in rows if row.finishing_position is not None and row.finishing_position <= 3),
                "top10s": sum(1 for row in rows if row.finishing_position is not None and row.finishing_position <= 10),
            }
        except Exception:
            logger.exception("Failed to get team stats team_id=%s season_year=%s", team_id, season_year)
            raise
