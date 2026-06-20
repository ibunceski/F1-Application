"""API tests for the read-only Model Lab artifact reader."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.routers.model_lab import get_model_lab_service, router  # noqa: E402
from app.services.model_lab_service import ModelLabService  # noqa: E402


def write_experiment(root: Path, experiment_id: str, completed_at: str, evaluation_season: int) -> None:
    directory = root / experiment_id
    directory.mkdir(parents=True)
    manifest = {
        "experiment_id": experiment_id,
        "status": "completed",
        "completed_at": completed_at,
        "contexts": ["pre_qualifying", "post_qualifying"],
        "evaluation_season": evaluation_season,
        "configuration": {"validation_strategy": "expanding_rolling_origin"},
        "feature_columns": {"pre_qualifying": ["driver_recent_form"]},
        "sample_counts": {"pre_qualifying": {"2024": 400}},
        "data_fingerprints": {"pre_qualifying": {"sha256": "test"}},
        "candidate_algorithms": {"pre_qualifying:position_model": ["MedianBaseline", "Ridge"]},
        "feature_ablations": {"pre_qualifying": {"form_only": ["driver_recent_form"]}},
    }
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    aggregate = pd.DataFrame(
        [
            {"context": "pre_qualifying", "task": "position_model", "algorithm": "MedianBaseline", "primary_metric": "mae", "primary_score": 4.2, "mae_mean": 4.2, "rank": 2, "champion": False},
            {"context": "pre_qualifying", "task": "position_model", "algorithm": "Ridge", "primary_metric": "mae", "primary_score": 3.8, "mae_mean": 3.8, "rank": 1, "champion": True},
        ]
    )
    aggregate.to_csv(directory / "aggregate_results.csv", index=False)
    results = pd.DataFrame(
        [
            {"phase": "validation", "fold": "fold_1_2024", "context": "pre_qualifying", "task": "position_model", "algorithm": "Ridge", "analysis_type": "candidate_model", "ablation": None, "evaluation_season": 2024, "mae": 3.7},
            {"phase": "final_holdout", "fold": f"holdout_{evaluation_season}", "context": "pre_qualifying", "task": "position_model", "algorithm": "Ridge", "analysis_type": "candidate_model", "ablation": None, "evaluation_season": evaluation_season, "mae": 3.9},
        ]
    )
    results.to_csv(directory / "model_results.csv", index=False)
    pd.DataFrame([{ "race_id": 1, "driver_id": 2, "actual": 3, "prediction": 4 }]).to_csv(directory / "out_of_fold_predictions.csv.gz", index=False, compression="gzip")
    ablation_dir = directory / "ablations"
    ablation_dir.mkdir()
    pd.DataFrame(
        [{"context": "pre_qualifying", "task": "position_model", "ablation": "form_only", "algorithm": "Ridge", "primary_metric": "mae", "primary_score": 4.1, "rank": 1, "ablation_champion": True, "best_ablation": True}]
    ).to_csv(ablation_dir / "aggregate_results.csv", index=False)
    figures = directory / "figures"
    figures.mkdir()
    (figures / "leaderboard_position_model.png").write_bytes(b"png")


class ModelLabApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        experiments = Path(self.temporary_directory.name) / "experiments"
        write_experiment(experiments, "older", "2026-01-01T10:00:00+00:00", 2024)
        write_experiment(experiments, "latest", "2026-02-01T10:00:00+00:00", 2025)
        malformed = experiments / "broken"
        malformed.mkdir()
        (malformed / "manifest.json").write_text("{bad json", encoding="utf-8")
        self.service = ModelLabService(experiments)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_model_lab_service] = lambda: self.service
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_lists_experiments_and_resolves_latest_successful(self) -> None:
        listed = self.client.get("/api/v1/model-lab/experiments")
        self.assertEqual(listed.status_code, 200)
        payload = listed.json()
        self.assertEqual(payload["latest_successful_experiment_id"], "latest")
        self.assertEqual({item["status"] for item in payload["experiments"]}, {"completed", "malformed"})

        overview = self.client.get("/api/v1/model-lab/overview")
        self.assertEqual(overview.status_code, 200)
        self.assertEqual(overview.json()["experiment_id"], "latest")
        self.assertTrue(overview.json()["resolved_latest"])
        self.assertEqual(overview.json()["champions"][0]["algorithm"], "Ridge")

    def test_filters_results_and_returns_ablation_and_artifact_metadata(self) -> None:
        results = self.client.get("/api/v1/model-lab/results", params={"experiment_id": "latest", "task": "position_model", "algorithm": "Ridge", "evaluation_season": 2025})
        self.assertEqual(results.status_code, 200)
        self.assertEqual(len(results.json()["rows"]), 1)
        self.assertEqual(results.json()["rows"][0]["phase"], "final_holdout")

        ablations = self.client.get("/api/v1/model-lab/ablations", params={"experiment_id": "latest"})
        self.assertEqual(ablations.status_code, 200)
        self.assertEqual(ablations.json()["leaderboard"][0]["ablation"], "form_only")

        artifacts = self.client.get("/api/v1/model-lab/artifacts", params={"experiment_id": "latest"})
        self.assertEqual(artifacts.status_code, 200)
        self.assertIn("figures/leaderboard_position_model.png", {item["relative_path"] for item in artifacts.json()["artifacts"]})

    def test_missing_and_malformed_artifacts_return_clear_errors(self) -> None:
        missing = self.client.get("/api/v1/model-lab/overview", params={"experiment_id": "does-not-exist"})
        self.assertEqual(missing.status_code, 404)
        malformed = self.client.get("/api/v1/model-lab/overview", params={"experiment_id": "broken"})
        self.assertEqual(malformed.status_code, 422)
        self.assertIn("malformed", malformed.json()["detail"].lower())


if __name__ == "__main__":
    unittest.main()
