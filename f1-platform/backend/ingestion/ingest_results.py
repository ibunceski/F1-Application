from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import fastf1
import httpx
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.models.driver import Driver
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.team import Team
from ingestion.db_helpers import get_session, upsert

LOGGER = logging.getLogger("ingestion.results")
JOLPICA_BASE_URL = os.getenv("JOLPICA_BASE_URL", "https://api.jolpi.ca/ergast/f1")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest F1 qualifying and race results.")
    parser.add_argument("--seasons", nargs="+", type=int, required=True)
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument("--skip-qualifying", action="store_true")
    parser.add_argument("--skip-race", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logs_dir = PROJECT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(logs_dir / "ingestion_results.log")
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[stdout_handler, file_handler], force=True)


def configure_fastf1_cache() -> None:
    cache_path = Path(os.getenv("FASTF1_CACHE_PATH", "./cache"))
    if not cache_path.is_absolute():
        cache_path = PROJECT_DIR / cache_path
    cache_path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_path))
    LOGGER.info("FastF1 cache enabled at %s", cache_path)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(value != value)
    except TypeError:
        return False


def _none_if_missing(value: Any) -> Any:
    if _is_missing(value) or str(value) in {"NaT", "nan", "None"}:
        return None
    return value


def _to_int(value: Any) -> int | None:
    value = _none_if_missing(value)
    if value is None or value == "":
        return None
    return int(float(value))


def _to_float(value: Any) -> float | None:
    value = _none_if_missing(value)
    if value is None or value == "":
        return None
    return float(value)


def _to_str(value: Any) -> str | None:
    value = _none_if_missing(value)
    if value is None:
        return None
    return str(value)


def _to_bool(value: Any) -> bool:
    value = _none_if_missing(value)
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _timedelta_to_ms(value: Any) -> float | None:
    value = _none_if_missing(value)
    if value is None:
        return None
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds() * 1000)
    return float(value)


