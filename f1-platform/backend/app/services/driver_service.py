import logging
from typing import Any

from sqlalchemy import select

from app.models.driver import Driver
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)
DNF_CLASSIFICATIONS = {"DNF", "DNQ", "DNS", "DSQ"}


class DriverService(BaseService):
    async def get_all_drivers(self) -> list[Driver]:
        try:
            result = await self.db.execute(select(Driver).order_by(Driver.full_name.asc()))
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get all drivers")
            raise

    async def get_driver_by_id(self, driver_id: int) -> Driver | None:
        try:
            result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
            return result.scalar_one_or_none()
        except Exception:
            logger.exception("Failed to get driver_id=%s", driver_id)
            raise

    async def get_drivers_by_season(self, season_year: int) -> list[Driver]:
        try:
            result = await self.db.execute(
                select(Driver)
                .join(RaceResult, RaceResult.driver_id == Driver.id)
                .join(Race, RaceResult.race_id == Race.id)
                .join(Season, Race.season_id == Season.id)
                .where(Season.year == season_year)
                .distinct()
                .order_by(Driver.full_name.asc())
            )
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get drivers for season_year=%s", season_year)
            raise

    async def get_driver_season_stats(self, driver_id: int, season_year: int) -> dict[str, Any]:
        try:
            result = await self.db.execute(
                select(RaceResult)
                .join(Race, RaceResult.race_id == Race.id)
                .join(Season, Race.season_id == Season.id)
                .where(RaceResult.driver_id == driver_id, Season.year == season_year)
            )
            rows = list(result.scalars().all())
            finishes = [row.finishing_position for row in rows if row.finishing_position is not None]
            dnf_count = sum(
                1
                for row in rows
                if row.finishing_position is None or (row.classified_position or "").upper() in DNF_CLASSIFICATIONS
            )
            return {
                "driver_id": driver_id,
                "season": season_year,
                "races_entered": len(rows),
                "avg_finish": sum(finishes) / len(finishes) if finishes else None,
                "best_finish": min(finishes) if finishes else None,
                "dnf_count": dnf_count,
                "total_points": sum(row.points for row in rows),
                "wins": sum(1 for row in rows if row.finishing_position == 1),
                "podiums": sum(1 for row in rows if row.finishing_position is not None and row.finishing_position <= 3),
                "top10s": sum(1 for row in rows if row.finishing_position is not None and row.finishing_position <= 10),
            }
        except Exception:
            logger.exception("Failed to get driver stats driver_id=%s season_year=%s", driver_id, season_year)
            raise
