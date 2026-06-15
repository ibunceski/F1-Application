import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


class RaceService(BaseService):
    async def get_races_by_season(self, season_year: int) -> list[Race]:
        try:
            result = await self.db.execute(
                select(Race)
                .join(Season, Race.season_id == Season.id)
                .where(Season.year == season_year)
                .order_by(Race.round_number.asc())
            )
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get races for season_year=%s", season_year)
            raise

    async def get_race_by_id(self, race_id: int) -> Race | None:
        try:
            result = await self.db.execute(select(Race).where(Race.id == race_id))
            return result.scalar_one_or_none()
        except Exception:
            logger.exception("Failed to get race_id=%s", race_id)
            raise

    async def get_race_by_round(self, season_year: int, round_number: int) -> Race | None:
        try:
            result = await self.db.execute(
                select(Race)
                .join(Season, Race.season_id == Season.id)
                .where(Season.year == season_year, Race.round_number == round_number)
            )
            return result.scalar_one_or_none()
        except Exception:
            logger.exception("Failed to get race season_year=%s round=%s", season_year, round_number)
            raise

    async def get_next_race(self, from_date: date) -> Race | None:
        try:
            result = await self.db.execute(
                select(Race).where(Race.race_date >= from_date).order_by(Race.race_date.asc()).limit(1)
            )
            return result.scalar_one_or_none()
        except Exception:
            logger.exception("Failed to get next race from_date=%s", from_date)
            raise

    async def get_qualifying_results(self, race_id: int) -> list[QualifyingResult]:
        try:
            result = await self.db.execute(
                select(QualifyingResult)
                .where(QualifyingResult.race_id == race_id)
                .options(selectinload(QualifyingResult.driver), selectinload(QualifyingResult.team))
                .order_by(QualifyingResult.position.asc().nulls_last())
            )
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get qualifying results for race_id=%s", race_id)
            raise

    async def get_race_results(self, race_id: int) -> list[RaceResult]:
        try:
            result = await self.db.execute(
                select(RaceResult)
                .where(RaceResult.race_id == race_id)
                .options(selectinload(RaceResult.driver), selectinload(RaceResult.team))
                .order_by(RaceResult.finishing_position.asc().nulls_last())
            )
            return list(result.scalars().all())
        except Exception:
            logger.exception("Failed to get race results for race_id=%s", race_id)
            raise
