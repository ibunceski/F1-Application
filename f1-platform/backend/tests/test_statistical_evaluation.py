import unittest
import numpy as np
import pandas as pd

from ml_pipeline.statistical_evaluation import (
    per_race_metric,
    bootstrap_mean_of_per_race,
    cluster_bootstrap_pooled,
    pooled_mae,
    pooled_roc_auc,
    per_race_mae,
    per_race_brier,
    paired_metric_differences,
    paired_permutation_test,
    paired_bootstrap_ci,
)


def _preds():
    # race 1: perfect predictions; race 2: poor predictions
    return pd.DataFrame({
        "race_id": [1, 1, 1, 2, 2, 2],
        "actual": [1.0, 2.0, 3.0, 1.0, 2.0, 3.0],
        "prediction": [1.0, 2.0, 3.0, 3.0, 2.0, 1.0],
    })


class StatisticalEvaluationTests(unittest.TestCase):
    def test_per_race_metric_indexes_by_race(self):
        s = per_race_metric(_preds(), per_race_mae)
        self.assertEqual(sorted(s.index.tolist()), [1, 2])
        self.assertAlmostEqual(s.loc[1], 0.0)
        self.assertAlmostEqual(s.loc[2], (2.0 + 0.0 + 2.0) / 3.0)

    def test_bootstrap_mean_of_per_race_is_inside_ci(self):
        s = pd.Series([0.0, 4.0], index=[1, 2])
        ci = bootstrap_mean_of_per_race(s, n_boot=200, seed=1)
        self.assertLessEqual(ci["ci_low"], ci["mean"])
        self.assertLessEqual(ci["mean"], ci["ci_high"])
        self.assertAlmostEqual(ci["mean"], 2.0, places=0)

    def test_cluster_bootstrap_pooled_resamples_races(self):
        ci = cluster_bootstrap_pooled(_preds(), pooled_mae, n_boot=100, seed=1)
        self.assertGreater(ci["ci_high"], 0.0)
        self.assertLessEqual(ci["ci_low"], ci["mean"])
        self.assertLessEqual(ci["mean"], ci["ci_high"])

    def test_pooled_roc_auc_nan_on_single_class(self):
        one_class = pd.DataFrame({"race_id": [1, 1], "actual": [1, 1], "probability": [0.9, 0.8]})
        self.assertTrue(np.isnan(pooled_roc_auc(one_class)))

    def test_per_race_brier_uses_probabilities(self):
        self.assertAlmostEqual(per_race_brier(np.array([1, 0]), np.array([0.8, 0.2])), 0.04, places=4)

    def test_paired_differences_align_on_common_races(self):
        a = pd.Series([1.0, 2.0], index=[1, 2])
        b = pd.Series([2.0, 3.0], index=[2, 3])
        d = paired_metric_differences(a, b)
        self.assertEqual(sorted(d.index.tolist()), [2])
        self.assertAlmostEqual(d.loc[2], 0.0)

    def test_paired_permutation_test_detects_real_difference(self):
        diffs = pd.Series([-1.0] * 30)
        p = paired_permutation_test(diffs, n_perm=500, seed=42)
        self.assertLess(p, 0.05)

    def test_paired_bootstrap_ci_excludes_zero_for_clear_difference(self):
        diffs = pd.Series([-1.0] * 50)
        ci = paired_bootstrap_ci(diffs, n_boot=200, seed=42)
        self.assertLess(ci["ci_high"], 0.0)


if __name__ == "__main__":
    unittest.main()
