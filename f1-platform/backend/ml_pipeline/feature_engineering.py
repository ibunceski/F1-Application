from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict
from datetime import UTC, date, datetime
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
from app.models.ml_feature import MLFeature, POST_QUALIFYING, PRE_QUALIFYING
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
    parser.add_argument("--seasons", nargs="+", type=int)
    parser.add_argument("--race-id", type=int)
    parser.add_argument("--next-race", action="store_true")
    parser.add_argument("--round", type=int, dest="round_number")
    parser.add_argument(
        "--context",
        "--feature-context",
        dest="context",
        choices=[PRE_QUALIFYING, POST_QUALIFYING, "all"],
        default="all",
        help="Prediction context to generate. Defaults to both contexts.",
    )
    parser.add_argument("--fallback-pre-qualifying", action="store_true")
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


def query_race_by_id(db: Session, race_id: int) -> list[tuple[Race, int]]:
    row = db.execute(
        select(Race, Season.year)
        .join(Season, Race.season_id == Season.id)
        .where(Race.id == race_id)
    ).one_or_none()
    return [row] if row is not None else []


def query_next_race(db: Session, from_date: date) -> list[tuple[Race, int]]:
    row = db.execute(
        select(Race, Season.year)
        .join(Season, Race.season_id == Season.id)
        .where(Race.race_date >= from_date)
        .order_by(Race.race_date.asc(), Race.round_number.asc())
        .limit(1)
    ).one_or_none()
    return [row] if row is not None else []


def validate_args(args: argparse.Namespace) -> None:
    target_count = int(args.race_id is not None) + int(args.next_race) + int(bool(args.seasons))
    if target_count != 1:
        raise ValueError("Specify exactly one target selector: --seasons, --race-id, or --next-race.")
    if args.round_number is not None and not args.seasons:
        raise ValueError("--round can only be used with --seasons.")
    if args.fallback_pre_qualifying and args.context not in {POST_QUALIFYING, "all"}:
        raise ValueError("--fallback-pre-qualifying only applies to post_qualifying generation.")


def query_target_races(db: Session, args: argparse.Namespace) -> list[tuple[Race, int]]:
    if args.race_id is not None:
        return query_race_by_id(db, args.race_id)
    if args.next_race:
        return query_next_race(db, date.today())
    return query_races(db, args.seasons, args.round_number)


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


def is_upcoming_race(race: Race, today: date | None = None) -> bool:
    return race.race_date >= (today or date.today())


