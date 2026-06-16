from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.prediction import (
    NextRacePredictionContextResponse,
    NextRacePredictionGenerateRequest,
    PredictionComparisonResponse,
    PredictionContext,
    PredictionResponse,
)
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


class PredictionGenerateRequest(BaseModel):
    force_regenerate: bool = False
    prediction_context: PredictionContext = "post_qualifying"


def get_prediction_service(db: AsyncSession = Depends(get_db)) -> PredictionService:
    return PredictionService(db)


PredictionComparisonContext = Literal["pre_qualifying", "post_qualifying", "latest"]


@router.get("/next-race/context", response_model=NextRacePredictionContextResponse)
async def get_next_race_prediction_context(
    service: PredictionService = Depends(get_prediction_service),
) -> NextRacePredictionContextResponse:
    return await service.get_next_race_context()


@router.post("/next-race/generate", response_model=list[PredictionResponse])
async def generate_next_race_predictions(
    request: NextRacePredictionGenerateRequest | None = None,
    service: PredictionService = Depends(get_prediction_service),
) -> list[PredictionResponse]:
    context = request.context if request is not None else "auto"
    force_regenerate = request.force_regenerate if request is not None else False
    return await service.generate_next_race_predictions(context, force_regenerate)


@router.get("/next-race", response_model=list[PredictionResponse])
async def get_next_race_predictions(
    service: PredictionService = Depends(get_prediction_service),
) -> list[PredictionResponse]:
    return await service.get_next_race_predictions()


@router.post("/races/{race_id}/generate", response_model=list[PredictionResponse])
async def generate_predictions(
    race_id: Annotated[int, Path(description="Race database identifier")],
    request: PredictionGenerateRequest | None = None,
    service: PredictionService = Depends(get_prediction_service),
) -> list[PredictionResponse]:
    force_regenerate = request.force_regenerate if request is not None else False
    prediction_context = request.prediction_context if request is not None else "post_qualifying"
    return await service.generate_predictions(race_id, force_regenerate, prediction_context)


@router.get("/races/{race_id}/comparison", response_model=PredictionComparisonResponse)
async def get_prediction_comparison(
    race_id: Annotated[int, Path(description="Race database identifier")],
    context: Annotated[PredictionComparisonContext, Query(description="Prediction context to compare")] = "latest",
    model_version: Annotated[str | None, Query(description="Optional model version filter")] = None,
    service: PredictionService = Depends(get_prediction_service),
) -> PredictionComparisonResponse:
    return await service.get_prediction_comparison(race_id, context, model_version)


@router.get("/races/{race_id}", response_model=list[PredictionResponse])
async def get_race_predictions(
    race_id: Annotated[int, Path(description="Race database identifier")],
    prediction_context: PredictionContext = "post_qualifying",
    service: PredictionService = Depends(get_prediction_service),
) -> list[PredictionResponse]:
    predictions = await service.get_existing_predictions(race_id, prediction_context)
    if not predictions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No predictions have been generated for this race",
        )
    return predictions


@router.get("/feature-importances")
async def get_feature_importances(service: PredictionService = Depends(get_prediction_service)) -> dict[str, Any]:
    return service.get_feature_importances()


@router.get("/model-info")
async def get_model_info(service: PredictionService = Depends(get_prediction_service)) -> dict[str, Any]:
    return service.get_model_metadata()
