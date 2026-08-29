import unittest

from app.services.prediction_service import DEFAULT_FEATURE_COLS

EXPECTED_PRE = [
    "avg_race_pace_ms",
    "driver_recent_form",
    "team_recent_form",
    "circuit_history_avg_finish",
    "circuit_history_dnf_rate",
    "dnf_rate_recent",
]
EXPECTED_POST = [
    "grid_position",
    "qualifying_position",
    "gap_to_pole_ms",
    *EXPECTED_PRE,
]


class PredictionServiceFeaturesTests(unittest.TestCase):
    def test_default_feature_cols_match_training_and_exclude_weather(self):
        self.assertEqual(DEFAULT_FEATURE_COLS["pre_qualifying"], EXPECTED_PRE)
        self.assertEqual(DEFAULT_FEATURE_COLS["post_qualifying"], EXPECTED_POST)
        for cols in DEFAULT_FEATURE_COLS.values():
            self.assertNotIn("weather_is_wet", cols)
            self.assertNotIn("avg_track_temp_c", cols)
