import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ml_pipeline import feature_engineering


class GridParityTests(unittest.TestCase):
    def test_post_qualifying_grid_uses_qualifying_position_not_race_result(self):
        race = SimpleNamespace(id=9, round_number=1, race_date=date(2024, 3, 2), circuit_name="X", race_name="X GP")
        qr = SimpleNamespace(driver_id=1, position=3, gap_to_pole_ms=150.0)
        rr = SimpleNamespace(driver_id=1, grid_position=6, team_id=7)
        with (
            patch.object(feature_engineering, "qualifying_results_for_race", return_value=[qr]),
            patch.object(feature_engineering, "is_upcoming_race", return_value=False),
            patch.object(feature_engineering, "current_race_result", return_value=rr),
            patch.object(feature_engineering, "latest_prior_team_id", return_value=7),
        ):
            entries = feature_engineering.post_qualifying_entries(MagicMock(), race)
        self.assertEqual(entries[0]["grid_position"], 3.0)
        self.assertEqual(entries[0]["grid_position_source"], "qualifying_position")
