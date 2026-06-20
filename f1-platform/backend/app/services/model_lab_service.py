"""Read-only access to persisted ML experiment artifacts."""

from __future__ import annotations

import json
import math
import mimetypes
import numbers
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException, status
from pydantic import ValidationError

from app.config import settings
from app.schemas.model_lab import (
    AblationLeaderboardEntry,
    AblationResultsResponse,
    ArtifactListResponse,
    ArtifactMetadata,
    ChampionSummary,
    ExperimentListResponse,
    ExperimentOverviewResponse,
    ExperimentSummary,
    FilteredResultsResponse,
    LeaderboardEntry,
    ResultRow,
)

REQUIRED_MANIFEST_KEYS = {"experiment_id", "completed_at", "contexts", "evaluation_season", "configuration"}
REQUIRED_SUCCESS_FILES = {"manifest.json", "aggregate_results.csv", "model_results.csv", "out_of_fold_predictions.csv.gz"}
RESULT_RESERVED_COLUMNS = {
    "phase", "fold", "context", "task", "algorithm", "analysis_type", "ablation", "evaluation_season",
    "threshold", "threshold_selection_season", "threshold_selection_scope", "train_rows", "validation_rows",
}


def _json_safe_value(value: Any) -> Any:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        return float(value)
    if isinstance(value, (str, bool)):
        return value
    return str(value)


def _as_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


