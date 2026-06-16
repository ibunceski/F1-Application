from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import fastf1
from dotenv import load_dotenv
from sqlalchemy import func, select

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.season import Season
from ingestion.db_helpers import get_session
from ingestion.ingest_results import _jolpica_qualifying_rows, ingest_qualifying_results

LOGGER = logging.getLogger("ingestion.weekend")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh upcoming race weekend data without ingesting race results.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--next-race", action="store_true", help="Refresh qualifying for the next race by race date.")
    target.add_argument("--season", type=int, help="Season year for an explicit race target.")
    parser.add_argument("--round", type=int, dest="round_number", help="Round number, required with --season.")
    parser.add_argument("--qualifying-only", action="store_true", help="Only refresh qualifying data. Race results are never ingested by this script.")
    parser.add_argument(
        "--generate-features",
        action="store_true",
        help="Generate post-qualifying ML features after qualifying rows are ingested.",
    )
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logs_dir = PROJECT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(logs_dir / "ingestion_weekend.log")
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[stdout_handler, file_handler], force=True)


def configure_fastf1_cache() -> None:
    cache_path = Path(os.getenv("FASTF1_CACHE_PATH", "./cache"))
    if not cache_path.is_absolute():
        cache_path = PROJECT_DIR / cache_path
    cache_path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_path))
    LOGGER.info("FastF1 cache enabled at %s", cache_path)


def validate_args(args: argparse.Namespace) -> None:
    if args.season is not None and args.round_number is None:
        raise SystemExit("--round is required when --season is provided.")
    if args.next_race and args.round_number is not None:
        raise SystemExit("--round can only be used with --season.")


def _today() -> date:
    return datetime.now(UTC).date()


def find_next_race(today: date | None = None) -> tuple[Race, int] | None:
    today = today or _today()
    with get_session() as db:
        statement = (
            select(Race, Season.year)
            .join(Season, Race.season_id == Season.id)
            .where(Race.race_date >= today)
            .order_by(Race.race_date.asc(), Season.year.asc(), Race.round_number.asc())
            .limit(1)
        )
        return db.execute(statement).one_or_none()


def find_race_by_round(season: int, round_number: int) -> tuple[Race, int] | None:
    with get_session() as db:
        statement = (
            select(Race, Season.year)
            .join(Season, Race.season_id == Season.id)
            .where(Season.year == season, Race.round_number == round_number)
            .limit(1)
        )
        return db.execute(statement).one_or_none()


def count_qualifying_rows(race_id: int) -> int:
    with get_session() as db:
        return int(
            db.execute(
                select(func.count(QualifyingResult.id)).where(QualifyingResult.race_id == race_id)
            ).scalar_one()
        )


def _is_qualifying_exception(error: Exception) -> bool:
    text = str(error).lower()
    unavailable_markers = (
        "session not available",
        "no data",
        "not found",
        "failed to load",
        "qualifying",
    )
    return any(marker in text for marker in unavailable_markers)


def _fallback_qualifying_available(year: int, round_number: int) -> bool:
    try:
        return bool(_jolpica_qualifying_rows(year, round_number))
    except Exception as exc:
        LOGGER.info("Qualifying fallback data is not available for %s Round %s: %s", year, round_number, exc)
        return False


def is_qualifying_available(year: int, round_number: int) -> bool:
    try:
        session = fastf1.get_session(year, round_number, "Q")
        session.load(laps=False, telemetry=False, weather=False, messages=False)
        results: Any = getattr(session, "results", None)
        if results is None or results.empty:
            return False
        return any(row.get("Position") == row.get("Position") for _, row in results.iterrows())
    except Exception as exc:
        if _is_qualifying_exception(exc):
            LOGGER.info("Qualifying is not available yet for %s Round %s: %s", year, round_number, exc)
            return _fallback_qualifying_available(year, round_number)
        LOGGER.warning("Could not confirm qualifying availability for %s Round %s: %s", year, round_number, exc)
        return _fallback_qualifying_available(year, round_number)


def generate_post_qualifying_features(race_id: int) -> bool:
    command = [
        sys.executable,
        str(PROJECT_DIR / "ml_pipeline" / "feature_engineering.py"),
        "--race-id",
        str(race_id),
        "--context",
        "post_qualifying",
        "--force",
    ]
    LOGGER.info("Generating post-qualifying features: %s", " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_DIR, check=False)
    if result.returncode != 0:
        LOGGER.error("Post-qualifying feature generation failed with exit code %s", result.returncode)
        return False
    return True


def refresh_qualifying(race: Race, year: int, generate_features: bool) -> int:
    LOGGER.info(
        "Refreshing weekend qualifying for %s Round %s: %s (%s)",
        year,
        race.round_number,
        race.race_name,
        race.race_date,
    )

    if not is_qualifying_available(year, race.round_number):
        message = f"Qualifying results are not available yet for {year} Round {race.round_number}. Nothing to ingest."
        LOGGER.info(message)
        print(message)
        return 0

    before_count = count_qualifying_rows(race.id)
    saved_count = ingest_qualifying_results(race, year)
    after_count = count_qualifying_rows(race.id)

    message = (
        f"Qualifying refresh complete for {year} Round {race.round_number}: "
        f"{saved_count} rows processed, {after_count} rows stored."
    )
    if before_count and after_count:
        message += " Existing qualifying rows were updated idempotently."
    LOGGER.info(message)
    print(message)

    if saved_count > 0 and generate_features:
        if generate_post_qualifying_features(race.id):
            LOGGER.info("Post-qualifying features generated for race_id=%s", race.id)
        else:
            LOGGER.error("Post-qualifying feature generation failed for race_id=%s", race.id)

    return saved_count


def main() -> None:
    args = parse_args()
    validate_args(args)
    configure_logging(args.verbose)
    configure_fastf1_cache()

    if not args.qualifying_only:
        LOGGER.info("Race results are intentionally not ingested by ingest_weekend.py.")

    target = find_next_race() if args.next_race else find_race_by_round(args.season, args.round_number)
    if target is None:
        selector = "next race" if args.next_race else f"{args.season} Round {args.round_number}"
        message = f"No race found for {selector}."
        LOGGER.warning(message)
        print(message)
        return

    race, year = target
    refresh_qualifying(race, year, args.generate_features)


if __name__ == "__main__":
    main()
