import unittest

import numpy as np
import pandas as pd

from app.ml.ordinal_models import LightGBMRankRegressor, OrdinalRidgeRegressor


class OrdinalRankingTests(unittest.TestCase):
    def test_lightgbm_rank_regressor_fits_with_group_and_predicts(self):
        X = pd.DataFrame({"form": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]})
        y = pd.Series([1.0, 2.0, 3.0, 1.0, 2.0, 3.0])
        group = [3, 3]
        model = LightGBMRankRegressor(n_estimators=10, random_state=0)
        model.fit(X, y, group=group)
        preds = model.predict(X)
        self.assertEqual(preds.shape, (6,))

    def test_ordinal_ridge_regressor_maps_gapped_positions(self):
        X = pd.DataFrame({"form": np.arange(12, dtype=float)})
        y = np.array([1, 1, 2, 2, 3, 3, 5, 5, 7, 7, 10, 10], dtype=float)
        model = OrdinalRidgeRegressor(alpha=1.0)
        model.fit(X, y)
        preds = model.predict(X)
        self.assertEqual(preds.shape, (12,))
        self.assertTrue(np.all(np.isfinite(preds)))
