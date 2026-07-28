from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.spot import SpotCreate, SpotRead, SpotUpdate
from app.services import spot_service

router = APIRouter(prefix="/spots", tags=["spots"])


@router.get("", response_model=list[SpotRead])
async def list_spots(
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[SpotRead]:
    spots = await spot_service.list_spots(db, min_lat, max_lat, min_lon, max_lon)
    return [SpotRead.model_validate(spot) for spot in spots]


@router.post("", response_model=SpotRead, status_code=status.HTTP_201_CREATED)
async def create_spot(
    spot_in: SpotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpotRead:
    spot = await spot_service.create_spot(db, spot_in, created_by=current_user.id)
    return SpotRead.model_validate(spot)


@router.get("/{spot_id}", response_model=SpotRead)
async def get_spot(spot_id: int, db: AsyncSession = Depends(get_db)) -> SpotRead:
    spot = await spot_service.get_spot(db, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    return SpotRead.model_validate(spot)


@router.patch("/{spot_id}", response_model=SpotRead)
async def update_spot(
    spot_id: int,
    spot_in: SpotUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SpotRead:
    spot = await spot_service.get_spot(db, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    if spot.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to edit this spot")

    spot = await spot_service.update_spot(db, spot, spot_in)
    return SpotRead.model_validate(spot)


@router.delete("/{spot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_spot(
    spot_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    spot = await spot_service.get_spot(db, spot_id)
    if spot is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Spot not found")
    if spot.created_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to delete this spot")

    await spot_service.delete_spot(db, spot)
