import unittest

import numpy as np
import pandas as pd

from app.ml.ordinal_models import LightGBMRankRegressor


class OrdinalRankingTests(unittest.TestCase):
    def test_lightgbm_rank_regressor_fits_with_group_and_predicts(self):
        X = pd.DataFrame({"form": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0]})
        y = pd.Series([1.0, 2.0, 3.0, 1.0, 2.0, 3.0])
        group = [3, 3]
        model = LightGBMRankRegressor(n_estimators=10, random_state=0)
        model.fit(X, y, group=group)
        preds = model.predict(X)
        self.assertEqual(preds.shape, (6,))
