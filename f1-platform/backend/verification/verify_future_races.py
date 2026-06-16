from __future__ import annotations

import asyncio
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://verify:verify@localhost/verify")
os.environ.setdefault("ENVIRONMENT", "test")

from app.models import Base
from app.models.lap_time import LapTime
from app.models.qualifying_result import QualifyingResult
from app.models.race import Race
from app.models.race_result import RaceResult
from app.models.season import Season
from app.models.weather import WeatherData
from app.routers.races import get_next_race
from app.services.race_service import RaceService


class AsyncSessionAdapter:
    def __init__(self, session: Session) -> None:
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)


def _count_children(db: Session, model: type, race_id: int) -> int:
    return int(
        db.execute(
            select(func.count()).select_from(model).where(model.race_id == race_id)
        ).scalar_one()
    )


def seed_calendar_only_future_race(db: Session) -> Race:
    today = date.today()
    season = Season(year=2026, total_races=2)
    db.add(season)
    db.flush()

    db.add(
        Race(
            season_id=season.id,
            round_number=1,
            circuit_name="Completed Grand Prix",
            circuit_location="Completed City",
            circuit_country="Completed Country",
            race_name="Completed Grand Prix",
            race_date=today - timedelta(days=14),
            session_key=None,
        )
    )
    future_race = Race(
        season_id=season.id,
        round_number=2,
        circuit_name="Future Grand Prix",
        circuit_location="Future City",
        circuit_country="Future Country",
        race_name="Future Grand Prix",
        race_date=today + timedelta(days=7),
        session_key=None,
    )
    db.add(future_race)
    db.commit()
    db.refresh(future_race)
    return future_race


async def verify() -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine, future=True) as db:
        future_race = seed_calendar_only_future_race(db)

        child_models = (RaceResult, QualifyingResult, LapTime, WeatherData)
        child_counts = {
            model.__tablename__: _count_children(db, model, future_race.id)
            for model in child_models
        }
        assert all(count == 0 for count in child_counts.values()), child_counts

        service = RaceService(AsyncSessionAdapter(db))
        response = await get_next_race(service=service)
        assert response.id == future_race.id
        assert response.race_date >= date.today()

    print(
        "OK: future race exists without results/session data and "
        "/api/v1/races/next returns it."
    )


if __name__ == "__main__":
    asyncio.run(verify())
