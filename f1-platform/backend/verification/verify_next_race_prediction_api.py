from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://verify:verify@localhost/verify")
os.environ.setdefault("ENVIRONMENT", "test")

from app.models import Base
from app.models.driver import Driver
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.season import Season
from app.models.team import Team
from app.services.prediction_service import PredictionService


class AsyncSessionAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


def seed_next_race(db: Session) -> tuple[Race, Driver, Team]:
    team = Team(name="Next API Racing", short_name="NAR", nationality="GB", constructor_id="next_api")
    driver = Driver(
        driver_number=4,
        full_name="Next API Driver",
        abbreviation="NXT",
        nationality="GB",
        team_id=None,
        driver_id="NXT",
    )
    season = Season(year=2026, total_races=1)
    db.add_all([team, driver, season])
    db.flush()
    driver.team_id = team.id
    race = Race(
        season_id=season.id,
        round_number=1,
        circuit_name="Next API Circuit",
        circuit_location="Next City",
        circuit_country="Next Country",
        race_name="Next API Grand Prix",
        race_date=date.today() + timedelta(days=12),
        session_key=None,
    )
    db.add(race)
    db.commit()
    db.refresh(race)
    db.refresh(driver)
    db.refresh(team)
    return race, driver, team


async def verify() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine, future=True) as db:
        race, driver, team = seed_next_race(db)
        service = PredictionService(AsyncSessionAdapter(db))

        context = await service.get_next_race_context()
        assert context.race.id == race.id
        assert context.recommended_context == "pre_qualifying"
        assert context.qualifying_available is False
        assert context.days_until_race == 12

        try:
            await service.resolve_prediction_context(race.id, "post_qualifying")
        except HTTPException as exc:
            assert exc.status_code == 409
        else:
            raise AssertionError("post_qualifying should fail when qualifying is unavailable")

        db.add(
            QualifyingResult(
                race_id=race.id,
                driver_id=driver.id,
                team_id=team.id,
                position=1,
                q1_time_ms=90000.0,
                q2_time_ms=89000.0,
                q3_time_ms=88000.0,
                best_time_ms=88000.0,
                gap_to_pole_ms=0.0,
            )
        )
        db.commit()

        assert await service.resolve_prediction_context(race.id, "auto") == "post_qualifying"
        context = await service.get_next_race_context()
        assert context.recommended_context == "post_qualifying"
        assert context.qualifying_available is True

    print("OK: next-race prediction context API behavior is correct.")


if __name__ == "__main__":
    asyncio.run(verify())
