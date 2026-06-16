from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://verify:verify@localhost/verify")
os.environ.setdefault("ENVIRONMENT", "test")

from app.models import Base
from app.models.driver import Driver
from app.models.ml_feature import MLFeature, POST_QUALIFYING, PRE_QUALIFYING
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.team import Team
from ml_pipeline.feature_engineering import (
    build_feature_row,
    feature_entries_for_context,
    resolve_feature_context,
)


def seed_context_data(db: Session) -> tuple[Race, Driver]:
    team = Team(
        name="Context Racing",
        short_name="CTX",
        nationality="GB",
        constructor_id="context_racing",
    )
    driver = Driver(
        driver_number=44,
        full_name="Context Driver",
        abbreviation="CTX",
        nationality="GB",
        team_id=None,
        driver_id="CTX",
    )
    db.add_all([team, driver])
    db.flush()
    driver.team_id = team.id

    season = Season(year=2026, total_races=2)
    db.add(season)
    db.flush()

    prior_race = Race(
        season_id=season.id,
        round_number=1,
        circuit_name="Prior Circuit",
        circuit_location="Prior City",
        circuit_country="Prior Country",
        race_name="Prior Grand Prix",
        race_date=date.today() - timedelta(days=14),
        session_key=None,
    )
    future_race = Race(
        season_id=season.id,
        round_number=2,
        circuit_name="Future Circuit",
        circuit_location="Future City",
        circuit_country="Future Country",
        race_name="Future Grand Prix",
        race_date=date.today() + timedelta(days=7),
        session_key=None,
    )
    db.add_all([prior_race, future_race])
    db.flush()

    db.add(
        RaceResult(
            race_id=prior_race.id,
            driver_id=driver.id,
            team_id=team.id,
            grid_position=3,
            finishing_position=2,
            classified_position="2",
            status="Finished",
            points=18.0,
            laps_completed=58,
            fastest_lap=False,
        )
    )
    db.commit()
    db.refresh(future_race)
    db.refresh(driver)
    return future_race, driver


def verify() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine, future=True) as db:
        future_race, driver = seed_context_data(db)

        pre_entries = feature_entries_for_context(db, future_race, PRE_QUALIFYING)
        assert len(pre_entries) == 1
        pre_feature = build_feature_row(db, future_race, pre_entries[0], PRE_QUALIFYING)
        assert pre_feature["driver_id"] == driver.id
        assert pre_feature["grid_position"] is None
        assert pre_feature["qualifying_position"] is None
        assert pre_feature["gap_to_pole_ms"] is None
        assert pre_feature["uses_current_qualifying"] is False
        assert pre_feature["data_cutoff_date"] < future_race.race_date

        try:
            resolve_feature_context(db, future_race, POST_QUALIFYING, fallback_pre_qualifying=False)
        except RuntimeError:
            pass
        else:
            raise AssertionError("post_qualifying without qualifying should fail")

        fallback_context = resolve_feature_context(
            db,
            future_race,
            POST_QUALIFYING,
            fallback_pre_qualifying=True,
        )
        assert fallback_context == PRE_QUALIFYING

        db.add(MLFeature(**pre_feature))
        db.add(
            QualifyingResult(
                race_id=future_race.id,
                driver_id=driver.id,
                team_id=driver.team_id,
                position=1,
                q1_time_ms=90000.0,
                q2_time_ms=89000.0,
                q3_time_ms=88000.0,
                best_time_ms=88000.0,
                gap_to_pole_ms=None,
            )
        )
        db.commit()

        post_entries = feature_entries_for_context(db, future_race, POST_QUALIFYING)
        assert len(post_entries) == 1
        post_feature = build_feature_row(db, future_race, post_entries[0], POST_QUALIFYING)
        assert post_feature["driver_id"] == driver.id
        assert post_feature["grid_position"] == 1.0
        assert post_feature["qualifying_position"] == 1.0
        assert post_feature["gap_to_pole_ms"] == 0.0
        assert post_feature["uses_current_qualifying"] is True
        assert post_feature["data_cutoff_date"] == future_race.race_date

        db.add(MLFeature(**post_feature))
        db.commit()

    print("OK: pre_qualifying and post_qualifying feature contexts are isolated.")


if __name__ == "__main__":
    verify()
