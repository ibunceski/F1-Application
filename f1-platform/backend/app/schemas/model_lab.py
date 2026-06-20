"""OpenAPI response schemas for read-only ML experiment artifacts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ExperimentStatus = Literal["completed", "malformed"]
PredictionTask = Literal["position_model", "top10_model", "podium_model", "position_gain_model"]
FeatureContext = Literal["pre_qualifying", "post_qualifying"]


class ExperimentSummary(BaseModel):
    experiment_id: str = Field(description="Immutable experiment artifact directory name.")
    completed_at: datetime | None = Field(default=None, description="Completion timestamp recorded in the manifest.")
    contexts: list[FeatureContext] = Field(default_factory=list, description="Feature contexts present in the experiment.")
    evaluation_season: int | None = Field(default=None, description="Final completed held-out season.")
    status: ExperimentStatus = Field(description="Completed artifacts are safe to query; malformed artifacts are listed but cannot be opened.")
    message: str | None = Field(default=None, description="Validation detail for malformed artifacts.")


class ExperimentListResponse(BaseModel):
    experiments: list[ExperimentSummary]
    latest_successful_experiment_id: str | None = Field(default=None, description="Default experiment used when an endpoint omits experiment_id.")


class ChampionSummary(BaseModel):
    context: FeatureContext
    task: PredictionTask
    algorithm: str
    primary_metric: str
    primary_score: float | None
    rank: int | None = None
    metrics: dict[str, float | None] = Field(default_factory=dict, description="Aggregate validation metric means and standard deviations.")


class LeaderboardEntry(ChampionSummary):
    champion: bool = Field(description="Whether the entry won candidate-model validation selection for its context/task.")


class ExperimentOverviewResponse(BaseModel):
    experiment_id: str
    resolved_latest: bool = Field(description="True when experiment_id was omitted and the latest successful artifact was resolved.")
    methodology: dict[str, Any] = Field(description="Stored experiment configuration and methodological controls.")
    data_summary: dict[str, Any] = Field(description="Data fingerprints, sample counts, season-completeness evidence, and feature columns.")
    champions: list[ChampionSummary]
    leaderboard: list[LeaderboardEntry]


class ResultRow(BaseModel):
    phase: str
    fold: str
    context: FeatureContext
    task: PredictionTask
    algorithm: str
    analysis_type: Literal["candidate_model", "feature_ablation"]
    ablation: str | None = None
    evaluation_season: int | None = None
    threshold: float | None = None
    threshold_selection_season: int | None = None
    metrics: dict[str, float | int | None] = Field(default_factory=dict)


class FilteredResultsResponse(BaseModel):
    experiment_id: str
    resolved_latest: bool
    analysis_type: Literal["candidate_model", "feature_ablation"]
    rows: list[ResultRow]


class AblationLeaderboardEntry(BaseModel):
    context: FeatureContext
    task: PredictionTask
    ablation: str
    algorithm: str
    primary_metric: str
    primary_score: float | None
    rank: int | None = None
    ablation_champion: bool
    best_ablation: bool
    metrics: dict[str, float | None] = Field(default_factory=dict)


class AblationResultsResponse(BaseModel):
    experiment_id: str
    resolved_latest: bool
    feature_sets: dict[str, dict[str, list[str]]] = Field(description="Context-specific named feature lists evaluated by the ablation analysis.")
    leaderboard: list[AblationLeaderboardEntry]


class ArtifactMetadata(BaseModel):
    name: str
    relative_path: str
    category: Literal["manifest", "table", "report", "figure", "model", "other"]
    media_type: str
    size_bytes: int


class ArtifactListResponse(BaseModel):
    experiment_id: str
    resolved_latest: bool
    artifacts: list[ArtifactMetadata]
