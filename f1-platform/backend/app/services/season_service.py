import logging
from typing import Any

from sqlalchemy import select

from app.models.driver import Driver
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.team import Team
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class SeasonService(BaseService):
    async def get_all_seasons(self) -> list[Season]:
        try:
            result = await self.db.execute(select(Season).order_by(Season.year.desc()))
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get all seasons")
            raise

    async def get_season_by_year(self, year: int) -> Season | None:
        try:
            result = await self.db.execute(select(Season).where(Season.year == year))
            return result.scalar_one_or_none()
        except Exception:
            logger.exception("Failed to get season by year=%s", year)
            raise

    async def get_season_with_stats(self, year: int) -> dict[str, Any] | None:
        try:
            season = await self.get_season_by_year(year)
            if season is None:
                return None

            races_result = await self.db.execute(
                select(Race).where(Race.season_id == season.id).order_by(Race.round_number.asc())
            )
            races = list(races_result.scalars().all())

            teams_result = await self.db.execute(
                select(Team)
                .join(RaceResult, RaceResult.team_id == Team.id)
                .join(Race, RaceResult.race_id == Race.id)
                .where(Race.season_id == season.id)
                .distinct()
                .order_by(Team.name.asc())
            )
            drivers_result = await self.db.execute(
                select(Driver)
                .join(RaceResult, RaceResult.driver_id == Driver.id)
                .join(Race, RaceResult.race_id == Race.id)
                .where(Race.season_id == season.id)
                .distinct()
                .order_by(Driver.full_name.asc())
            )
            return {
                "season": season,
                "race_count": len(races),
                "teams": list(teams_result.scalars().all()),
                "drivers": list(drivers_result.scalars().all()),
            }
        except Exception:
            logger.exception("Failed to get season stats for year=%s", year)
            raise
