from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ml_pipeline.thesis_visualizations import (  # noqa: E402
    build_context_lift_summary,
    generate_thesis_visualization_package,
)


def _aggregate() -> pd.DataFrame:
    rows = []
    for context in ("pre_qualifying", "post_qualifying"):
        for task, metric in {"position_model": "mae", "top10_model": "roc_auc", "podium_model": "pr_auc", "position_gain_model": "mae"}.items():
            champion = "Champion"
            baseline = "QualifyingPositionBaseline" if task == "position_model" and context == "post_qualifying" else {"position_model": "MedianBaseline", "top10_model": "PrevalenceBaseline", "podium_model": "PrevalenceBaseline", "position_gain_model": "ZeroChangeBaseline"}[task]
            rows.extend([
                {"context": context, "task": task, "algorithm": champion, "champion": True, "primary_score": 1.0 if metric == "mae" else 0.8, "primary_metric": metric, "mae_mean": 1.0, "roc_auc_mean": 0.8, "pr_auc_mean": 0.7, "spearman_mean": 0.6},
                {"context": context, "task": task, "algorithm": baseline, "champion": False, "primary_score": 2.0 if metric == "mae" else 0.5, "primary_metric": metric, "mae_mean": 2.0, "roc_auc_mean": 0.5, "pr_auc_mean": 0.3, "spearman_mean": 0.0},
            ])
    return pd.DataFrame(rows)


def _predictions() -> pd.DataFrame:
    rows = []
    for phase, season in (("validation", 2024), ("final_holdout", 2025)):
        for task in ("position_model", "top10_model", "podium_model", "position_gain_model"):
            for context in ("pre_qualifying", "post_qualifying"):
                # The post context deliberately has one fewer row; the common
                # subset test confirms it never compares the extra pre row.
                count = 2 if context == "pre_qualifying" else 1
                for driver_id in range(1, count + 1):
                    classification = task in {"top10_model", "podium_model"}
                    actual = int(driver_id == 1) if classification else float(driver_id)
                    rows.append({"phase": phase, "fold": phase, "context": context, "task": task, "algorithm": "Champion", "analysis_type": "candidate_model", "race_id": 10, "driver_id": driver_id, "season_year": season, "actual": actual, "prediction": float(driver_id) + (0.0 if context == "post_qualifying" else 0.5), "probability": 0.9 if driver_id == 1 else 0.1})
    return pd.DataFrame(rows)


class ThesisVisualizationTests(unittest.TestCase):
    def test_context_lift_uses_exact_common_driver_race_rows_and_keeps_phases_separate(self) -> None:
        summary = build_context_lift_summary(_predictions(), _aggregate())
        self.assertEqual(set(summary["phase"]), {"validation", "final_holdout"})
        self.assertTrue((summary["common_driver_race_rows"] == 1).all())
        self.assertEqual(len(summary), 8)

    def test_package_exports_standardized_phase_scoped_outputs_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ablations").mkdir()
            (root / "champions").mkdir()
            (root / "manifest.json").write_text(json.dumps({"experiment_id": "synthetic"}), encoding="utf-8")
            _aggregate().to_csv(root / "aggregate_results.csv", index=False)
            _aggregate().assign(phase="validation").to_csv(root / "model_results.csv", index=False)
            _aggregate()[_aggregate()["champion"]].assign(mae=1.0, roc_auc=0.8, pr_auc=0.7).to_csv(root / "final_holdout_results.csv", index=False)
            _predictions().to_csv(root / "out_of_fold_predictions.csv.gz", index=False, compression="gzip")
            pd.DataFrame(columns=["phase", "context", "task", "count", "mean_predicted_probability", "observed_positive_rate"]).to_csv(root / "reliability_bins.csv", index=False)
            pd.DataFrame([{"context": "pre_qualifying", "task": "position_model", "ablation": "form_only", "primary_score": 2.0}]).to_csv(root / "ablations" / "aggregate_results.csv", index=False)
            (root / "champions" / "pre_qualifying_feature_importances.json").write_text(json.dumps({"position_model": {"driver_recent_form": 0.7}}), encoding="utf-8")
            paths = generate_thesis_visualization_package(root)
            figures = root / "reports" / "thesis_figures"
            self.assertTrue(paths)
            self.assertTrue(all(path.suffix in {".png", ".svg"} and path.name.startswith("fig_") for path in paths))
            self.assertTrue((figures / "fig_leaderboard_position_model_validation.png").is_file())
            self.assertTrue((figures / "fig_leaderboard_position_model_final_holdout.svg").is_file())
            self.assertTrue((figures / "champion_vs_baseline_summary.csv").is_file())
            self.assertTrue((figures / "champion_vs_baseline_summary.md").is_file())
            manifest = json.loads((figures / "figure_manifest.json").read_text(encoding="utf-8"))
            self.assertIn("phase_separation", manifest)


if __name__ == "__main__":
    unittest.main()
