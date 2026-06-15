from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import fastf1
from dotenv import load_dotenv
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.models.driver import Driver
from app.models.lap_time import LapTime
from app.models.race import Race
from app.models.season import Season
from app.models.weather import WeatherData
from ingestion.db_helpers import get_session

LOGGER = logging.getLogger("ingestion.laps")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest F1 lap times and weather data.")
    parser.add_argument("--seasons", nargs="+", type=int, required=True)
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--weather-only", action="store_true")
    parser.add_argument("--laps-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logs_dir = PROJECT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(logs_dir / "ingestion_laps.log")
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[stdout_handler, file_handler], force=True)


def cache_path() -> Path:
    path = Path(os.getenv("FASTF1_CACHE_PATH", "./cache"))
    if not path.is_absolute():
        path = PROJECT_DIR / path
    return path


def configure_fastf1_cache() -> Path:
    path = cache_path()
    path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(path))
    LOGGER.info("FastF1 cache enabled at %s", path)
    return path


def checkpoint_path() -> Path:
    return cache_path() / "ingestion_checkpoints.json"


def load_checkpoints() -> dict[str, str]:
    path = checkpoint_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as checkpoint_file:
        return json.load(checkpoint_file)


def write_checkpoint(year: int, round_number: int, value: str) -> None:
    path = checkpoint_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    checkpoints = load_checkpoints()
    checkpoints[f"{year}_{round_number}"] = value

    temp_path = path.with_suffix(".tmp")
    with temp_path.open("w", encoding="utf-8") as checkpoint_file:
        json.dump(checkpoints, checkpoint_file, indent=2, sort_keys=True)
    temp_path.replace(path)


def checkpoint_value(include_laps: bool, include_weather: bool) -> str:
    if include_laps and include_weather:
        return "laps_weather"
    if include_laps:
        return "laps"
    return "weather"


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


def _timedelta_to_seconds(value: Any) -> float | None:
    value = _none_if_missing(value)
    if value is None:
        return None
    if hasattr(value, "total_seconds"):
        return float(value.total_seconds())
    return float(value)


def _is_present(value: Any) -> bool:
    return _none_if_missing(value) is not None


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


def _is_future_race(race_date: date) -> bool:
    return race_date > datetime.now(UTC).date()


def _driver_map(db: Session) -> dict[int, int]:
    drivers = db.execute(select(Driver.id, Driver.driver_number)).all()
    return {int(driver_number): driver_id for driver_id, driver_number in drivers}


def _lap_mapping(row: Any, race_id: int, driver_id: int) -> dict[str, Any]:
    compound = _none_if_missing(row.get("Compound"))
    compound_value = str(compound)[:10] if compound is not None else None
    return {
        "race_id": race_id,
        "driver_id": driver_id,
        "lap_number": _to_int(row.get("LapNumber")),
        "lap_time_ms": _timedelta_to_ms(row.get("LapTime")),
        "sector1_ms": _timedelta_to_ms(row.get("Sector1Time")),
        "sector2_ms": _timedelta_to_ms(row.get("Sector2Time")),
        "sector3_ms": _timedelta_to_ms(row.get("Sector3Time")),
        "compound": compound_value,
        "tyre_age_laps": _to_int(row.get("TyreLife")),
        "stint_number": _to_int(row.get("Stint")),
        "is_pit_out_lap": _is_present(row.get("PitOutTime")),
        "is_pit_in_lap": _is_present(row.get("PitInTime")),
        "is_personal_best": _to_bool(row.get("IsPersonalBest")),
        "deleted": _to_bool(row.get("Deleted")),
    }


def build_lap_mappings(session: Any, race: Race) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    seen_keys: set[tuple[int, int, int]] = set()

    with get_session() as db:
        drivers_by_number = _driver_map(db)

    for _, row in session.laps.iterrows():
        driver_number = _to_int(row.get("DriverNumber"))
        driver_id = drivers_by_number.get(driver_number) if driver_number is not None else None
        if driver_id is None:
            LOGGER.warning(
                "Skipping lap for Round %s: driver number %s not found.",
                race.round_number,
                row.get("DriverNumber"),
            )
            continue

        mapping = _lap_mapping(row, race.id, driver_id)
        lap_number = mapping["lap_number"]
        if lap_number is None:
            LOGGER.warning("Skipping lap for Round %s: missing LapNumber.", race.round_number)
            continue

        key = (race.id, driver_id, lap_number)
        if key in seen_keys:
            LOGGER.warning(
                "Skipping duplicate lap for Round %s: driver_id=%s lap=%s.",
                race.round_number,
                driver_id,
                lap_number,
            )
            continue
        seen_keys.add(key)
        mappings.append(mapping)

    return mappings


def insert_lap_mappings(race: Race, mappings: list[dict[str, Any]], batch_size: int) -> int:
    with get_session() as db:
        db.execute(delete(LapTime).where(LapTime.race_id == race.id))

        inserted = 0
        next_progress_log = 1000
        total = len(mappings)
        for index in range(0, total, batch_size):
            batch = mappings[index : index + batch_size]
            db.bulk_insert_mappings(LapTime, batch)
            inserted += len(batch)
            if inserted >= next_progress_log or inserted == total:
                LOGGER.info("Inserted %s/%s laps for Round %s...", inserted, total, race.round_number)
                next_progress_log += 1000

    return len(mappings)


