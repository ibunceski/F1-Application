from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.driver import DriverResponse
from app.services.driver_service import DriverService

router = APIRouter(prefix="/drivers", tags=["Drivers"])


def get_driver_service(db: AsyncSession = Depends(get_db)) -> DriverService:
    return DriverService(db)


@router.get("", response_model=list[DriverResponse])
async def get_drivers(
    season: Annotated[int | None, Query(description="Optional season year filter")] = None,
    service: DriverService = Depends(get_driver_service),
) -> list[DriverResponse]:
    drivers = await service.get_drivers_by_season(season) if season is not None else await service.get_all_drivers()
    return [DriverResponse.model_validate(driver) for driver in drivers]


@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(
    driver_id: Annotated[int, Path(description="Driver database identifier")],
    service: DriverService = Depends(get_driver_service),
) -> DriverResponse:
    driver = await service.get_driver_by_id(driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    return DriverResponse.model_validate(driver)


@router.get("/{driver_id}/stats")
async def get_driver_stats(
    driver_id: Annotated[int, Path(description="Driver database identifier")],
    season: Annotated[int, Query(description="Season year for driver statistics")],
    service: DriverService = Depends(get_driver_service),
) -> dict[str, Any]:
    driver = await service.get_driver_by_id(driver_id)
    if driver is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Driver not found")
    return await service.get_driver_season_stats(driver_id, season)
