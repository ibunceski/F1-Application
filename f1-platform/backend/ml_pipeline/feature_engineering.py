from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import mean, median
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.orm import Session

PROJECT_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = PROJECT_DIR.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(ROOT_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env", override=False)

from app.models.lap_time import LapTime
from app.models.ml_feature import MLFeature
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.weather import WeatherData
from ingestion.db_helpers import get_session, upsert

LOGGER = logging.getLogger("ml.feature_engineering")
DNF_CLASSIFICATIONS = {"DNF", "DNQ", "DNS", "DSQ"}
NUMERIC_FEATURES = [
    "grid_position",
    "qualifying_position",
    "gap_to_pole_ms",
    "avg_race_pace_ms",
    "driver_recent_form",
    "team_recent_form",
    "circuit_history_avg_finish",
    "circuit_history_dnf_rate",
    "dnf_rate_recent",
    "avg_track_temp_c",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build ML feature rows from ingested F1 data.")
    parser.add_argument("--seasons", nargs="+", type=int, required=True)
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logs_dir = PROJECT_DIR / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_level = logging.DEBUG if verbose else logging.INFO
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(logs_dir / "feature_engineering.log")
    file_handler.setFormatter(formatter)

    logging.basicConfig(level=log_level, handlers=[stdout_handler, file_handler], force=True)


def query_races(db: Session, seasons: list[int], round_number: int | None) -> list[tuple[Race, int]]:
    statement = (
        select(Race, Season.year)
        .join(Season, Race.season_id == Season.id)
        .where(Season.year.in_(seasons))
        .order_by(Race.race_date.asc(), Season.year.asc(), Race.round_number.asc())
    )
    if round_number is not None:
        statement = statement.where(Race.round_number == round_number)
    return list(db.execute(statement).all())


def is_dnf(result: RaceResult) -> bool:
    classification = (result.classified_position or "").upper()
    return result.finishing_position is None or classification in DNF_CLASSIFICATIONS


def average(values: list[float | int]) -> float | None:
    return float(mean(values)) if values else None


def prior_driver_results(
    db: Session,
    driver_id: int,
    before_date: date,
    limit: int,
) -> list[RaceResult]:
    statement = (
        select(RaceResult)
        .join(Race, RaceResult.race_id == Race.id)
        .where(RaceResult.driver_id == driver_id, Race.race_date < before_date)
        .order_by(Race.race_date.desc(), Race.round_number.desc())
        .limit(limit)
    )
    return list(db.execute(statement).scalars().all())


def avg_race_pace_ms(db: Session, driver_id: int, before_date: date) -> float | None:
    race_id_statement = (
        select(RaceResult.race_id)
        .join(Race, RaceResult.race_id == Race.id)
        .where(RaceResult.driver_id == driver_id, Race.race_date < before_date)
        .order_by(Race.race_date.desc(), Race.round_number.desc())
        .limit(3)
    )
    prior_race_ids = list(db.execute(race_id_statement).scalars().all())
    race_medians: list[float] = []

    for race_id in prior_race_ids:
        lap_statement = (
            select(LapTime.lap_time_ms)
            .where(
                LapTime.race_id == race_id,
                LapTime.driver_id == driver_id,
                LapTime.lap_time_ms.is_not(None),
                LapTime.deleted.is_(False),
                LapTime.is_pit_out_lap.is_(False),
                LapTime.is_pit_in_lap.is_(False),
            )
        )
        lap_times = list(db.execute(lap_statement).scalars().all())
        if lap_times:
            race_medians.append(float(median(lap_times)))

    return average(race_medians)


def driver_recent_form(db: Session, driver_id: int, before_date: date) -> float | None:
    results = prior_driver_results(db, driver_id, before_date, 5)
    finishing_positions = [
        result.finishing_position for result in results if result.finishing_position is not None
    ]
    if finishing_positions:
        return average(finishing_positions)
    return 20.0 if results else None


def dnf_rate_recent(db: Session, driver_id: int, before_date: date) -> float | None:
    results = prior_driver_results(db, driver_id, before_date, 10)
    if not results:
        return None
    return sum(1 for result in results if is_dnf(result)) / len(results)


def recent_team_race_ids(db: Session, team_id: int, before_date: date) -> list[int]:
    statement = (
        select(RaceResult.race_id, Race.race_date, Race.round_number)
        .join(Race, RaceResult.race_id == Race.id)
        .where(RaceResult.team_id == team_id, Race.race_date < before_date)
        .group_by(RaceResult.race_id, Race.race_date, Race.round_number)
        .order_by(Race.race_date.desc(), Race.round_number.desc())
        .limit(3)
    )
    return [row.race_id for row in db.execute(statement).all()]


def team_recent_form(db: Session, team_id: int, before_date: date) -> float | None:
    race_ids = recent_team_race_ids(db, team_id, before_date)
    if not race_ids:
        return None

    statement = select(RaceResult.finishing_position).where(
        RaceResult.team_id == team_id,
        RaceResult.race_id.in_(race_ids),
        RaceResult.finishing_position.is_not(None),
    )
    finishing_positions = list(db.execute(statement).scalars().all())
    return average(finishing_positions)


def circuit_history(db: Session, driver_id: int, current_race: Race) -> tuple[float, float | None]:
    statement = (
        select(RaceResult)
        .join(Race, RaceResult.race_id == Race.id)
        .where(
            RaceResult.driver_id == driver_id,
            Race.circuit_name == current_race.circuit_name,
            Race.race_date < current_race.race_date,
        )
    )
    results = list(db.execute(statement).scalars().all())
    if not results:
        return 10.5, None

    finishing_positions = [
        result.finishing_position for result in results if result.finishing_position is not None
    ]
    avg_finish = average(finishing_positions) if finishing_positions else 10.5
    dnf_rate = sum(1 for result in results if is_dnf(result)) / len(results)
    return float(avg_finish), dnf_rate


def weather_features(db: Session, race_id: int) -> tuple[bool, float | None]:
    weather_rows = list(
        db.execute(
            select(WeatherData).where(
                WeatherData.race_id == race_id,
                WeatherData.session_type == "race",
            )
        )
        .scalars()
        .all()
    )
    weather_is_wet = any(row.rainfall is True for row in weather_rows)
    track_temps = [row.track_temp_c for row in weather_rows if row.track_temp_c is not None]
    return weather_is_wet, average(track_temps)


def target_metrics(race_result: RaceResult) -> dict[str, Any]:
    finishing_position = race_result.finishing_position
    return {
        "actual_finishing_position": finishing_position,
        "finished_top10": finishing_position is not None and finishing_position <= 10,
        "finished_podium": finishing_position is not None and finishing_position <= 3,
        "position_gain_loss": (
            race_result.grid_position - finishing_position
            if race_result.grid_position is not None and finishing_position is not None
            else None
        ),
        "dnf": is_dnf(race_result),
    }


def season_medians(feature_history: dict[str, list[float]]) -> dict[str, float]:
    return {
        feature_name: float(median(values))
        for feature_name, values in feature_history.items()
        if values
    }


def fill_missing_numeric_features(
    feature_row: dict[str, Any],
    medians: dict[str, float],
) -> dict[str, Any]:
    filled = feature_row.copy()
    for feature_name in NUMERIC_FEATURES:
        if filled.get(feature_name) is None and feature_name in medians:
            filled[feature_name] = medians[feature_name]
    return filled


def update_feature_history(feature_history: dict[str, list[float]], feature_row: dict[str, Any]) -> None:
    for feature_name in NUMERIC_FEATURES:
        value = feature_row.get(feature_name)
        if value is not None:
            feature_history[feature_name].append(float(value))


def current_race_result(db: Session, race_id: int, driver_id: int) -> RaceResult | None:
    return db.execute(
        select(RaceResult).where(
            RaceResult.race_id == race_id,
            RaceResult.driver_id == driver_id,
        )
    ).scalar_one_or_none()


def qualifying_results_for_race(db: Session, race_id: int) -> list[QualifyingResult]:
    return list(
        db.execute(
            select(QualifyingResult)
            .where(QualifyingResult.race_id == race_id)
            .order_by(QualifyingResult.position.asc().nulls_last())
        )
        .scalars()
        .all()
    )


def build_feature_row(
    db: Session,
    race: Race,
    qualifying_result: QualifyingResult,
    race_result: RaceResult,
) -> dict[str, Any]:
    circuit_avg_finish, circuit_dnf_rate = circuit_history(db, qualifying_result.driver_id, race)
    weather_is_wet, avg_track_temp_c = weather_features(db, race.id)
    gap_to_pole_ms = qualifying_result.gap_to_pole_ms
    if qualifying_result.position == 1:
        gap_to_pole_ms = 0.0

    return {
        "race_id": race.id,
        "driver_id": qualifying_result.driver_id,
        "grid_position": float(race_result.grid_position) if race_result.grid_position is not None else None,
        "qualifying_position": (
            float(qualifying_result.position) if qualifying_result.position is not None else None
        ),
        "gap_to_pole_ms": gap_to_pole_ms,
        "avg_race_pace_ms": avg_race_pace_ms(db, qualifying_result.driver_id, race.race_date),
        "driver_recent_form": driver_recent_form(db, qualifying_result.driver_id, race.race_date),
        "team_recent_form": team_recent_form(db, race_result.team_id, race.race_date),
        "circuit_history_avg_finish": circuit_avg_finish,
        "circuit_history_dnf_rate": circuit_dnf_rate,
        "dnf_rate_recent": dnf_rate_recent(db, qualifying_result.driver_id, race.race_date),
        "weather_is_wet": weather_is_wet,
        "avg_track_temp_c": avg_track_temp_c,
    }


def should_skip_feature_row(feature_row: dict[str, Any], race: Race, driver_id: int) -> bool:
    if feature_row["grid_position"] is None:
        LOGGER.warning("Skipping Race %s driver %s: missing grid_position.", race.id, driver_id)
        return True
    if feature_row["qualifying_position"] is None:
        LOGGER.warning("Skipping Race %s driver %s: missing qualifying_position.", race.id, driver_id)
        return True
    return False


def process_race(
    db: Session,
    race: Race,
    year: int,
    season_feature_history: dict[int, dict[str, list[float]]],
) -> dict[str, int]:
    counts = {
        "features": 0,
        "missing_pace": 0,
        "podiums": 0,
        "top10s": 0,
        "dnfs": 0,
    }

    LOGGER.info("Processing %s Round %s: %s", year, race.round_number, race.race_name)
    for qualifying_result in qualifying_results_for_race(db, race.id):
        race_result = current_race_result(db, race.id, qualifying_result.driver_id)
        if race_result is None:
            LOGGER.warning(
                "Skipping Race %s driver %s: missing RaceResult.",
                race.id,
                qualifying_result.driver_id,
            )
            continue

        feature_row = build_feature_row(db, race, qualifying_result, race_result)
        if should_skip_feature_row(feature_row, race, qualifying_result.driver_id):
            continue

        if feature_row["avg_race_pace_ms"] is None:
            counts["missing_pace"] += 1
            LOGGER.warning(
                "Race %s driver %s has no prior avg_race_pace_ms history.",
                race.id,
                qualifying_result.driver_id,
            )

        medians = season_medians(season_feature_history[year])
        feature_row = fill_missing_numeric_features(feature_row, medians)
        upsert(db, MLFeature, ["race_id", "driver_id"], feature_row)
        update_feature_history(season_feature_history[year], feature_row)

        targets = target_metrics(race_result)
        counts["features"] += 1
        counts["podiums"] += int(targets["finished_podium"])
        counts["top10s"] += int(targets["finished_top10"])
        counts["dnfs"] += int(targets["dnf"])

    return counts


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)

    season_counts: dict[int, dict[str, int]] = defaultdict(
        lambda: {"features": 0, "missing_pace": 0, "podiums": 0, "top10s": 0, "dnfs": 0}
    )
    season_feature_history: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    with get_session() as db:
        races = query_races(db, args.seasons, args.round_number)

    if not races:
        LOGGER.warning("No races found for seasons=%s round=%s", args.seasons, args.round_number)

    for race, year in races:
        try:
            with get_session() as db:
                race_counts = process_race(db, race, year, season_feature_history)
        except Exception:
            LOGGER.exception("Failed to process %s Round %s", year, race.round_number)
            continue

        for key, value in race_counts.items():
            season_counts[year][key] += value

    for year in sorted(set(args.seasons) | set(season_counts.keys())):
        counts = season_counts[year]
        features = counts["features"]
        missing_pace_pct = (counts["missing_pace"] / features * 100) if features else 0.0
        message = (
            f"Season {year}: {features} feature rows, "
            f"{missing_pace_pct:.1f}% missing avg_race_pace_ms before median fill, "
            f"{counts['podiums']} podium labels, "
            f"{counts['top10s']} top10 labels, "
            f"{counts['dnfs']} DNFs."
        )
        LOGGER.info(message)
        print(message)


if __name__ == "__main__":
    main()
