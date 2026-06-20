"""Read-only Model Lab endpoints for persisted experiment evidence."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.schemas.model_lab import (
    AblationResultsResponse,
    ArtifactListResponse,
    ExperimentListResponse,
    ExperimentOverviewResponse,
    FeatureContext,
    FilteredResultsResponse,
    PredictionTask,
)
from app.services.model_lab_service import ModelLabService

router = APIRouter(prefix="/model-lab", tags=["Model Lab"])


def get_model_lab_service() -> ModelLabService:
    return ModelLabService()


@router.get("/experiments", response_model=ExperimentListResponse, summary="List persisted ML experiments")
def list_experiments(service: ModelLabService = Depends(get_model_lab_service)) -> ExperimentListResponse:
    """List completed and malformed experiment directories without loading or training models."""
    return service.list_experiments()


@router.get("/overview", response_model=ExperimentOverviewResponse, summary="Get experiment methodology and leaderboard")
def experiment_overview(
    experiment_id: Annotated[str | None, Query(description="Experiment ID. Omit to use the latest successful artifact.")] = None,
    service: ModelLabService = Depends(get_model_lab_service),
) -> ExperimentOverviewResponse:
    """Return stored configuration, data evidence, selected champions, and candidate leaderboard."""
    return service.overview(experiment_id)


@router.get("/results", response_model=FilteredResultsResponse, summary="Filter candidate-model fold results")
def experiment_results(
    experiment_id: Annotated[str | None, Query(description="Experiment ID. Omit to use the latest successful artifact.")] = None,
    task: Annotated[PredictionTask | None, Query(description="Optional target task filter.")] = None,
    context: Annotated[FeatureContext | None, Query(description="Optional feature-context filter.")] = None,
    algorithm: Annotated[str | None, Query(max_length=100, description="Optional model algorithm filter.")] = None,
    evaluation_season: Annotated[int | None, Query(ge=1950, le=2100, description="Optional final evaluation season filter.")] = None,
    service: ModelLabService = Depends(get_model_lab_service),
) -> FilteredResultsResponse:
    """Read candidate-model metrics from CSV artifacts; no fitting occurs."""
    return service.results(experiment_id, task, context, algorithm, evaluation_season)


@router.get("/ablations", response_model=AblationResultsResponse, summary="Get feature-ablation results")
def ablation_results(
    experiment_id: Annotated[str | None, Query(description="Experiment ID. Omit to use the latest successful artifact.")] = None,
    task: Annotated[PredictionTask | None, Query(description="Optional target task filter.")] = None,
    context: Annotated[FeatureContext | None, Query(description="Optional feature-context filter.")] = None,
    algorithm: Annotated[str | None, Query(max_length=100, description="Optional model algorithm filter.")] = None,
    service: ModelLabService = Depends(get_model_lab_service),
) -> AblationResultsResponse:
    """Read feature-ablation aggregate results stored beneath the selected experiment."""
    return service.ablations(experiment_id, task, context, algorithm)


@router.get("/artifacts", response_model=ArtifactListResponse, summary="List available experiment artifacts and figures")
def artifact_metadata(
    experiment_id: Annotated[str | None, Query(description="Experiment ID. Omit to use the latest successful artifact.")] = None,
    service: ModelLabService = Depends(get_model_lab_service),
) -> ArtifactListResponse:
    """Return safe relative-path metadata only; this endpoint does not serve or modify files."""
    return service.artifacts(experiment_id)