def weather_features(db: Session, race_id: int) -> tuple[bool, float | None]:
    weather_rows = list(
        db.execute(select(WeatherData).where(WeatherData.race_id == race_id))
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


def prior_feature_medians(db: Session, race: Race, feature_context: str) -> dict[str, float]:
    rows = list(
        db.execute(
            select(MLFeature)
            .join(Race, MLFeature.race_id == Race.id)
            .where(
                MLFeature.feature_context == feature_context,
                Race.race_date < race.race_date,
            )
        )
        .scalars()
        .all()
    )
    medians: dict[str, float] = {}
    for feature_name in NUMERIC_FEATURES:
        values = [
            float(value)
            for row in rows
            if (value := getattr(row, feature_name)) is not None
        ]
        if values:
            medians[feature_name] = float(median(values))
    return medians


def current_entry_medians(entries: list[dict[str, Any]]) -> dict[str, float]:
    medians: dict[str, float] = {}
    for feature_name in ("grid_position", "qualifying_position", "gap_to_pole_ms"):
        values = [
            float(value)
            for entry in entries
            if (value := entry.get(feature_name)) is not None
        ]
        if values:
            medians[feature_name] = float(median(values))
    return medians


def fill_missing_numeric_features(
    feature_row: dict[str, Any],
    medians: dict[str, float],
) -> dict[str, Any]:
    filled = feature_row.copy()
    preserve_null_features: set[str] = set()
    if filled.get("feature_context") == PRE_QUALIFYING:
        preserve_null_features = {"grid_position", "qualifying_position", "gap_to_pole_ms"}

    for feature_name in NUMERIC_FEATURES:
        if feature_name in preserve_null_features:
            continue
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


def latest_prior_race_result_rows(db: Session, before_date: date) -> tuple[list[RaceResult], date | None]:
    prior_race = db.execute(
        select(RaceResult.race_id, Race.race_date)
        .join(Race, RaceResult.race_id == Race.id)
        .where(Race.race_date < before_date)
        .order_by(Race.race_date.desc(), Race.round_number.desc())
        .limit(1)
    ).one_or_none()
    if prior_race is None:
        return [], None

    rows = list(
        db.execute(
            select(RaceResult)
            .where(RaceResult.race_id == prior_race.race_id)
            .order_by(RaceResult.grid_position.asc().nulls_last(), RaceResult.driver_id.asc())
        )
        .scalars()
        .all()
    )
    return rows, prior_race.race_date


def latest_prior_team_id(db: Session, driver_id: int, before_date: date) -> int | None:
    return db.execute(
        select(RaceResult.team_id)
        .join(Race, RaceResult.race_id == Race.id)
        .where(RaceResult.driver_id == driver_id, Race.race_date < before_date)
        .order_by(Race.race_date.desc(), Race.round_number.desc())
        .limit(1)
    ).scalar_one_or_none()


def pre_qualifying_entries(db: Session, race: Race) -> list[dict[str, Any]]:
    rows, data_cutoff_date = latest_prior_race_result_rows(db, race.race_date)
    if not rows:
        LOGGER.warning(
            "No completed prior race results found before Race %s (%s); expected driver/team mapping is uncertain.",
            race.id,
            race.race_date,
        )
    entries: list[dict[str, Any]] = []
    seen_driver_ids: set[int] = set()
    for row in rows:
        if row.driver_id in seen_driver_ids:
            continue
        entries.append(
            {
                "driver_id": row.driver_id,
                "team_id": row.team_id,
                "grid_position": None,
                "qualifying_position": None,
                "gap_to_pole_ms": None,
                "data_cutoff_date": data_cutoff_date or race.race_date,
            }
        )
        seen_driver_ids.add(row.driver_id)
    return entries


def post_qualifying_entries(db: Session, race: Race) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for qualifying_result in qualifying_results_for_race(db, race.id):
        race_result = None if is_upcoming_race(race) else current_race_result(db, race.id, qualifying_result.driver_id)
        grid_position = race_result.grid_position if race_result is not None else qualifying_result.position
        team_id = (
            race_result.team_id
            if race_result is not None
            else latest_prior_team_id(db, qualifying_result.driver_id, race.race_date)
        )
        if team_id is None:
            LOGGER.warning(
                "Skipping Race %s driver %s: no latest known team for post-qualifying features.",
                race.id,
                qualifying_result.driver_id,
            )
            continue

        gap_to_pole_ms = qualifying_result.gap_to_pole_ms
        if qualifying_result.position == 1:
            gap_to_pole_ms = 0.0

        entries.append(
            {
                "driver_id": qualifying_result.driver_id,
                "team_id": team_id,
                "grid_position": float(grid_position) if grid_position is not None else None,
                "qualifying_position": (
                    float(qualifying_result.position) if qualifying_result.position is not None else None
                ),
                "gap_to_pole_ms": gap_to_pole_ms,
                "data_cutoff_date": race.race_date,
            }
        )
    return entries


def feature_entries_for_context(db: Session, race: Race, feature_context: str) -> list[dict[str, Any]]:
    if feature_context == PRE_QUALIFYING:
        return pre_qualifying_entries(db, race)
    if feature_context == POST_QUALIFYING:
        return post_qualifying_entries(db, race)
    raise ValueError(f"Unsupported feature context: {feature_context}")


def existing_feature_count(db: Session, race_id: int, feature_context: str) -> int:
    return len(
        db.execute(
            select(MLFeature.id).where(
                MLFeature.race_id == race_id,
                MLFeature.feature_context == feature_context,
            )
        )
        .scalars()
        .all()
    )


def resolve_feature_context(
    db: Session,
    race: Race,
    requested_context: str,
    fallback_pre_qualifying: bool,
) -> str:
    if requested_context != POST_QUALIFYING:
        return requested_context
    if qualifying_results_for_race(db, race.id):
        return POST_QUALIFYING
    if fallback_pre_qualifying:
        LOGGER.warning(
            "Race %s has no qualifying results; falling back to %s features.",
            race.id,
            PRE_QUALIFYING,
        )
        return PRE_QUALIFYING
    raise RuntimeError(
        f"Race {race.id} has no qualifying results. "
        "Run pre_qualifying or pass --fallback-pre-qualifying."
    )


def build_feature_row(
    db: Session,
    race: Race,
    entry: dict[str, Any],
    feature_context: str,
) -> dict[str, Any]:
    driver_id = entry["driver_id"]
    team_id = entry["team_id"]
    circuit_avg_finish, circuit_dnf_rate = circuit_history(db, driver_id, race)
    weather_is_wet, avg_track_temp_c = weather_features(db, race.id)

    return {
        "race_id": race.id,
        "driver_id": driver_id,
        "feature_context": feature_context,
        "grid_position": entry["grid_position"],
        "qualifying_position": entry["qualifying_position"],
        "gap_to_pole_ms": entry["gap_to_pole_ms"],
        "avg_race_pace_ms": avg_race_pace_ms(db, driver_id, race.race_date),
        "driver_recent_form": driver_recent_form(db, driver_id, race.race_date),
        "team_recent_form": team_recent_form(db, team_id, race.race_date),
        "circuit_history_avg_finish": circuit_avg_finish,
        "circuit_history_dnf_rate": circuit_dnf_rate,
        "dnf_rate_recent": dnf_rate_recent(db, driver_id, race.race_date),
        "weather_is_wet": weather_is_wet,
        "avg_track_temp_c": avg_track_temp_c,
        "uses_current_qualifying": feature_context == POST_QUALIFYING,
        "data_cutoff_date": entry["data_cutoff_date"],
    }


def should_skip_feature_row(feature_row: dict[str, Any], race: Race, driver_id: int, feature_context: str) -> bool:
    return False


def process_race(
    db: Session,
    race: Race,
    year: int,
    feature_context: str,
    feature_history: dict[str, list[float]],
    force: bool,
) -> dict[str, int]:
    counts = {
        "features": 0,
        "missing_pace": 0,
        "podiums": 0,
        "top10s": 0,
        "dnfs": 0,
    }

    LOGGER.info(
        "Processing %s Round %s %s features: %s",
        year,
        race.round_number,
        feature_context,
        race.race_name,
    )
    if not force and existing_feature_count(db, race.id, feature_context) > 0:
        LOGGER.info(
            "Skipping Race %s %s features because rows already exist. Use --force to regenerate.",
            race.id,
            feature_context,
        )
        return counts

    entries = feature_entries_for_context(db, race, feature_context)
    if not entries:
        LOGGER.warning(
            "No %s feature entries for %s Round %s.",
            feature_context,
            year,
            race.round_number,
        )
    entry_medians = current_entry_medians(entries)

    for entry in entries:
        driver_id = entry["driver_id"]
        feature_row = build_feature_row(db, race, entry, feature_context)
        if should_skip_feature_row(feature_row, race, driver_id, feature_context):
            continue

        if feature_row["avg_race_pace_ms"] is None:
            counts["missing_pace"] += 1
            LOGGER.warning(
                "Race %s driver %s has no prior avg_race_pace_ms history.",
                race.id,
                driver_id,
            )

        medians = prior_feature_medians(db, race, feature_context)
        medians.update(entry_medians)
        medians.update(season_medians(feature_history))
        feature_row = fill_missing_numeric_features(feature_row, medians)
        feature_row["generated_at"] = datetime.now(UTC)
        upsert(db, MLFeature, ["race_id", "driver_id", "feature_context"], feature_row)
        update_feature_history(feature_history, feature_row)

        counts["features"] += 1
        race_result = None if is_upcoming_race(race) else current_race_result(db, race.id, driver_id)
        if race_result is not None:
            targets = target_metrics(race_result)
            counts["podiums"] += int(targets["finished_podium"])
            counts["top10s"] += int(targets["finished_top10"])
            counts["dnfs"] += int(targets["dnf"])

    return counts


def main() -> None:
    args = parse_args()
    configure_logging(args.verbose)
    validate_args(args)

    contexts = (
        [PRE_QUALIFYING, POST_QUALIFYING]
        if args.context == "all"
        else [args.context]
    )
    season_counts: dict[tuple[int, str], dict[str, int]] = defaultdict(
        lambda: {"features": 0, "missing_pace": 0, "podiums": 0, "top10s": 0, "dnfs": 0}
    )
    season_feature_history: dict[tuple[int, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    with get_session() as db:
        races = query_target_races(db, args)

    if not races:
        LOGGER.warning(
            "No races found for seasons=%s race_id=%s next_race=%s round=%s",
            args.seasons,
            args.race_id,
            args.next_race,
            args.round_number,
        )

    for race, year in races:
        processed_contexts: set[str] = set()
        for requested_context in contexts:
            try:
                with get_session() as db:
                    feature_context = resolve_feature_context(
                        db,
                        race,
                        requested_context,
                        args.fallback_pre_qualifying,
                    )
                    if feature_context in processed_contexts:
                        LOGGER.info("Skipping duplicate %s context for Race %s.", feature_context, race.id)
                        continue
                    processed_contexts.add(feature_context)
                    history_key = (year, feature_context)
                    race_counts = process_race(
                        db,
                        race,
                        year,
                        feature_context,
                        season_feature_history[history_key],
                        args.force,
                    )
            except Exception:
                LOGGER.exception("Failed to process %s Round %s context=%s", year, race.round_number, requested_context)
                if args.context != "all":
                    raise
                continue

            for key, value in race_counts.items():
                season_counts[(year, feature_context)][key] += value

    summary_years = sorted({year for _, year in races} | set(args.seasons or []))
    summary_contexts = sorted(set(contexts) | {key[1] for key in season_counts})
    for year in summary_years:
        for feature_context in summary_contexts:
            counts = season_counts[(year, feature_context)]
            features = counts["features"]
            missing_pace_pct = (counts["missing_pace"] / features * 100) if features else 0.0
            message = (
                f"Season {year} {feature_context}: {features} feature rows, "
                f"{missing_pace_pct:.1f}% missing avg_race_pace_ms before median fill, "
                f"{counts['podiums']} podium labels, "
                f"{counts['top10s']} top10 labels, "
                f"{counts['dnfs']} DNFs."
            )
            LOGGER.info(message)
            print(message)


if __name__ == "__main__":
    main()
