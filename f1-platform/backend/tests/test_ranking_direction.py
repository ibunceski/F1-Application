import unittest

import numpy as np
import pandas as pd

from app.ml.ordinal_models import finishing_positions_to_relevance


class RankingDirectionTests(unittest.TestCase):
    def test_relevance_is_inverted_independently_for_each_race(self):
        positions = np.array([1.0, 5.0, 2.0, 1.0, 3.0])
        race_ids = np.array([101, 101, 101, 202, 202])

        relevance = finishing_positions_to_relevance(positions, race_ids)

        np.testing.assert_array_equal(relevance, np.array([5.0, 1.0, 4.0, 3.0, 1.0]))
        for race_id in np.unique(race_ids):
            in_race = race_ids == race_id
            best = np.argmin(positions[in_race])
            self.assertEqual(relevance[in_race][best], relevance[in_race].max())

    def test_higher_relevance_scores_assign_rank_one_to_the_best_finisher(self):
        positions = np.array([3.0, 1.0, 2.0, 4.0, 2.0, 1.0])
        race_ids = np.array([101, 101, 101, 101, 202, 202])
        relevance = finishing_positions_to_relevance(positions, race_ids)

        # Rankers are trained against relevance, whose convention is that a
        # higher output score means a better finish.  This is deliberately
        # dependency-free: it verifies the shared label/score contract rather
        # than requiring LightGBM or XGBoost in the unit-test environment.
        prediction_scores = relevance
        predicted_positions = (
            pd.DataFrame({"race_id": race_ids, "score": prediction_scores})
            .groupby("race_id", sort=False)["score"]
            .rank(method="first", ascending=False)
            .to_numpy(dtype=float)
        )

        self.assertTrue(np.all(predicted_positions[positions == 1.0] == 1.0))
        correlation = pd.Series(positions).corr(pd.Series(predicted_positions), method="spearman")
        self.assertGreater(correlation, 0.0)


if __name__ == "__main__":
    unittest.main()
