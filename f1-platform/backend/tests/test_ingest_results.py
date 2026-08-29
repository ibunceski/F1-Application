"""Regression tests for result-ingestion fallbacks."""

from __future__ import annotations

import sys
import unittest
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion import ingest_results  # noqa: E402


class RaceResultIngestionTests(unittest.TestCase):
    def test_uses_jolpica_when_fastf1_session_load_fails(self) -> None:
        race = SimpleNamespace(id=1, round_number=1)
        fallback_rows = [
            {
                "abbreviation": "VER",
                "team_name": "Red Bull",
                "grid_position": 1,
                "finishing_position": 1,
                "classified_position": "1",
                "status": "Finished",
                "points": 25.0,
                "laps_completed": 57,
                "fastest_lap": True,
                "fastest_lap_time_ms": 90_000.0,
                "fastest_lap_rank": 1,
            }
        ]
        failing_session = SimpleNamespace(load=lambda **_: (_ for _ in ()).throw(KeyError("DriverNumber")))

        with (
            patch.object(ingest_results.fastf1, "get_session", return_value=failing_session),
            patch.object(ingest_results, "_jolpica_sprint_points", return_value={"VER": 8.0}),
            patch.object(ingest_results, "_jolpica_race_rows", return_value=fallback_rows) as fallback,
            patch.object(ingest_results, "get_session", return_value=nullcontext(SimpleNamespace())),
            patch.object(ingest_results, "_lookup_driver", return_value=SimpleNamespace(id=10)),
            patch.object(ingest_results, "_lookup_team", return_value=SimpleNamespace(id=20)),
            patch.object(ingest_results, "upsert") as upsert,
        ):
            saved_count = ingest_results.ingest_race_results(race, 2022)

        self.assertEqual(saved_count, 1)
        fallback.assert_called_once_with(2022, 1)
        self.assertEqual(upsert.call_args.args[3]["sprint_points"], 8.0)


if __name__ == "__main__":
    unittest.main()
