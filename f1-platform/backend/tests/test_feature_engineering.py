"""Regression tests for feature-engineering row hygiene."""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_pipeline import feature_engineering  # noqa: E402


class FeatureEngineeringHygieneTests(unittest.TestCase):
    def test_force_regeneration_deletes_stale_rows_before_upsert(self) -> None:
        race = SimpleNamespace(id=7, round_number=8, race_date=date(2023, 6, 1), circuit_name="X", race_name="X GP")
        entry = {
            "driver_id": 1,
            "team_id": 2,
            "grid_position": None,
            "qualifying_position": None,
            "gap_to_pole_ms": None,
            "data_cutoff_date": "2023-05-30",
        }

        fake_db = MagicMock()
        fake_delete = MagicMock()

        with (
            patch.object(feature_engineering, "delete", return_value=fake_delete),
            patch.object(
                feature_engineering,
                "feature_entries_for_context",
                return_value=[entry],
            ),
            patch.object(
                feature_engineering,
                "current_entry_medians",
                return_value={},
            ),
            patch.object(
                feature_engineering,
                "build_feature_row",
                return_value={"avg_race_pace_ms": None, "driver_id": 1},
            ),
            patch.object(feature_engineering, "prior_feature_medians", return_value={}),
            patch.object(feature_engineering, "season_medians", return_value={}),
            patch.object(feature_engineering, "fill_missing_numeric_features", side_effect=lambda row, _m: row),
            patch.object(feature_engineering, "upsert"),
            patch.object(feature_engineering, "current_race_result", return_value=None),
        ):
            feature_engineering.process_race(fake_db, race, 2023, "pre_qualifying", {}, force=True)

        fake_db.execute.assert_called_once_with(fake_delete.where.return_value)
        where_args = fake_delete.where.call_args.args
        conditions = [arg for arg in where_args if hasattr(arg, "left")]
        self.assertEqual(len(conditions), 2)
        race_condition = next(c for c in conditions if getattr(c.left, "key", None) == "race_id")
        self.assertEqual(race_condition.right.value, 7)

    def test_non_force_skips_when_rows_exist(self) -> None:
        race = SimpleNamespace(id=7, round_number=8, race_date=date(2023, 6, 1), circuit_name="X", race_name="X GP")

        fake_db = MagicMock()

        with (
            patch.object(feature_engineering, "existing_feature_count", return_value=3),
            patch.object(feature_engineering, "feature_entries_for_context") as entries,
        ):
            counts = feature_engineering.process_race(fake_db, race, 2023, "pre_qualifying", {}, force=False)

        self.assertEqual(counts["features"], 0)
        entries.assert_not_called()


if __name__ == "__main__":
    unittest.main()