class ModelLabService:
    """Filesystem-only experiment reader; it never loads or trains model objects."""

    def __init__(self, experiments_root: Path | None = None) -> None:
        models_root = Path(settings.MODELS_STORE_PATH)
        self.experiments_root = (experiments_root or models_root / "experiments").resolve()

    def _validate_experiment_id(self, experiment_id: str) -> str:
        if not experiment_id or Path(experiment_id).name != experiment_id or experiment_id in {".", ".."}:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="experiment_id must be a single artifact directory name")
        return experiment_id

    def _experiment_dir(self, experiment_id: str) -> Path:
        identifier = self._validate_experiment_id(experiment_id)
        path = self.experiments_root / identifier
        if not path.is_dir():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experiment artifact not found")
        if not path.resolve().is_relative_to(self.experiments_root):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="experiment_id resolves outside the artifact store")
        return path

    @staticmethod
    def _read_manifest(experiment_dir: Path) -> dict[str, Any]:
        path = experiment_dir / "manifest.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValueError("manifest.json is missing") from exc
        except json.JSONDecodeError as exc:
            raise ValueError("manifest.json is not valid JSON") from exc
        if not isinstance(value, dict):
            raise ValueError("manifest.json must contain an object")
        missing = REQUIRED_MANIFEST_KEYS - set(value)
        if missing:
            raise ValueError(f"manifest.json is missing required keys: {', '.join(sorted(missing))}")
        return value

    @classmethod
    def _successful_manifest(cls, experiment_dir: Path) -> dict[str, Any]:
        manifest = cls._read_manifest(experiment_dir)
        missing_files = sorted(name for name in REQUIRED_SUCCESS_FILES if not (experiment_dir / name).is_file())
        if missing_files:
            raise ValueError(f"successful artifact is missing: {', '.join(missing_files)}")
        if not (experiment_dir / "champions").is_dir() or not any((experiment_dir / "champions").glob("*.joblib")):
            raise ValueError("successful artifact has no promoted champion models")
        if manifest.get("status") not in {None, "completed"}:
            raise ValueError("manifest status is not completed")
        contexts = manifest.get("contexts")
        if not isinstance(contexts, list) or not set(contexts).issubset({"pre_qualifying", "post_qualifying"}):
            raise ValueError("manifest contexts are invalid")
        if not isinstance(manifest.get("evaluation_season"), int):
            raise ValueError("manifest evaluation_season is invalid")
        return manifest

    @staticmethod
    def _completed_at(manifest: dict[str, Any]) -> datetime | None:
        try:
            return datetime.fromisoformat(str(manifest["completed_at"]).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None

    def list_experiments(self) -> ExperimentListResponse:
        summaries: list[ExperimentSummary] = []
        if not self.experiments_root.is_dir():
            return ExperimentListResponse(experiments=[], latest_successful_experiment_id=None)
        for experiment_dir in sorted((path for path in self.experiments_root.iterdir() if path.is_dir()), key=lambda path: path.name):
            try:
                if not experiment_dir.resolve().is_relative_to(self.experiments_root):
                    raise ValueError("artifact directory resolves outside the experiment store")
                manifest = self._successful_manifest(experiment_dir)
                summaries.append(ExperimentSummary(
                    experiment_id=experiment_dir.name,
                    completed_at=self._completed_at(manifest),
                    contexts=manifest.get("contexts", []),
                    evaluation_season=manifest.get("evaluation_season"),
                    status="completed",
                ))
            except (ValueError, ValidationError) as exc:
                summaries.append(ExperimentSummary(experiment_id=experiment_dir.name, status="malformed", message=str(exc)))
        successful = [summary for summary in summaries if summary.status == "completed"]
        timestamp = lambda summary: summary.completed_at.timestamp() if summary.completed_at is not None else float("-inf")
        latest = max(successful, key=lambda summary: (timestamp(summary), summary.experiment_id), default=None)
        summaries.sort(key=lambda summary: (timestamp(summary), summary.experiment_id), reverse=True)
        return ExperimentListResponse(experiments=summaries, latest_successful_experiment_id=latest.experiment_id if latest else None)

    def _resolve(self, experiment_id: str | None) -> tuple[Path, dict[str, Any], bool]:
        resolved_latest = experiment_id is None
        if resolved_latest:
            latest = self.list_experiments().latest_successful_experiment_id
            if latest is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No successful experiment artifacts are available")
            experiment_id = latest
        experiment_dir = self._experiment_dir(experiment_id)
        try:
            manifest = self._successful_manifest(experiment_dir)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Experiment artifact is malformed: {exc}") from exc
        return experiment_dir, manifest, resolved_latest

    @staticmethod
    def _read_csv(path: Path) -> pd.DataFrame:
        try:
            return pd.read_csv(path)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Experiment artifact is missing: {path.name}") from exc
        except (pd.errors.EmptyDataError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"Experiment artifact is malformed: {path.name}") from exc

    @staticmethod
    def _metric_map(row: pd.Series, reserved: set[str] | None = None) -> dict[str, float | None]:
        reserved = reserved or set()
        values: dict[str, float | None] = {}
        for key, value in row.items():
            if key in reserved or key.endswith("_count"):
                continue
            safe = _json_safe_value(value)
            if isinstance(safe, (int, float)) or safe is None:
                values[str(key)] = float(safe) if isinstance(safe, int) else safe
        return values

    def overview(self, experiment_id: str | None) -> ExperimentOverviewResponse:
        experiment_dir, manifest, resolved_latest = self._resolve(experiment_id)
        aggregate = self._read_csv(experiment_dir / "aggregate_results.csv")
        required = {"context", "task", "algorithm", "primary_metric", "primary_score", "champion"}
        if not required.issubset(aggregate.columns):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Experiment artifact is malformed: aggregate_results.csv schema")
        leaderboard = [
            LeaderboardEntry(
                context=row["context"], task=row["task"], algorithm=row["algorithm"], primary_metric=row["primary_metric"],
                primary_score=_json_safe_value(row["primary_score"]), rank=int(row["rank"]) if pd.notna(row.get("rank")) else None,
                champion=_as_bool(row["champion"]), metrics=self._metric_map(row, {"context", "task", "algorithm", "primary_metric", "primary_score", "rank", "champion", "analysis_type"}),
            )
            for _, row in aggregate.iterrows()
        ]
        champions = [ChampionSummary(**entry.model_dump(exclude={"champion"})) for entry in leaderboard if entry.champion]
        methodology = {
            "configuration": manifest.get("configuration", {}),
            "candidate_algorithms": manifest.get("candidate_algorithms", {}),
            "weather_policy": manifest.get("weather_policy"),
            "seed": manifest.get("seed"),
            "train_seasons": manifest.get("train_seasons", []),
            "evaluation_season": manifest.get("evaluation_season"),
            "contexts": manifest.get("contexts", []),
        }
        data_summary = {key: manifest.get(key, {}) for key in ("feature_columns", "sample_counts", "data_fingerprints", "season_completeness", "folds")}
        return ExperimentOverviewResponse(experiment_id=experiment_dir.name, resolved_latest=resolved_latest, methodology=methodology, data_summary=data_summary, champions=champions, leaderboard=leaderboard)

    def results(self, experiment_id: str | None, task: str | None, context: str | None, algorithm: str | None, evaluation_season: int | None) -> FilteredResultsResponse:
        experiment_dir, manifest, resolved_latest = self._resolve(experiment_id)
        results = self._read_csv(experiment_dir / "model_results.csv")
        required = {"phase", "fold", "context", "task", "algorithm", "analysis_type"}
        if not required.issubset(results.columns):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Experiment artifact is malformed: model_results.csv schema")
        for column, value in (("task", task), ("context", context), ("algorithm", algorithm)):
            if value is not None:
                results = results[results[column] == value]
        if evaluation_season is not None:
            if "evaluation_season" in results.columns:
                results = results[results["evaluation_season"] == evaluation_season]
            else:
                results = results[results["phase"].eq("final_holdout")] if evaluation_season == manifest["evaluation_season"] else results.iloc[0:0]
        rows = [
            ResultRow(
                phase=row["phase"], fold=row["fold"], context=row["context"], task=row["task"], algorithm=row["algorithm"],
                analysis_type=row["analysis_type"], ablation=_json_safe_value(row.get("ablation")),
                evaluation_season=int(row["evaluation_season"]) if pd.notna(row.get("evaluation_season")) else None,
                threshold=_json_safe_value(row.get("threshold")),
                threshold_selection_season=int(row["threshold_selection_season"]) if pd.notna(row.get("threshold_selection_season")) else None,
                metrics=self._metric_map(row, RESULT_RESERVED_COLUMNS),
            )
            for _, row in results.iterrows()
        ]
        return FilteredResultsResponse(experiment_id=experiment_dir.name, resolved_latest=resolved_latest, analysis_type="candidate_model", rows=rows)

    def ablations(self, experiment_id: str | None, task: str | None, context: str | None, algorithm: str | None) -> AblationResultsResponse:
        experiment_dir, manifest, resolved_latest = self._resolve(experiment_id)
        aggregate = self._read_csv(experiment_dir / "ablations" / "aggregate_results.csv")
        required = {"context", "task", "ablation", "algorithm", "primary_metric", "primary_score", "ablation_champion", "best_ablation"}
        if not required.issubset(aggregate.columns):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Experiment artifact is malformed: ablation aggregate schema")
        for column, value in (("task", task), ("context", context), ("algorithm", algorithm)):
            if value is not None:
                aggregate = aggregate[aggregate[column] == value]
        leaderboard = [
            AblationLeaderboardEntry(
                context=row["context"], task=row["task"], ablation=row["ablation"], algorithm=row["algorithm"],
                primary_metric=row["primary_metric"], primary_score=_json_safe_value(row["primary_score"]),
                rank=int(row["rank"]) if pd.notna(row.get("rank")) else None,
                ablation_champion=_as_bool(row["ablation_champion"]), best_ablation=_as_bool(row["best_ablation"]),
                metrics=self._metric_map(row, {"context", "task", "ablation", "algorithm", "primary_metric", "primary_score", "rank", "ablation_champion", "best_ablation", "analysis_type"}),
            )
            for _, row in aggregate.iterrows()
        ]
        return AblationResultsResponse(experiment_id=experiment_dir.name, resolved_latest=resolved_latest, feature_sets=manifest.get("feature_ablations", {}), leaderboard=leaderboard)

    def artifacts(self, experiment_id: str | None) -> ArtifactListResponse:
        experiment_dir, _, resolved_latest = self._resolve(experiment_id)
        items: list[ArtifactMetadata] = []
        for path in sorted((item for item in experiment_dir.rglob("*") if item.is_file()), key=lambda item: item.as_posix()):
            relative = path.relative_to(experiment_dir).as_posix()
            if relative == "manifest.json":
                category = "manifest"
            elif relative.startswith("figures/"):
                category = "figure"
            elif path.suffix == ".joblib":
                category = "model"
            elif path.suffix in {".csv", ".gz"}:
                category = "table"
            elif path.suffix in {".md", ".txt"}:
                category = "report"
            else:
                category = "other"
            items.append(ArtifactMetadata(name=path.name, relative_path=relative, category=category, media_type=mimetypes.guess_type(path.name)[0] or "application/octet-stream", size_bytes=path.stat().st_size))
        return ArtifactListResponse(experiment_id=experiment_dir.name, resolved_latest=resolved_latest, artifacts=items)
