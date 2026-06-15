from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.prediction import PredictionResponse
from app.services.prediction_service import PredictionService

router = APIRouter(prefix="/predictions", tags=["Predictions"])


class PredictionGenerateRequest(BaseModel):
    force_regenerate: bool = False


def get_prediction_service(db: AsyncSession = Depends(get_db)) -> PredictionService:
    return PredictionService(db)


@router.post("/races/{race_id}/generate", response_model=list[PredictionResponse])
async def generate_predictions(
    race_id: Annotated[int, Path(description="Race database identifier")],
    request: PredictionGenerateRequest | None = None,
    service: PredictionService = Depends(get_prediction_service),
) -> list[PredictionResponse]:
    force_regenerate = request.force_regenerate if request is not None else False
    return await service.generate_predictions(race_id, force_regenerate)


@router.get("/races/{race_id}", response_model=list[PredictionResponse])
async def get_race_predictions(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: PredictionService = Depends(get_prediction_service),
) -> list[PredictionResponse]:
    predictions = await service.get_existing_predictions(race_id)
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
