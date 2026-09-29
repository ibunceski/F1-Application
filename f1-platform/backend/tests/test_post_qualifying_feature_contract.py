"""Contract tests for the single post-qualifying position predictor."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.prediction_service import POST_QUALIFYING_FEATURE_COLS as SERVING_FEATURES  # noqa: E402
from ml_pipeline.train_models import (  # noqa: E402
    POST_QUALIFYING_FEATURE_COLS as TRAINING_FEATURES,
    candidate_factories,
    feature_importances,
)
from ml_pipeline.preprocessing import build_pipeline  # noqa: E402


class PostQualifyingFeatureContractTests(unittest.TestCase):
    def test_grid_proxy_is_not_duplicated_in_active_feature_matrix(self) -> None:
        for feature_columns in (TRAINING_FEATURES, SERVING_FEATURES):
            self.assertIn("qualifying_position", feature_columns)
            self.assertNotIn("grid_position", feature_columns)
            self.assertEqual(len(feature_columns), len(set(feature_columns)))

    def test_post_qualifying_domain_baseline_uses_qualifying_position(self) -> None:
        candidates = candidate_factories("position_model", "post_qualifying", TRAINING_FEATURES)
        names = {candidate.name for candidate in candidates}
        self.assertIn("QualifyingPositionBaseline", names)
        self.assertNotIn("GridPositionBaseline", names)

    def test_importance_labels_follow_retained_preprocessor_columns(self) -> None:
        columns = ["first", "all_missing", "last"]
        frame = pd.DataFrame({"first": [1.0, 2.0, 3.0], "all_missing": [np.nan] * 3, "last": [3.0, 2.0, 1.0]})
        model = build_pipeline(Ridge(alpha=1.0), columns).fit(frame, pd.Series([1.0, 2.0, 3.0]))

        importances = feature_importances(model, columns)

        self.assertEqual(set(importances), {"first", "last"})
        self.assertNotIn("all_missing", importances)


if __name__ == "__main__":
    unittest.main()
