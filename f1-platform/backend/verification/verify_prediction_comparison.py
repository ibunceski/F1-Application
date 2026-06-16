from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://verify:verify@localhost/verify")
os.environ.setdefault("ENVIRONMENT", "test")

from app.models import Base
from app.models.driver import Driver
from app.models.ml_feature import MLFeature, POST_QUALIFYING
from app.models.prediction import Prediction
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.team import Team
from app.services.prediction_service import PredictionService


class AsyncSessionAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


def add_driver(db: Session, team: Team, number: int, code: str) -> Driver:
    driver = Driver(
        driver_number=number,
        full_name=f"{code} Driver",
        abbreviation=code[:3],
        nationality="GB",
        team_id=team.id,
        driver_id=code,
    )
    db.add(driver)
    db.flush()
    return driver


def seed_base(db: Session) -> tuple[Race, Race, Race, list[Driver], Team]:
    team = Team(name="Comparison Racing", short_name="CMP", nationality="GB", constructor_id="comparison")
    db.add(team)
    db.flush()
    drivers = [add_driver(db, team, index, f"C{index}") for index in range(1, 4)]
    season = Season(year=2026, total_races=3)
    db.add(season)
    db.flush()
    races = []
    for round_number in range(1, 4):
        race = Race(
            season_id=season.id,
            round_number=round_number,
            circuit_name=f"Comparison Circuit {round_number}",
            circuit_location="Comparison City",
            circuit_country="Comparison Country",
            race_name=f"Comparison GP {round_number}",
            race_date=date.today() - timedelta(days=30 - round_number),
            session_key=None,
        )
        db.add(race)
        races.append(race)
    db.flush()
    return races[0], races[1], races[2], drivers, team


def add_features_predictions_and_results(db: Session, race: Race, drivers: list[Driver], team: Team) -> None:
    predictions = [1.2, 2.4, 3.1]
    actuals = [1, 3, 2]
    for driver, predicted_position, actual_position in zip(drivers, predictions, actuals, strict=True):
        db.add(
            MLFeature(
                race_id=race.id,
                driver_id=driver.id,
                feature_context=POST_QUALIFYING,
                grid_position=float(driver.driver_number),
                qualifying_position=float(driver.driver_number),
                gap_to_pole_ms=float(driver.driver_number * 100),
                avg_race_pace_ms=90000.0,
                driver_recent_form=2.0,
                team_recent_form=2.0,
                circuit_history_avg_finish=2.0,
                circuit_history_dnf_rate=0.0,
                dnf_rate_recent=0.0,
                weather_is_wet=False,
                avg_track_temp_c=30.0,
                uses_current_qualifying=True,
                data_cutoff_date=race.race_date,
            )
        )
        db.add(
            Prediction(
                race_id=race.id,
                driver_id=driver.id,
                prediction_context=POST_QUALIFYING,
                model_context=POST_QUALIFYING,
                feature_context=POST_QUALIFYING,
                model_version="comparison-test",
                predicted_position=predicted_position,
                top10_probability=0.9,
                podium_probability=0.8,
                winner_probability=0.5 if predicted_position == 1.2 else 0.25,
                predicted_position_gain=None,
                confidence_score=0.8,
                generated_at=datetime.now(UTC),
            )
        )
        db.add(
            RaceResult(
                race_id=race.id,
                driver_id=driver.id,
                team_id=team.id,
                grid_position=driver.driver_number,
                finishing_position=actual_position,
                classified_position=str(actual_position),
                status="Finished",
                points=float(26 - actual_position),
                laps_completed=58,
                fastest_lap=False,
            )
        )
    db.commit()


async def expect_http_error(service: PredictionService, race_id: int, status_code: int, detail: str) -> None:
    try:
        await service.get_prediction_comparison(race_id)
    except HTTPException as exc:
        assert exc.status_code == status_code
        assert exc.detail == detail
    else:
        raise AssertionError(f"Expected HTTP {status_code}")


async def verify() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine, future=True) as db:
        comparison_race, no_results_race, no_predictions_race, drivers, team = seed_base(db)
        add_features_predictions_and_results(db, comparison_race, drivers, team)
        db.add(
            Prediction(
                race_id=no_results_race.id,
                driver_id=drivers[0].id,
                prediction_context=POST_QUALIFYING,
                model_context=POST_QUALIFYING,
                feature_context=POST_QUALIFYING,
                model_version="comparison-test",
                predicted_position=1.0,
                generated_at=datetime.now(UTC),
            )
        )
        db.add(
            RaceResult(
                race_id=no_predictions_race.id,
                driver_id=drivers[0].id,
                team_id=team.id,
                grid_position=1,
                finishing_position=1,
                classified_position="1",
                status="Finished",
                points=25.0,
                laps_completed=58,
                fastest_lap=False,
            )
        )
        db.commit()

        service = PredictionService(AsyncSessionAdapter(db))
        before_count = len(db.execute(select(Prediction.id)).scalars().all())
        comparison = await service.get_prediction_comparison(comparison_race.id, POST_QUALIFYING)
        after_count = len(db.execute(select(Prediction.id)).scalars().all())
        assert before_count == after_count
        assert comparison.context == POST_QUALIFYING
        assert comparison.model_version == "comparison-test"
        assert comparison.summary.mae > 0
        assert comparison.summary.rmse >= comparison.summary.mae
        assert comparison.summary.winner_correct is True
        assert len(comparison.drivers) == 3

        await expect_http_error(service, no_results_race.id, 400, "Race results are not available yet.")
        await expect_http_error(
            service,
            no_predictions_race.id,
            404,
            "Predictions have not been generated for this race.",
        )

    print("OK: prediction comparison covers success, no results, and no predictions.")


if __name__ == "__main__":
    asyncio.run(verify())