def _time_string_to_ms(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        minutes = 0
        seconds_part = value
        if ":" in value:
            minutes_text, seconds_part = value.split(":", 1)
            minutes = int(minutes_text)
        return (minutes * 60 + float(seconds_part)) * 1000
    except ValueError:
        LOGGER.debug("Could not parse timing value %s", value)
        return None


def _fetch_jolpica_results(year: int, round_number: int, endpoint: str) -> list[dict[str, Any]]:
    url = f"{JOLPICA_BASE_URL}/{year}/{round_number}/{endpoint}.json"
    LOGGER.info("Fetching %s fallback data from %s", endpoint, url)
    response = httpx.get(url, timeout=30.0)
    response.raise_for_status()
    races = response.json().get("MRData", {}).get("RaceTable", {}).get("Races", [])
    if not races:
        return []
    result_key = {
        "qualifying": "QualifyingResults",
        "sprint": "SprintResults",
    }.get(endpoint, "Results")
    return races[0].get(result_key, [])


def _is_fastf1_race_results_complete(results: Any) -> bool:
    if results is None or results.empty:
        return False
    meaningful_rows = 0
    for _, row in results.iterrows():
        position = _to_int(row.get("Position"))
        laps = _to_int(row.get("NumberOfLaps"))
        status = _to_str(row.get("Status"))
        points = _to_float(row.get("Points"))
        if position is not None or (laps is not None and laps > 0) or (status and status != "Unknown") or (points is not None and points > 0):
            meaningful_rows += 1
    return meaningful_rows > 0


def _is_fastf1_qualifying_complete(results: Any) -> bool:
    if results is None or results.empty:
        return False
    for _, row in results.iterrows():
        if _to_int(row.get("Position")) is not None:
            return True
    return False


def _lookup_driver(db: Session, abbreviation: str | None) -> Driver | None:
    if not abbreviation:
        return None
    return db.execute(select(Driver).where(Driver.driver_id == abbreviation)).scalar_one_or_none()


def _normalize_name(value: str | None) -> str:
    return "".join(char for char in (value or "").lower() if char.isalnum())


def _lookup_team(db: Session, team_name: str | None) -> Team | None:
    if not team_name:
        return None
    exact = db.execute(select(Team).where(Team.name == team_name)).scalar_one_or_none()
    if exact is not None:
        return exact

    normalized = _normalize_name(team_name)
    teams = db.execute(select(Team)).scalars().all()
    for team in teams:
        team_normalized = _normalize_name(team.name)
        short_normalized = _normalize_name(team.short_name)
        constructor_normalized = _normalize_name(team.constructor_id)
        if (
            normalized in team_normalized
            or team_normalized in normalized
            or normalized in short_normalized
            or short_normalized in normalized
            or normalized == constructor_normalized
        ):
            return team
    return None


def _query_races(seasons: list[int], round_number: int | None) -> list[tuple[Race, int]]:
    with get_session() as db:
        statement = (
            select(Race, Season.year)
            .join(Season, Race.season_id == Season.id)
            .where(Season.year.in_(seasons))
            .order_by(Season.year.asc(), Race.round_number.asc())
        )
        if round_number is not None:
            statement = statement.where(Race.round_number == round_number)
        return list(db.execute(statement).all())


def _is_upcoming_race(race_date: date) -> bool:
    return race_date >= datetime.now(UTC).date()


def _log_sprint_format_note(session: Any, year: int, round_number: int) -> None:
    event_format = getattr(session.event, "EventFormat", None)
    if event_format is None and hasattr(session.event, "get"):
        event_format = session.event.get("EventFormat")
    event_format = str(event_format or "")
    if "sprint_shootout" in event_format:
        LOGGER.info(
            "Round %s qualifying uses event format %s for %s; processing main qualifying session.",
            round_number,
            event_format,
            year,
        )


def _qualifying_times(row: Any) -> tuple[float | None, float | None, float | None, float | None]:
    q1_time_ms = _timedelta_to_ms(row.get("Q1"))
    q2_time_ms = _timedelta_to_ms(row.get("Q2"))
    q3_time_ms = _timedelta_to_ms(row.get("Q3"))
    valid_times = [time_ms for time_ms in (q1_time_ms, q2_time_ms, q3_time_ms) if time_ms is not None]
    best_time_ms = min(valid_times) if valid_times else None
    return q1_time_ms, q2_time_ms, q3_time_ms, best_time_ms


def _jolpica_qualifying_rows(year: int, round_number: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _fetch_jolpica_results(year, round_number, "qualifying"):
        q1_time_ms = _time_string_to_ms(item.get("Q1"))
        q2_time_ms = _time_string_to_ms(item.get("Q2"))
        q3_time_ms = _time_string_to_ms(item.get("Q3"))
        valid_times = [time_ms for time_ms in (q1_time_ms, q2_time_ms, q3_time_ms) if time_ms is not None]
        rows.append(
            {
                "abbreviation": item.get("Driver", {}).get("code"),
                "team_name": item.get("Constructor", {}).get("name"),
                "position": _to_int(item.get("position")),
                "q1_time_ms": q1_time_ms,
                "q2_time_ms": q2_time_ms,
                "q3_time_ms": q3_time_ms,
                "best_time_ms": min(valid_times) if valid_times else None,
            }
        )
    return rows


def _jolpica_race_rows(year: int, round_number: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in _fetch_jolpica_results(year, round_number, "results"):
        fastest_lap = item.get("FastestLap") or {}
        rows.append(
            {
                "abbreviation": item.get("Driver", {}).get("code"),
                "team_name": item.get("Constructor", {}).get("name"),
                "grid_position": _to_int(item.get("grid")),
                "finishing_position": _to_int(item.get("positionOrder") or item.get("position")),
                "classified_position": item.get("positionText"),
                "status": item.get("status") or "Unknown",
                "points": _to_float(item.get("points")) or 0.0,
                "laps_completed": _to_int(item.get("laps")) or 0,
                "fastest_lap": str(fastest_lap.get("rank")) == "1",
                "fastest_lap_time_ms": _time_string_to_ms((fastest_lap.get("Time") or {}).get("time")),
                "fastest_lap_rank": _to_int(fastest_lap.get("rank")),
            }
        )
    return rows


def _jolpica_sprint_points(year: int, round_number: int) -> dict[str, float]:
    points_by_driver: dict[str, float] = {}
    try:
        sprint_rows = _fetch_jolpica_results(year, round_number, "sprint")
    except Exception as exc:
        LOGGER.info("Sprint results unavailable for %s Round %s: %s", year, round_number, exc)
        return points_by_driver

    for item in sprint_rows:
        abbreviation = item.get("Driver", {}).get("code")
        if abbreviation:
            points_by_driver[abbreviation] = _to_float(item.get("points")) or 0.0
    return points_by_driver


def ingest_qualifying_results(race: Race, year: int) -> int:
    started_at = time.monotonic()
    try:
        LOGGER.info("Loading qualifying session for %s Round %s", year, race.round_number)
        rows: list[dict[str, Any]] = []
        pole_best_time_ms: float | None = None

        try:
            session = fastf1.get_session(year, race.round_number, "Q")
            session.load(laps=False, telemetry=False, weather=False, messages=False)
            _log_sprint_format_note(session, year, race.round_number)

            if _is_fastf1_qualifying_complete(session.results):
                for _, row in session.results.iterrows():
                    q1_time_ms, q2_time_ms, q3_time_ms, best_time_ms = _qualifying_times(row)
                    position = _to_int(row.get("Position"))
                    rows.append(
                        {
                            "abbreviation": _to_str(row.get("Abbreviation")),
                            "team_name": _to_str(row.get("TeamName")),
                            "position": position,
                            "q1_time_ms": q1_time_ms,
                            "q2_time_ms": q2_time_ms,
                            "q3_time_ms": q3_time_ms,
                            "best_time_ms": best_time_ms,
                        }
                    )
                    if position == 1:
                        pole_best_time_ms = best_time_ms
            else:
                LOGGER.warning(
                    "FastF1 qualifying results incomplete for %s Round %s; using Jolpica fallback.",
                    year,
                    race.round_number,
                )
                rows = _jolpica_qualifying_rows(year, race.round_number)
                pole_best_time_ms = next((row["best_time_ms"] for row in rows if row["position"] == 1), None)
        except Exception as exc:
            LOGGER.warning(
                "FastF1 qualifying unavailable for %s Round %s (%s); using Jolpica fallback.",
                year,
                race.round_number,
                exc,
            )
            rows = _jolpica_qualifying_rows(year, race.round_number)
            pole_best_time_ms = next((row["best_time_ms"] for row in rows if row["position"] == 1), None)

        saved_count = 0
        with get_session() as db:
            for row in rows:
                driver = _lookup_driver(db, row["abbreviation"])
                team = _lookup_team(db, row["team_name"])
                if driver is None or team is None:
                    LOGGER.warning(
                        "Skipping qualifying result for %s Round %s: driver=%s team=%s not found.",
                        year,
                        race.round_number,
                        row["abbreviation"],
                        row["team_name"],
                    )
                    continue

                best_time_ms = row["best_time_ms"]
                gap_to_pole_ms = (
                    best_time_ms - pole_best_time_ms
                    if best_time_ms is not None and pole_best_time_ms is not None
                    else None
                )
                upsert(
                    db,
                    QualifyingResult,
                    ["race_id", "driver_id"],
                    {
                        "race_id": race.id,
                        "driver_id": driver.id,
                        "team_id": team.id,
                        "position": row["position"],
                        "q1_time_ms": row["q1_time_ms"],
                        "q2_time_ms": row["q2_time_ms"],
                        "q3_time_ms": row["q3_time_ms"],
                        "best_time_ms": best_time_ms,
                        "gap_to_pole_ms": gap_to_pole_ms,
                    },
                )
                saved_count += 1

        elapsed = time.monotonic() - started_at
        LOGGER.info("Round %s qualifying ingested in %.2f seconds", race.round_number, elapsed)
        return saved_count
    except Exception:
        LOGGER.exception("Failed to ingest qualifying for %s Round %s", year, race.round_number)
        return 0


def ingest_race_results(race: Race, year: int) -> int:
    started_at = time.monotonic()
    try:
        LOGGER.info("Loading race session for %s Round %s", year, race.round_number)
        session = fastf1.get_session(year, race.round_number, "R")
        session.load(laps=False, telemetry=False, weather=False, messages=False)
        rows: list[dict[str, Any]] = []
        sprint_points = _jolpica_sprint_points(year, race.round_number)
        if _is_fastf1_race_results_complete(session.results):
            for _, row in session.results.iterrows():
                abbreviation = _to_str(row.get("Abbreviation"))
                rows.append(
                    {
                        "abbreviation": abbreviation,
                        "team_name": _to_str(row.get("TeamName")),
                        "grid_position": _to_int(row.get("GridPosition")),
                        "finishing_position": _to_int(row.get("Position")),
                        "classified_position": _to_str(row.get("ClassifiedPosition")),
                        "status": _to_str(row.get("Status")) or "Unknown",
                        "points": _to_float(row.get("Points")) or 0.0,
                        "sprint_points": sprint_points.get(abbreviation or "", 0.0),
                        "laps_completed": _to_int(row.get("NumberOfLaps")) or 0,
                        "fastest_lap": _to_bool(row.get("FastestLap")),
                        "fastest_lap_time_ms": _timedelta_to_ms(row.get("FastestLapTime")),
                        "fastest_lap_rank": _to_int(row.get("FastestLapRank")),
                    }
                )
        else:
            LOGGER.warning(
                "FastF1 race results incomplete for %s Round %s; using Jolpica fallback.",
                year,
                race.round_number,
            )
            rows = _jolpica_race_rows(year, race.round_number)
            for row in rows:
                row["sprint_points"] = sprint_points.get(row.get("abbreviation") or "", 0.0)

        saved_count = 0
        with get_session() as db:
            for row in rows:
                abbreviation = _to_str(row.get("abbreviation"))
                team_name = _to_str(row.get("team_name"))
                driver = _lookup_driver(db, abbreviation)
                team = _lookup_team(db, team_name)
                if driver is None or team is None:
                    LOGGER.warning(
                        "Skipping race result for %s Round %s: driver=%s team=%s not found.",
                        year,
                        race.round_number,
                        abbreviation,
                        team_name,
                    )
                    continue

                upsert(
                    db,
                    RaceResult,
                    ["race_id", "driver_id"],
                    {
                        "race_id": race.id,
                        "driver_id": driver.id,
                        "team_id": team.id,
                        "grid_position": row["grid_position"],
                        "finishing_position": row["finishing_position"],
                        "classified_position": row["classified_position"],
                        "status": row["status"],
                        "points": row["points"],
                        "sprint_points": row.get("sprint_points", 0.0),
                        "laps_completed": row["laps_completed"],
                        "fastest_lap": row["fastest_lap"],
                        "fastest_lap_time_ms": row["fastest_lap_time_ms"],
                        "fastest_lap_rank": row["fastest_lap_rank"],
                    },
                )
                saved_count += 1

        elapsed = time.monotonic() - started_at
        LOGGER.info("Round %s race results ingested in %.2f seconds", race.round_number, elapsed)
        return saved_count
    except Exception:
        LOGGER.exception("Failed to ingest race results for %s Round %s", year, race.round_number)
        return 0


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    configure_fastf1_cache()

    summary: dict[int, dict[str, int]] = defaultdict(lambda: {"qualifying": 0, "race": 0})
    for year in args.seasons:
        summary[year]
    races = _query_races(args.seasons, args.round_number)

    if not races:
        LOGGER.warning("No races found for seasons=%s round=%s", args.seasons, args.round_number)

    for race, year in races:
        if _is_upcoming_race(race.race_date):
            LOGGER.warning(
                "Skipping upcoming race without final results: %s Round %s (%s)",
                year,
                race.round_number,
                race.race_date,
            )
            continue

        if not args.skip_qualifying:
            summary[year]["qualifying"] += ingest_qualifying_results(race, year)

        if not args.skip_race:
            summary[year]["race"] += ingest_race_results(race, year)

    for year in sorted(summary):
        message = (
            f"Season {year}: "
            f"{summary[year]['qualifying']} qualifying results, "
            f"{summary[year]['race']} race results saved."
        )
        LOGGER.info(message)
        print(message)


if __name__ == "__main__":
    main()
