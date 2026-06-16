from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import fastf1
from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.models.driver import Driver
from app.models.race import Race
from app.models.season import Season
from app.models.team import Team
from ingestion.db_helpers import get_session, upsert

LOGGER = logging.getLogger("ingestion.core")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest core F1 seasons, races, teams, and drivers.")
    parser.add_argument("--seasons", nargs="+", type=int, required=True)
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logs_dir = PROJECT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(logs_dir / "ingestion_core.log")
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[stdout_handler, file_handler], force=True)


def configure_fastf1_cache() -> None:
    cache_path = Path(os.getenv("FASTF1_CACHE_PATH", "./cache"))
    if not cache_path.is_absolute():
        cache_path = PROJECT_DIR / cache_path
    cache_path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_path))
    LOGGER.info("FastF1 cache enabled at %s", cache_path)


def _normalize_event_date(value: Any) -> date:
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise ValueError(f"Unsupported EventDate value: {value!r}")


def _value_or_none(value: Any) -> Any:
    return None if value is None or str(value) == "nan" else value


def _string_or_default(value: Any, default: str) -> str:
    value = _value_or_none(value)
    return str(value) if value else default


def _team_identifier(team_name: str, team_id: Any) -> str:
    team_id = _value_or_none(team_id)
    if team_id:
        return str(team_id)
    return team_name.lower().replace(" ", "_")


def _driver_number(value: Any) -> int:
    value = _value_or_none(value)
    if value is None:
        raise ValueError("DriverNumber is required.")
    return int(value)


def _has_race_completed(race_date: date, today: date | None = None) -> bool:
    return race_date < (today or datetime.now(UTC).date())


def ingest_schedule(year: int, processed_seasons: set[int], processed_races: set[tuple[int, int]]) -> list[dict[str, Any]]:
    LOGGER.info("Fetching schedule for %s", year)
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    if "EventFormat" in schedule.columns:
        schedule = schedule[schedule["EventFormat"] != "testing"]

    total_races = len(schedule.index)
    occurred_events: list[dict[str, Any]] = []

    with get_session() as db:
        season = upsert(
            db,
            Season,
            "year",
            {"year": year, "total_races": total_races},
        )
        processed_seasons.add(year)

        for _, event in schedule.iterrows():
            round_number = int(event["RoundNumber"])
            event_name = _string_or_default(event.get("EventName"), f"Round {round_number}")
            LOGGER.info("Processing Round %s: %s", round_number, event_name)

            try:
                race_date = _normalize_event_date(event["EventDate"])
                race_data = {
                    "season_id": season.id,
                    "round_number": round_number,
                    "circuit_name": _string_or_default(event.get("OfficialEventName"), event_name),
                    "circuit_location": _string_or_default(event.get("Location"), "Unknown"),
                    "circuit_country": _string_or_default(event.get("Country"), "Unknown"),
                    "race_name": event_name,
                    "race_date": race_date,
                    "session_key": None,
                }
                upsert(db, Race, ["season_id", "round_number"], race_data)
                processed_races.add((year, round_number))

                if _has_race_completed(race_date):
                    occurred_events.append(
                        {
                            "year": year,
                            "round_number": round_number,
                            "event_name": event_name,
                        }
                    )
                else:
                    LOGGER.info("Skipping upcoming race session load: %s Round %s", year, round_number)
            except Exception:
                LOGGER.exception("Failed to ingest schedule data for %s Round %s", year, round_number)

    return occurred_events


def ingest_session_participants(
    events: list[dict[str, Any]],
    processed_drivers: set[str],
    processed_teams: set[str],
    failed_races: list[str],
) -> None:
    for event in events:
        year = event["year"]
        round_number = event["round_number"]
        event_name = event["event_name"]

        try:
            LOGGER.info("Loading race session for %s Round %s: %s", year, round_number, event_name)
            race_session = fastf1.get_session(year, round_number, "R")
            race_session.load(laps=False, telemetry=False, weather=False, messages=False)
            results = race_session.results

            with get_session() as db:
                for _, driver in results.iterrows():
                    team_name = _string_or_default(driver.get("TeamName"), "Unknown")
                    constructor_id = _team_identifier(team_name, driver.get("TeamId"))
                    team = upsert(
                        db,
                        Team,
                        "constructor_id",
                        {
                            "name": team_name,
                            "short_name": team_name,
                            "nationality": None,
                            "constructor_id": constructor_id,
                        },
                    )
                    processed_teams.add(constructor_id)

                    abbreviation = _string_or_default(driver.get("Abbreviation"), "")
                    if not abbreviation:
                        LOGGER.warning("Skipping driver without abbreviation in %s Round %s", year, round_number)
                        continue

                    driver_number = _driver_number(driver.get("DriverNumber"))
                    driver_id = abbreviation
                    upsert(
                        db,
                        Driver,
                        "driver_id",
                        {
                            "driver_number": driver_number,
                            "full_name": _string_or_default(driver.get("FullName"), abbreviation),
                            "abbreviation": abbreviation[:3],
                            "nationality": _value_or_none(driver.get("CountryCode")),
                            "team_id": team.id,
                            "driver_id": driver_id,
                        },
                    )
                    processed_drivers.add(driver_id)
        except Exception:
            race_label = f"{year} Round {round_number}: {event_name}"
            failed_races.append(race_label)
            LOGGER.exception("Failed to ingest participants for %s", race_label)


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    configure_fastf1_cache()

    processed_seasons: set[int] = set()
    processed_races: set[tuple[int, int]] = set()
    processed_drivers: set[str] = set()
    processed_teams: set[str] = set()
    failed_races: list[str] = []

    for year in args.seasons:
        try:
            occurred_events = ingest_schedule(year, processed_seasons, processed_races)
            ingest_session_participants(occurred_events, processed_drivers, processed_teams, failed_races)
        except Exception:
            LOGGER.exception("Failed to ingest season %s", year)

    if failed_races:
        LOGGER.warning("Failed races: %s", "; ".join(failed_races))
    else:
        LOGGER.info("Failed races: none")

    summary = (
        "Ingestion complete: "
        f"{len(processed_seasons)} seasons, "
        f"{len(processed_races)} races, "
        f"{len(processed_drivers)} drivers, "
        f"{len(processed_teams)} teams processed."
    )
    LOGGER.info(summary)
    print(summary)


if __name__ == "__main__":
    main()
