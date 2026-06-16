from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

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
from app.models.ml_feature import MLFeature, POST_QUALIFYING, PRE_QUALIFYING
from app.models.prediction import Prediction
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.team import Team
from app.main import app
from app.services import prediction_service as prediction_service_module
from app.services.prediction_service import PredictionService


class AsyncSessionAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def commit(self) -> None:
        self.session.commit()

    def add_all(self, values: list[Any]) -> None:
        self.session.add_all(values)


class FakeRegressor:
    def __init__(self, base: float) -> None:
        self.base = base

    def predict(self, frame):
        adjustment = float(frame.iloc[0].get("driver_recent_form", 0) or 0) / 10.0
        return [self.base + adjustment]


class FakeClassifier:
    def __init__(self, probability: float) -> None:
        self.probability = probability

    def predict_proba(self, _frame):
        return [[1.0 - self.probability, self.probability]]


class FakeModelStore:
    def __init__(self, missing_context: str | None = None) -> None:
        self.missing_context = missing_context
        self.model_metadata_by_context = {
            PRE_QUALIFYING: {"trained_at": "workflow-pre-test", "feature_columns": prediction_service_module.PRE_QUALIFYING_FEATURE_COLS},
            POST_QUALIFYING: {"trained_at": "workflow-post-test", "feature_columns": prediction_service_module.POST_QUALIFYING_FEATURE_COLS},
        }
        self.feature_importances_by_context = {}

    def is_ready(self, context: str = POST_QUALIFYING) -> bool:
        return context != self.missing_context

    def models_for_context(self, _context: str) -> dict[str, Any]:
        return {
            "position_model": FakeRegressor(4.0),
            "top10_model": FakeClassifier(0.8),
            "podium_model": FakeClassifier(0.4),
            "position_gain_model": FakeRegressor(0.5),
        }

    def metadata_for_context(self, context: str) -> dict[str, Any]:
        return self.model_metadata_by_context.get(context, {})

    def feature_columns_for_context(self, context: str) -> list[str]:
        return list(self.metadata_for_context(context).get("feature_columns") or [])


def install_fake_models(missing_context: str | None = None):
    original = prediction_service_module.model_store
    prediction_service_module.model_store = FakeModelStore(missing_context=missing_context)
    return original


def restore_models(original) -> None:
    prediction_service_module.model_store = original


def verify_prediction_routes_registered() -> None:
    paths = set(app.openapi()["paths"])
    required = {
        "/api/v1/predictions/next-race/context",
        "/api/v1/predictions/next-race/generate",
        "/api/v1/predictions/next-race",
        "/api/v1/predictions/races/{race_id}/comparison",
    }
    missing = required - paths
    assert not missing, f"Prediction routes missing from OpenAPI: {sorted(missing)}"


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


def seed_base(db: Session) -> tuple[Season, Team, list[Driver]]:
    season = Season(year=2026, total_races=4)
    team = Team(name="Workflow Racing", short_name="WFL", nationality="GB", constructor_id="workflow")
    db.add_all([season, team])
    db.flush()
    drivers = [add_driver(db, team, number, f"W{number}") for number in range(1, 4)]
    db.commit()
    return season, team, drivers


def add_race(db: Session, season: Season, round_number: int, race_date: date, name: str) -> Race:
    race = Race(
        season_id=season.id,
        round_number=round_number,
        circuit_name=f"{name} Circuit",
        circuit_location="Workflow City",
        circuit_country="Workflow Country",
        race_name=name,
        race_date=race_date,
        session_key=None,
    )
    db.add(race)
    db.commit()
    db.refresh(race)
    return race


def add_features(db: Session, race: Race, drivers: list[Driver], context: str) -> None:
    for index, driver in enumerate(drivers, start=1):
        uses_qualifying = context == POST_QUALIFYING
        db.add(
            MLFeature(
                race_id=race.id,
                driver_id=driver.id,
                feature_context=context,
                grid_position=float(index) if uses_qualifying else None,
                qualifying_position=float(index) if uses_qualifying else None,
                gap_to_pole_ms=float(index * 100) if uses_qualifying else None,
                avg_race_pace_ms=90000.0 + index,
                driver_recent_form=float(index),
                team_recent_form=2.0,
                circuit_history_avg_finish=5.0,
                circuit_history_dnf_rate=0.1,
                dnf_rate_recent=0.1,
                weather_is_wet=False,
                avg_track_temp_c=30.0,
                uses_current_qualifying=uses_qualifying,
                data_cutoff_date=race.race_date if uses_qualifying else race.race_date - timedelta(days=1),
            )
        )
    db.commit()


