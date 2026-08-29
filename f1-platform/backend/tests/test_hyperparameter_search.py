import unittest
import pandas as pd

from ml_pipeline.hyperparameter_search import (
    CLASSIFICATION_SEARCH_SPACES,
    REGRESSION_SEARCH_SPACES,
    build_model_from_config,
    select_hyperparameters,
)
from ml_pipeline.temporal_splits import generate_temporal_folds


class HyperparameterSearchTests(unittest.TestCase):
    def test_temporal_folds_match_original_behavior(self):
        folds = generate_temporal_folds([2021, 2022, 2023, 2024], min_train_seasons=1)
        self.assertEqual([f.validation_season for f in folds], [2022, 2023, 2024])
        self.assertEqual(folds[0].train_seasons, (2021,))

    def test_search_spaces_are_predeclared_and_bounded(self):
        self.assertGreaterEqual(len(REGRESSION_SEARCH_SPACES["Ridge"]), 1)
        self.assertGreaterEqual(len(CLASSIFICATION_SEARCH_SPACES["LogisticRegression"]), 1)
        for space in (REGRESSION_SEARCH_SPACES, CLASSIFICATION_SEARCH_SPACES):
            for name, configs in space.items():
                self.assertGreaterEqual(len(configs), 1)

    def test_build_model_from_config_is_sklearn_fittable(self):
        model = build_model_from_config(
            "Ridge", {"alpha": 1.0}, 42, ["driver_recent_form"], "position_model", pd.Series([1.0, 2.0])
        )
        X = pd.DataFrame({"driver_recent_form": [2.0, 3.0]})
        model.fit(X, pd.Series([1.0, 2.0]))
        self.assertEqual(model.predict(X).shape, (2,))

    def test_select_hyperparameters_returns_config_and_records(self):
        train = pd.DataFrame({
            "season_year": [2021, 2021, 2022, 2022, 2023, 2023],
            "driver_recent_form": [2.0, 12.0, 3.0, 13.0, 4.0, 14.0],
            "actual_finishing_position": [1.0, 11.0, 2.0, 12.0, 3.0, 13.0],
        })
        best, records = select_hyperparameters(
            "Ridge", REGRESSION_SEARCH_SPACES["Ridge"], train,
            "actual_finishing_position", ["driver_recent_form"], "position_model", seed=42,
        )
        self.assertIn("alpha", best)
        self.assertEqual(len(records), len(REGRESSION_SEARCH_SPACES["Ridge"]))

    def test_select_hyperparameters_returns_default_on_single_season(self):
        train = pd.DataFrame({
            "season_year": [2021, 2021, 2021, 2021],
            "driver_recent_form": [2.0, 12.0, 3.0, 13.0],
            "actual_finishing_position": [1.0, 11.0, 2.0, 12.0],
        })
        best, records = select_hyperparameters(
            "Ridge", REGRESSION_SEARCH_SPACES["Ridge"], train,
            "actual_finishing_position", ["driver_recent_form"], "position_model", seed=42,
        )
        self.assertEqual(best, REGRESSION_SEARCH_SPACES["Ridge"][0])
        self.assertEqual(len(records), 1)
