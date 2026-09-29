"""Regression tests for development-only final champion parameter refits."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_pipeline import train_models  # noqa: E402


class FinalHyperparameterPersistenceTests(unittest.TestCase):
    def test_final_refit_and_metadata_keep_selected_non_default_parameters(self) -> None:
        features = ["driver_recent_form"]
        train = pd.DataFrame(
            {
                "race_id": [1, 1, 2, 2, 3, 3, 4, 4],
                "driver_id": list(range(1, 9)),
                "season_year": [2021] * 4 + [2022] * 4,
                "driver_recent_form": [1.0, 2.0, 10.0, 11.0, 1.5, 2.5, 10.5, 11.5],
                "actual_finishing_position": [1.0, 2.0, 10.0, 11.0, 1.0, 3.0, 9.0, 12.0],
                "finished_top10": [1, 1, 1, 0, 1, 1, 1, 0],
            }
        )
        holdout = pd.DataFrame(
            {
                "race_id": [10, 10, 11, 11],
                "driver_id": [11, 12, 13, 14],
                "season_year": [2025] * 4,
                "driver_recent_form": [1.2, 2.2, 9.8, 12.0],
                "actual_finishing_position": [1.0, 2.0, 9.0, 12.0],
                "finished_top10": [1, 1, 1, 0],
            }
        )
        ridge = next(candidate for candidate in train_models.candidate_factories("position_model", "pre_qualifying", features) if candidate.name == "Ridge")
        logistic = next(candidate for candidate in train_models.candidate_factories("top10_model", "pre_qualifying", features) if candidate.name == "LogisticRegression")

        ridge_result, _, ridge_model = train_models.evaluate_candidate(
            ridge, "position_model", "pre_qualifying", train, holdout, features, "holdout_2025", 42,
            "final_holdout", hyperparams={"alpha": 10.0},
            hyperparameter_selection_scope="full_development_expanding_inner_validation",
        )
        with patch("ml_pipeline.train_models.build_candidate_model", wraps=train_models.build_candidate_model) as build_model:
            logistic_result, _, logistic_model = train_models.evaluate_candidate(
                logistic, "top10_model", "pre_qualifying", train, holdout, features, "holdout_2025", 43,
                "final_holdout", hyperparams={"C": 0.1},
                hyperparameter_selection_scope="full_development_expanding_inner_validation",
            )

        self.assertEqual(ridge_result["hyperparameters"], {"alpha": 10.0})
        self.assertEqual(logistic_result["hyperparameters"], {"C": 0.1})
        self.assertEqual(ridge_model.named_steps["model"].alpha, 10.0)
        self.assertEqual(logistic_model.named_steps["model"].C, 0.1)
        # One construction chooses the F1 threshold and one fits the final
        # holdout model; neither may use the candidate factory defaults.
        self.assertGreaterEqual(build_model.call_count, 2)
        self.assertTrue(all(call.args[5] == {"C": 0.1} for call in build_model.call_args_list))

        aggregate = pd.DataFrame(
            [
                {"context": "pre_qualifying", "task": "position_model", "algorithm": "Ridge", "champion": True},
                {"context": "pre_qualifying", "task": "top10_model", "algorithm": "LogisticRegression", "champion": True},
            ]
        )
        manifest = {
            "completed_at": "2026-08-30T00:00:00+00:00",
            "experiment_id": "parameter-persistence-test",
            "train_seasons": [2021, 2022, 2023, 2024],
            "evaluation_season": 2025,
            "seed": 42,
            "data_fingerprints": {"pre_qualifying": {"sha256": "test"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "experiment").mkdir()
            train_models.promote_champions(
                root / "deployment",
                root / "experiment",
                {
                    ("pre_qualifying", "position_model"): (ridge_model, ridge_result),
                    ("pre_qualifying", "top10_model"): (logistic_model, logistic_result),
                },
                aggregate,
                {"pre_qualifying": features},
                manifest,
            )
            metadata = json.loads((root / "deployment" / "pre_qualifying_model_metadata.json").read_text(encoding="utf-8"))

        self.assertEqual(metadata["models"]["position_model"]["hyperparameters"], {"alpha": 10.0})
        self.assertEqual(metadata["models"]["top10_model"]["hyperparameters"], {"C": 0.1})


if __name__ == "__main__":
    unittest.main()
