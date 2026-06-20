"""Focused unit tests for the temporal experiment-runner contracts."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_pipeline.train_models import (  # noqa: E402
    GridPositionRegressor,
    MedianRegressor,
    ZeroChangeRegressor,
    assert_no_future_data,
    calibration_reliability,
    candidate_factories,
    choose_classification_threshold,
    classification_metrics,
    generate_temporal_folds,
    generate_thesis_figures,
    mean_per_race_spearman,
    regression_metrics,
    validate_artifact_schema,
    write_experiment_artifacts,
)


class TrainModelExperimentTests(unittest.TestCase):
    def test_expanding_temporal_folds_only_train_on_past_seasons(self) -> None:
        folds = generate_temporal_folds([2021, 2022, 2023, 2024, 2025], min_train_seasons=3)
        self.assertEqual([fold.validation_season for fold in folds], [2024, 2025])
        for fold in folds:
            self.assertLess(max(fold.train_seasons), fold.validation_season)

    def test_no_future_data_guard_rejects_overlapping_time(self) -> None:
        train = pd.DataFrame({"season_year": [2023], "race_date": ["2023-10-01"]})
        valid = pd.DataFrame({"season_year": [2024], "race_date": ["2024-03-01"]})
        assert_no_future_data(train, valid)
        with self.assertRaisesRegex(ValueError, "Temporal leakage"):
            assert_no_future_data(valid, train)

    def test_metrics_are_calculated_from_predictions(self) -> None:
        regression = regression_metrics(pd.Series([1.0, 2.0]), np.array([1.0, 4.0]), "position_model")
        self.assertAlmostEqual(regression["mae"], 1.0)
        self.assertAlmostEqual(regression["rmse"], np.sqrt(2.0))
        classification = classification_metrics(pd.Series([0, 1, 1, 0]), np.array([0.1, 0.9, 0.8, 0.2]), 0.5)
        self.assertAlmostEqual(classification["f1"], 1.0)
        self.assertAlmostEqual(classification["roc_auc"], 1.0)
        self.assertAlmostEqual(classification["pr_auc"], 1.0)
        self.assertAlmostEqual(classification["balanced_accuracy"], 1.0)

    def test_per_race_spearman_does_not_pool_races(self) -> None:
        correlation = mean_per_race_spearman(
            pd.Series([1.0, 2.0, 1.0, 2.0]),
            np.array([1.0, 2.0, 2.0, 1.0]),
            pd.Series([10, 10, 11, 11]),
        )
        self.assertAlmostEqual(correlation, 0.0)

    def test_calibration_reliability_reports_all_bins(self) -> None:
        bins = calibration_reliability(pd.Series([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9]), n_bins=2)
        self.assertEqual(bins["count"].tolist(), [2, 2])
        self.assertAlmostEqual(bins.loc[0, "mean_predicted_probability"], 0.15)
        self.assertAlmostEqual(bins.loc[0, "observed_positive_rate"], 0.0)
        self.assertAlmostEqual(bins.loc[1, "observed_positive_rate"], 1.0)

    def test_threshold_is_selected_on_an_inner_past_validation_season(self) -> None:
        frame = pd.DataFrame(
            {
                "season_year": [2021, 2021, 2022, 2022, 2023, 2023],
                "driver_recent_form": [2.0, 12.0, 3.0, 13.0, 4.0, 14.0],
                "finished_top10": [1, 0, 1, 0, 1, 0],
            }
        )
        candidate = candidate_factories("top10_model", "pre_qualifying", ["driver_recent_form"])[0]
        _, threshold_season = choose_classification_threshold(candidate, frame, "finished_top10", ["driver_recent_form"], 42)
        self.assertEqual(threshold_season, 2023)

    def test_baselines_follow_their_defined_behavior(self) -> None:
        X = pd.DataFrame({"grid_position": [1.0, np.nan, 6.0]})
        y = pd.Series([2.0, 4.0, 8.0])
        self.assertTrue(np.allclose(MedianRegressor().fit(X, y).predict(X), [4.0, 4.0, 4.0]))
        self.assertTrue(np.allclose(ZeroChangeRegressor().fit(X, y).predict(X), [0.0, 0.0, 0.0]))
        self.assertTrue(np.allclose(GridPositionRegressor().fit(X, y).predict(X), [1.0, 4.0, 6.0]))

    def test_artifact_schema_contains_required_manifest_and_prediction_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact_dir = Path(directory)
            manifest = {
                "experiment_id": "unit-test",
                "completed_at": "2026-06-20T00:00:00+00:00",
                "seed": 42,
                "train_seasons": [2021, 2022, 2023, 2024],
                "evaluation_season": 2025,
                "feature_columns": {"pre_qualifying": ["driver_recent_form"]},
                "data_fingerprints": {"pre_qualifying": {"sha256": "abc"}},
            }
            aggregate = pd.DataFrame(
                [{"context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "primary_metric": "mae", "primary_score": 4.0, "mae_std": 0.1, "champion": True}]
            )
            predictions = pd.DataFrame(
                [{"phase": "validation", "fold": "fold_1_2024", "context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "analysis_type": "candidate_model", "ablation": None, "race_id": 1, "driver_id": 2, "season_year": 2024, "actual": 3.0, "prediction": 4.0, "probability": np.nan, "threshold": np.nan}]
            )
            final = pd.DataFrame(
                [{"context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "mae": 4.0}]
            )
            write_experiment_artifacts(artifact_dir, manifest, pd.DataFrame(), aggregate, predictions, final)
            validate_artifact_schema(artifact_dir)
            self.assertEqual(json.loads((artifact_dir / "manifest.json").read_text(encoding="utf-8"))["experiment_id"], "unit-test")

    def test_headless_figures_are_generated_from_csv_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact_dir = Path(directory)
            manifest = {
                "experiment_id": "plot-test", "completed_at": "2026-06-20T00:00:00+00:00", "seed": 42,
                "train_seasons": [2021, 2022, 2023, 2024], "evaluation_season": 2025,
                "feature_columns": {"pre_qualifying": ["driver_recent_form"]},
                "data_fingerprints": {"pre_qualifying": {"sha256": "abc"}},
            }
            aggregate = pd.DataFrame([{"context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "primary_metric": "mae", "primary_score": 4.0, "mae_std": 0.1, "champion": True}])
            predictions = pd.DataFrame([
                {"phase": "validation", "fold": "fold_1", "context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "analysis_type": "candidate_model", "ablation": None, "race_id": 1, "driver_id": 1, "season_year": 2024, "actual": 2.0, "prediction": 3.0, "probability": np.nan, "threshold": np.nan},
                {"phase": "validation", "fold": "fold_1", "context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "analysis_type": "candidate_model", "ablation": None, "race_id": 1, "driver_id": 2, "season_year": 2024, "actual": 4.0, "prediction": 3.0, "probability": np.nan, "threshold": np.nan},
            ])
            ablation_aggregate = pd.DataFrame([{"context": "pre_qualifying", "task": "position_model", "ablation": "form_only", "algorithm": "MedianBaseline", "primary_metric": "mae", "primary_score": 4.5}])
            final = pd.DataFrame([{"context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "mae": 4.0}])
            write_experiment_artifacts(artifact_dir, manifest, pd.DataFrame(), aggregate, predictions, final, ablation_results=pd.DataFrame(), ablation_aggregate=ablation_aggregate, ablation_predictions=pd.DataFrame())
            generated = generate_thesis_figures(artifact_dir)
            self.assertTrue(generated)
            self.assertTrue(all(path.is_file() for path in generated))


if __name__ == "__main__":
    unittest.main()