def _weather_mapping(row: Any, race_id: int, session_type: str) -> dict[str, Any] | None:
    timestamp_offset_s = _timedelta_to_seconds(row.get("Time"))
    if timestamp_offset_s is None:
        return None
    return {
        "race_id": race_id,
        "session_type": session_type,
        "timestamp_offset_s": timestamp_offset_s,
        "air_temp_c": _to_float(row.get("AirTemp")),
        "track_temp_c": _to_float(row.get("TrackTemp")),
        "humidity_pct": _to_float(row.get("Humidity")),
        "rainfall": None if _none_if_missing(row.get("Rainfall")) is None else _to_bool(row.get("Rainfall")),
        "wind_speed_ms": _to_float(row.get("WindSpeed")),
        "wind_direction_deg": _to_int(row.get("WindDirection")),
    }


def build_weather_mappings(session: Any, race: Race, session_type: str) -> list[dict[str, Any]]:
    weather_data = getattr(session, "weather_data", None)
    if weather_data is None:
        LOGGER.warning("No %s weather data available for Round %s.", session_type, race.round_number)
        return []

    mappings: list[dict[str, Any]] = []
    for _, row in weather_data.iterrows():
        mapping = _weather_mapping(row, race.id, session_type)
        if mapping is not None:
            mappings.append(mapping)
    return mappings


def insert_weather_mappings(race: Race, session_type: str, mappings: list[dict[str, Any]]) -> int:
    with get_session() as db:
        db.execute(
            delete(WeatherData).where(
                WeatherData.race_id == race.id,
                WeatherData.session_type == session_type,
            )
        )
        if mappings:
            db.bulk_insert_mappings(WeatherData, mappings)
    return len(mappings)


def load_race_session(year: int, round_number: int, include_laps: bool, include_weather: bool) -> Any:
    session = fastf1.get_session(year, round_number, "R")
    session.load(
        laps=include_laps,
        telemetry=False,
        weather=include_weather,
        messages=False,
    )
    return session


def load_qualifying_weather_session(year: int, round_number: int) -> Any:
    session = fastf1.get_session(year, round_number, "Q")
    session.load(laps=False, telemetry=False, weather=True, messages=False)
    return session


def ingest_laps_for_race(race: Race, year: int, session: Any, batch_size: int) -> int:
    started_at = time.monotonic()
    mappings = build_lap_mappings(session, race)
    inserted_count = insert_lap_mappings(race, mappings, batch_size)
    elapsed = time.monotonic() - started_at
    LOGGER.info(
        "Round %s lap ingestion saved %s rows in %.2f seconds.",
        race.round_number,
        inserted_count,
        elapsed,
    )
    return inserted_count


def ingest_weather_for_race(race: Race, year: int, race_session: Any) -> int:
    race_weather = build_weather_mappings(race_session, race, "race")
    race_count = insert_weather_mappings(race, "race", race_weather)

    LOGGER.info("Loading qualifying weather for %s Round %s", year, race.round_number)
    qualifying_session = load_qualifying_weather_session(year, race.round_number)
    qualifying_weather = build_weather_mappings(qualifying_session, race, "qualifying")
    qualifying_count = insert_weather_mappings(race, "qualifying", qualifying_weather)

    LOGGER.info(
        "Round %s weather ingestion saved %s race rows and %s qualifying rows.",
        race.round_number,
        race_count,
        qualifying_count,
    )
    return race_count + qualifying_count


def validate_args(args: argparse.Namespace) -> None:
    if args.weather_only and args.laps_only:
        raise ValueError("--weather-only and --laps-only cannot be used together.")
    if args.batch_size < 1:
        raise ValueError("--batch-size must be greater than zero.")


def main() -> None:
    args = parse_args()
    validate_args(args)
    configure_logging(args.verbose)
    configure_fastf1_cache()

    include_laps = not args.weather_only
    include_weather = not args.laps_only
    checkpoint_label = checkpoint_value(include_laps, include_weather)
    checkpoints = load_checkpoints()

    races = _query_races(args.seasons, args.round_number)
    if not races:
        LOGGER.warning("No races found for seasons=%s round=%s", args.seasons, args.round_number)

    total_laps = 0
    total_weather = 0

    for race, year in races:
        checkpoint_key = f"{year}_{race.round_number}"
        if checkpoint_key in checkpoints and not args.force:
            LOGGER.info(
                "Skipping %s Round %s because checkpoint exists: %s",
                year,
                race.round_number,
                checkpoints[checkpoint_key],
            )
            continue

        if _is_future_race(race.race_date):
            LOGGER.warning("Skipping future race: %s Round %s (%s)", year, race.round_number, race.race_date)
            continue

        try:
            LOGGER.info("Loading race session for %s Round %s", year, race.round_number)
            race_session = load_race_session(year, race.round_number, include_laps, include_weather)

            if include_laps:
                total_laps += ingest_laps_for_race(race, year, race_session, args.batch_size)

            if include_weather:
                total_weather += ingest_weather_for_race(race, year, race_session)

            write_checkpoint(year, race.round_number, checkpoint_label)
            LOGGER.info("Wrote checkpoint for %s Round %s: %s", year, race.round_number, checkpoint_label)
        except Exception:
            LOGGER.exception("Failed to ingest laps/weather for %s Round %s", year, race.round_number)

    summary = f"Lap/weather ingestion complete: {total_laps} laps, {total_weather} weather rows saved."
    LOGGER.info(summary)
    print(summary)


if __name__ == "__main__":
    main()
