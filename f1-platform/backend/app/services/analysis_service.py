import logging
import time
from collections import defaultdict
from statistics import mean, median
from typing import Any

from sqlalchemy import Select, select

from app.models.driver import Driver
from app.models.lap_time import LapTime
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.team import Team
from app.models.weather import WeatherData
from app.schemas.analysis import DriverComparisonResponse, DriverLapSummary, DriverTyreStrategy, TyreStintInfo
from app.schemas.lap_time import LapTimeResponse
from app.services.base_service import BaseService

logger = logging.getLogger(__name__)


def _avg(values: list[float]) -> float | None:
    return float(mean(values)) if values else None


def _median(values: list[float]) -> float | None:
    return float(median(values)) if values else None


class AnalysisService(BaseService):
    async def race_exists(self, race_id: int) -> bool:
        race = await self.db.get(Race, race_id)
        return race is not None

    async def driver_raced(self, race_id: int, driver_id: int) -> bool:
        result = await self.db.execute(
            select(RaceResult.id).where(RaceResult.race_id == race_id, RaceResult.driver_id == driver_id)
        )
        return result.scalar_one_or_none() is not None

    def _clean_lap_filters(self, query: Select[Any], exclude_pit_laps: bool = True) -> Select[Any]:
        query = query.where(LapTime.deleted.is_(False))
        if exclude_pit_laps:
            query = query.where(LapTime.is_pit_out_lap.is_(False), LapTime.is_pit_in_lap.is_(False))
        return query

    async def _driver_team_info(self, race_id: int, driver_id: int) -> tuple[Driver, Team | None]:
        result = await self.db.execute(
            select(Driver, Team)
            .outerjoin(RaceResult, (RaceResult.driver_id == Driver.id) & (RaceResult.race_id == race_id))
            .outerjoin(Team, Team.id == RaceResult.team_id)
            .where(Driver.id == driver_id)
        )
        row = result.first()
        if row is None:
            raise ValueError(f"Driver {driver_id} not found")
        return row[0], row[1]

    async def get_lap_times(
        self,
        race_id: int,
        driver_id: int | None = None,
        exclude_pit_laps: bool = True,
    ) -> list[dict[str, Any]]:
        started_at = time.monotonic()
        try:
            query = (
                select(LapTime, Driver, Team)
                .join(Driver, LapTime.driver_id == Driver.id)
                .outerjoin(RaceResult, (RaceResult.driver_id == Driver.id) & (RaceResult.race_id == LapTime.race_id))
                .outerjoin(Team, Team.id == RaceResult.team_id)
                .where(LapTime.race_id == race_id)
                .order_by(Driver.abbreviation.asc(), LapTime.lap_number.asc())
            )
            if driver_id is not None:
                query = query.where(LapTime.driver_id == driver_id)
            query = self._clean_lap_filters(query, exclude_pit_laps)

            rows = list((await self.db.execute(query)).all())
            grouped: dict[int, dict[str, Any]] = {}
            for lap, driver, team in rows:
                entry = grouped.setdefault(
                    driver.id,
                    {
                        "driver_id": driver.id,
                        "driver_name": driver.full_name,
                        "abbreviation": driver.abbreviation,
                        "team_name": team.name if team else None,
                        "laps": [],
                    },
                )
                entry["laps"].append(LapTimeResponse.model_validate(lap).model_dump(mode="json"))
            return list(grouped.values())
        except Exception:
            logger.exception("Failed get_lap_times race_id=%s driver_id=%s", race_id, driver_id)
            raise
        finally:
            logger.info("get_lap_times race_id=%s driver_id=%s took %.3fs", race_id, driver_id, time.monotonic() - started_at)

    async def get_driver_lap_summary(self, race_id: int, driver_id: int) -> DriverLapSummary:
        started_at = time.monotonic()
        try:
            all_laps = list(
                (
                    await self.db.execute(
                        select(LapTime).where(LapTime.race_id == race_id, LapTime.driver_id == driver_id)
                    )
                )
                .scalars()
                .all()
            )
            clean_laps = [
                lap
                for lap in all_laps
                if not lap.deleted and not lap.is_pit_in_lap and not lap.is_pit_out_lap and lap.lap_time_ms is not None
            ]
            lap_times = [lap.lap_time_ms for lap in clean_laps if lap.lap_time_ms is not None]
            driver, team = await self._driver_team_info(race_id, driver_id)
            return DriverLapSummary(
                driver_id=driver.id,
                driver_name=driver.full_name,
                abbreviation=driver.abbreviation,
                team_name=team.name if team else "Unknown",
                avg_lap_time_ms=_avg(lap_times),
                best_lap_time_ms=min(lap_times) if lap_times else None,
                median_lap_time_ms=_median(lap_times),
                total_laps=len(all_laps),
                total_clean_laps=len(clean_laps),
            )
        except Exception:
            logger.exception("Failed get_driver_lap_summary race_id=%s driver_id=%s", race_id, driver_id)
            raise
        finally:
            logger.info("get_driver_lap_summary race_id=%s driver_id=%s took %.3fs", race_id, driver_id, time.monotonic() - started_at)

    async def get_tyre_strategy(self, race_id: int) -> list[DriverTyreStrategy]:
        started_at = time.monotonic()
        try:
            rows = list(
                (
                    await self.db.execute(
                        select(LapTime, Driver, Team)
                        .join(Driver, LapTime.driver_id == Driver.id)
                        .outerjoin(RaceResult, (RaceResult.driver_id == Driver.id) & (RaceResult.race_id == LapTime.race_id))
                        .outerjoin(Team, Team.id == RaceResult.team_id)
                        .where(LapTime.race_id == race_id)
                        .order_by(LapTime.driver_id.asc(), LapTime.lap_number.asc())
                    )
                )
                .all()
            )
            grouped: dict[int, dict[str, Any]] = {}
            stint_laps: dict[tuple[int, int | None, str | None], list[LapTime]] = defaultdict(list)
            for lap, driver, team in rows:
                grouped.setdefault(
                    driver.id,
                    {"driver": driver, "team": team, "stints": []},
                )
                stint_laps[(driver.id, lap.stint_number, lap.compound)].append(lap)

            for (driver_id, stint_number, compound), laps in stint_laps.items():
                lap_times = [
                    lap.lap_time_ms
                    for lap in laps
                    if lap.lap_time_ms is not None and not lap.deleted and not lap.is_pit_in_lap and not lap.is_pit_out_lap
                ]
                start_lap = min(lap.lap_number for lap in laps)
                end_lap = max(lap.lap_number for lap in laps)
                grouped[driver_id]["stints"].append(
                    TyreStintInfo(
                        compound=compound,
                        stint_number=stint_number,
                        start_lap=start_lap,
                        end_lap=end_lap,
                        laps_on_tyre=end_lap - start_lap + 1,
                        avg_lap_time_ms=_avg(lap_times),
                    )
                )

            strategies: list[DriverTyreStrategy] = []
            for value in grouped.values():
                driver = value["driver"]
                team = value["team"]
                strategies.append(
                    DriverTyreStrategy(
                        driver_id=driver.id,
                        driver_name=driver.full_name,
                        abbreviation=driver.abbreviation,
                        team_name=team.name if team else "Unknown",
                        stints=sorted(value["stints"], key=lambda stint: stint.stint_number or 0),
                    )
                )
            return strategies
        except Exception:
            logger.exception("Failed get_tyre_strategy race_id=%s", race_id)
            raise
        finally:
            logger.info("get_tyre_strategy race_id=%s took %.3fs", race_id, time.monotonic() - started_at)

    async def get_position_changes(self, race_id: int) -> list[dict[str, Any]]:
        started_at = time.monotonic()
        try:
            result = await self.db.execute(
                select(RaceResult, QualifyingResult, Driver, Team)
                .join(Driver, RaceResult.driver_id == Driver.id)
                .join(Team, RaceResult.team_id == Team.id)
                .outerjoin(
                    QualifyingResult,
                    (QualifyingResult.race_id == RaceResult.race_id)
                    & (QualifyingResult.driver_id == RaceResult.driver_id),
                )
                .where(RaceResult.race_id == race_id)
                .order_by(RaceResult.finishing_position.asc().nulls_last())
            )
            data = []
            for race_result, qualifying_result, driver, team in result.all():
                position_change = (
                    race_result.grid_position - race_result.finishing_position
                    if race_result.grid_position is not None and race_result.finishing_position is not None
                    else None
                )
                data.append(
                    {
                        "driver": {
                            "id": driver.id,
                            "driver_id": driver.driver_id,
                            "driver_number": driver.driver_number,
                            "full_name": driver.full_name,
                            "abbreviation": driver.abbreviation,
                            "nationality": driver.nationality,
                            "team_id": driver.team_id,
                        },
                        "team": {
                            "id": team.id,
                            "name": team.name,
                            "short_name": team.short_name,
                            "nationality": team.nationality,
                            "constructor_id": team.constructor_id,
                        },
                        "qualifying_position": qualifying_result.position if qualifying_result else None,
                        "starting_position": race_result.grid_position,
                        "finishing_position": race_result.finishing_position,
                        "classified_position": race_result.classified_position,
                        "position_change": position_change,
                    }
                )
            return data
        except Exception:
            logger.exception("Failed get_position_changes race_id=%s", race_id)
            raise
        finally:
            logger.info("get_position_changes race_id=%s took %.3fs", race_id, time.monotonic() - started_at)

    async def _sector_averages(self, race_id: int, driver_id: int) -> dict[str, float | None]:
        laps = list(
            (
                await self.db.execute(
                    select(LapTime).where(
                        LapTime.race_id == race_id,
                        LapTime.driver_id == driver_id,
                        LapTime.deleted.is_(False),
                        LapTime.is_pit_in_lap.is_(False),
                        LapTime.is_pit_out_lap.is_(False),
                    )
                )
            )
            .scalars()
            .all()
        )
        return {
            "avg_sector1_ms": _avg([lap.sector1_ms for lap in laps if lap.sector1_ms is not None]),
            "avg_sector2_ms": _avg([lap.sector2_ms for lap in laps if lap.sector2_ms is not None]),
            "avg_sector3_ms": _avg([lap.sector3_ms for lap in laps if lap.sector3_ms is not None]),
        }

    async def get_driver_comparison(self, race_id: int, driver1_id: int, driver2_id: int) -> DriverComparisonResponse:
        started_at = time.monotonic()
        try:
            driver1 = await self.get_driver_lap_summary(race_id, driver1_id)
            driver2 = await self.get_driver_lap_summary(race_id, driver2_id)
            q_rows = list(
                (
                    await self.db.execute(
                        select(QualifyingResult).where(
                            QualifyingResult.race_id == race_id,
                            QualifyingResult.driver_id.in_([driver1_id, driver2_id]),
                        )
                    )
                )
                .scalars()
                .all()
            )
            r_rows = list(
                (
                    await self.db.execute(
                        select(RaceResult).where(
                            RaceResult.race_id == race_id,
                            RaceResult.driver_id.in_([driver1_id, driver2_id]),
                        )
                    )
                )
                .scalars()
                .all()
            )
            q_by_driver = {row.driver_id: row for row in q_rows}
            r_by_driver = {row.driver_id: row for row in r_rows}
            return DriverComparisonResponse(
                race_id=race_id,
                driver1=driver1,
                driver2=driver2,
                sector_comparison={
                    str(driver1_id): await self._sector_averages(race_id, driver1_id),
                    str(driver2_id): await self._sector_averages(race_id, driver2_id),
                },
                qualifying_comparison={
                    str(driver_id): {
                        "position": q_by_driver.get(driver_id).position if q_by_driver.get(driver_id) else None,
                        "gap_to_pole_ms": q_by_driver.get(driver_id).gap_to_pole_ms if q_by_driver.get(driver_id) else None,
                    }
                    for driver_id in [driver1_id, driver2_id]
                },
                race_result_comparison={
                    str(driver_id): {
                        "finishing_position": r_by_driver.get(driver_id).finishing_position if r_by_driver.get(driver_id) else None,
                        "status": r_by_driver.get(driver_id).status if r_by_driver.get(driver_id) else None,
                        "points": r_by_driver.get(driver_id).points if r_by_driver.get(driver_id) else None,
                    }
                    for driver_id in [driver1_id, driver2_id]
                },
            )
        except Exception:
            logger.exception(
                "Failed get_driver_comparison race_id=%s driver1_id=%s driver2_id=%s",
                race_id,
                driver1_id,
                driver2_id,
            )
            raise
        finally:
            logger.info(
                "get_driver_comparison race_id=%s driver1_id=%s driver2_id=%s took %.3fs",
                race_id,
                driver1_id,
                driver2_id,
                time.monotonic() - started_at,
            )

    async def get_fastest_laps(self, race_id: int) -> list[dict[str, Any]]:
        started_at = time.monotonic()
        try:
            rows = list(
                (
                    await self.db.execute(
                        select(LapTime, Driver, Team)
                        .join(Driver, LapTime.driver_id == Driver.id)
                        .outerjoin(RaceResult, (RaceResult.driver_id == Driver.id) & (RaceResult.race_id == LapTime.race_id))
                        .outerjoin(Team, Team.id == RaceResult.team_id)
                        .where(
                            LapTime.race_id == race_id,
                            LapTime.deleted.is_(False),
                            LapTime.is_pit_in_lap.is_(False),
                            LapTime.is_pit_out_lap.is_(False),
                            LapTime.lap_time_ms.is_not(None),
                        )
                        .order_by(LapTime.driver_id.asc(), LapTime.lap_time_ms.asc())
                    )
                )
                .all()
            )
            fastest_by_driver: dict[int, tuple[LapTime, Driver, Team | None]] = {}
            for lap, driver, team in rows:
                fastest_by_driver.setdefault(driver.id, (lap, driver, team))
            return sorted(
                [
                    {
                        "driver": {"id": driver.id, "full_name": driver.full_name, "abbreviation": driver.abbreviation},
                        "team": {"id": team.id, "name": team.name} if team else None,
                        "lap_number": lap.lap_number,
                        "lap_time_ms": lap.lap_time_ms,
                        "compound": lap.compound,
                        "sector1_ms": lap.sector1_ms,
                        "sector2_ms": lap.sector2_ms,
                        "sector3_ms": lap.sector3_ms,
                    }
                    for lap, driver, team in fastest_by_driver.values()
                ],
                key=lambda item: item["lap_time_ms"] or float("inf"),
            )
        except Exception:
            logger.exception("Failed get_fastest_laps race_id=%s", race_id)
            raise
        finally:
            logger.info("get_fastest_laps race_id=%s took %.3fs", race_id, time.monotonic() - started_at)

    async def get_race_weather_summary(self, race_id: int) -> dict[str, Any]:
        started_at = time.monotonic()
        try:
            rows = list(
                (
                    await self.db.execute(
                        select(WeatherData).where(WeatherData.race_id == race_id, WeatherData.session_type == "race")
                    )
                )
                .scalars()
                .all()
            )
            track_temps = [row.track_temp_c for row in rows if row.track_temp_c is not None]
            air_temps = [row.air_temp_c for row in rows if row.air_temp_c is not None]
            humidity = [row.humidity_pct for row in rows if row.humidity_pct is not None]
            return {
                "race_id": race_id,
                "avg_air_temp": _avg(air_temps),
                "avg_track_temp": _avg(track_temps),
                "max_track_temp": max(track_temps) if track_temps else None,
                "min_track_temp": min(track_temps) if track_temps else None,
                "avg_humidity": _avg(humidity),
                "had_rainfall": any(row.rainfall is True for row in rows),
                "samples": len(rows),
            }
        except Exception:
            logger.exception("Failed get_race_weather_summary race_id=%s", race_id)
            raise
        finally:
            logger.info("get_race_weather_summary race_id=%s took %.3fs", race_id, time.monotonic() - started_at)
