from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.analysis import DriverComparisonResponse, DriverLapSummary, DriverTyreStrategy
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["Analysis"])


def get_analysis_service(db: AsyncSession = Depends(get_db)) -> AnalysisService:
    return AnalysisService(db)


async def ensure_race_exists(race_id: int, service: AnalysisService) -> None:
    if not await service.race_exists(race_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race not found")


def ensure_lap_data(data: list[Any]) -> None:
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No lap data exists for this race. Run lap ingestion before using analysis endpoints.",
        )


@router.get("/races/{race_id}/laps")
async def get_lap_times(
    race_id: Annotated[int, Path(description="Race database identifier")],
    driver_id: Annotated[int | None, Query(description="Optional driver database identifier")] = None,
    exclude_pit_laps: Annotated[bool, Query(description="Exclude pit-in and pit-out laps")] = True,
    service: AnalysisService = Depends(get_analysis_service),
) -> list[dict[str, Any]]:
    await ensure_race_exists(race_id, service)
    data = await service.get_lap_times(race_id, driver_id, exclude_pit_laps)
    ensure_lap_data(data)
    return data


@router.get("/races/{race_id}/lap-summary", response_model=DriverLapSummary)
async def get_lap_summary(
    race_id: Annotated[int, Path(description="Race database identifier")],
    driver_id: Annotated[int, Query(description="Driver database identifier")],
    service: AnalysisService = Depends(get_analysis_service),
) -> DriverLapSummary:
    await ensure_race_exists(race_id, service)
    data = await service.get_lap_times(race_id, driver_id)
    ensure_lap_data(data)
    return await service.get_driver_lap_summary(race_id, driver_id)


@router.get("/races/{race_id}/tyre-strategy", response_model=list[DriverTyreStrategy])
async def get_tyre_strategy(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: AnalysisService = Depends(get_analysis_service),
) -> list[DriverTyreStrategy]:
    await ensure_race_exists(race_id, service)
    strategies = await service.get_tyre_strategy(race_id)
    ensure_lap_data(strategies)
    return strategies


@router.get("/races/{race_id}/position-changes")
async def get_position_changes(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: AnalysisService = Depends(get_analysis_service),
) -> list[dict[str, Any]]:
    await ensure_race_exists(race_id, service)
    return await service.get_position_changes(race_id)


@router.get("/races/{race_id}/compare", response_model=DriverComparisonResponse)
async def compare_drivers(
    race_id: Annotated[int, Path(description="Race database identifier")],
    driver1_id: Annotated[int, Query(description="First driver database identifier")],
    driver2_id: Annotated[int, Query(description="Second driver database identifier")],
    service: AnalysisService = Depends(get_analysis_service),
) -> DriverComparisonResponse:
    await ensure_race_exists(race_id, service)
    if driver1_id == driver2_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver1_id and driver2_id must be different")
    if not await service.driver_raced(race_id, driver1_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver1_id did not race in this race")
    if not await service.driver_raced(race_id, driver2_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="driver2_id did not race in this race")
    ensure_lap_data(await service.get_lap_times(race_id))
    return await service.get_driver_comparison(race_id, driver1_id, driver2_id)


@router.get("/races/{race_id}/fastest-laps")
async def get_fastest_laps(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: AnalysisService = Depends(get_analysis_service),
) -> list[dict[str, Any]]:
    await ensure_race_exists(race_id, service)
    data = await service.get_fastest_laps(race_id)
    ensure_lap_data(data)
    return data


@router.get("/races/{race_id}/weather")
async def get_weather_summary(
    race_id: Annotated[int, Path(description="Race database identifier")],
    service: AnalysisService = Depends(get_analysis_service),
) -> dict[str, Any]:
    await ensure_race_exists(race_id, service)
    return await service.get_race_weather_summary(race_id)