def add_qualifying(db: Session, race: Race, team: Team, drivers: list[Driver]) -> None:
    for index, driver in enumerate(drivers, start=1):
        db.add(
            QualifyingResult(
                race_id=race.id,
                driver_id=driver.id,
                team_id=team.id,
                position=index,
                q1_time_ms=90000.0 + index,
                q2_time_ms=89000.0 + index,
                q3_time_ms=88000.0 + index,
                best_time_ms=88000.0 + index,
                gap_to_pole_ms=float(index - 1),
            )
        )
    db.commit()


def add_results(db: Session, race: Race, team: Team, drivers: list[Driver]) -> None:
    actual_positions = [1, 3, 2]
    for driver, actual_position in zip(drivers, actual_positions, strict=True):
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


async def expect_http_error(coro, status_code: int, message_fragment: str) -> None:
    try:
        await coro
    except HTTPException as exc:
        assert exc.status_code == status_code, exc.detail
        assert message_fragment in str(exc.detail), exc.detail
    else:
        raise AssertionError(f"Expected HTTP {status_code}")


async def verify() -> None:
    verify_prediction_routes_registered()
    original_store = install_fake_models()
    try:
        engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)

        with Session(engine, future=True) as db:
            season, team, drivers = seed_base(db)
            future_race = add_race(db, season, 1, date.today() + timedelta(days=10), "Future Workflow GP")
            past_race = add_race(db, season, 2, date.today() - timedelta(days=30), "Past Workflow GP")
            missing_feature_race = add_race(db, season, 3, date.today() + timedelta(days=20), "Missing Feature GP")

            add_features(db, future_race, drivers, PRE_QUALIFYING)
            add_features(db, past_race, drivers, POST_QUALIFYING)
            add_results(db, past_race, team, drivers)

            service = PredictionService(AsyncSessionAdapter(db))

            before_qualifying = await service.get_next_race_context()
            assert before_qualifying.recommended_context == PRE_QUALIFYING
            assert before_qualifying.qualifying_available is False
            pre_predictions = await service.generate_next_race_predictions("auto", force_regenerate=True)
            assert pre_predictions
            assert all(prediction.model_context == PRE_QUALIFYING for prediction in pre_predictions)
            assert db.execute(select(RaceResult).where(RaceResult.race_id == future_race.id)).first() is None

            add_qualifying(db, future_race, team, drivers)
            add_features(db, future_race, drivers, POST_QUALIFYING)
            after_qualifying = await service.get_next_race_context()
            assert after_qualifying.recommended_context == POST_QUALIFYING
            assert after_qualifying.qualifying_available is True
            post_predictions = await service.generate_next_race_predictions("auto", force_regenerate=True)
            assert post_predictions
            assert all(prediction.model_context == POST_QUALIFYING for prediction in post_predictions)
            assert db.execute(select(RaceResult).where(RaceResult.race_id == future_race.id)).first() is None

            # Generate comparison rows for a past race with actual results.
            await service.generate_predictions(past_race.id, force_regenerate=True, prediction_context=POST_QUALIFYING)
            comparison = await service.get_prediction_comparison(past_race.id, context="latest")
            assert comparison.summary.mae >= 0
            assert comparison.summary.rmse >= comparison.summary.mae
            assert len(comparison.drivers) == len(drivers)

            await expect_http_error(
                service.generate_predictions(missing_feature_race.id, force_regenerate=True, prediction_context=PRE_QUALIFYING),
                400,
                "Features missing",
            )

            restore_models(original_store)
            original_store = install_fake_models(missing_context=PRE_QUALIFYING)
            await expect_http_error(
                service.generate_predictions(missing_feature_race.id, force_regenerate=True, prediction_context=PRE_QUALIFYING),
                503,
                "models not loaded",
            )

            pre_features = db.execute(
                select(MLFeature).where(MLFeature.race_id == future_race.id, MLFeature.feature_context == PRE_QUALIFYING)
            ).scalars().all()
            post_features = db.execute(
                select(MLFeature).where(MLFeature.race_id == future_race.id, MLFeature.feature_context == POST_QUALIFYING)
            ).scalars().all()
            assert pre_features
            assert post_features
            assert all(feature.uses_current_qualifying is False for feature in pre_features)
            assert all(feature.grid_position is None for feature in pre_features)
            assert all(feature.qualifying_position is None for feature in pre_features)
            assert all(feature.gap_to_pole_ms is None for feature in pre_features)
            assert all(feature.data_cutoff_date < future_race.race_date for feature in pre_features)
            assert all(feature.uses_current_qualifying is True for feature in post_features)
            assert all(feature.qualifying_position is not None for feature in post_features)
            assert db.execute(select(RaceResult).where(RaceResult.race_id == future_race.id)).first() is None

    finally:
        restore_models(original_store)

    print("OK: end-to-end prediction workflow verification passed.")


if __name__ == "__main__":
    asyncio.run(verify())
