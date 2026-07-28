from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spot import Spot
from app.schemas.spot import SpotCreate, SpotUpdate


async def get_spot(db: AsyncSession, spot_id: int) -> Spot | None:
    return await db.get(Spot, spot_id)


async def list_spots(
    db: AsyncSession,
    min_lat: float | None = None,
    max_lat: float | None = None,
    min_lon: float | None = None,
    max_lon: float | None = None,
) -> list[Spot]:
    query = select(Spot)
    if min_lat is not None:
        query = query.where(Spot.latitude >= min_lat)
    if max_lat is not None:
        query = query.where(Spot.latitude <= max_lat)
    if min_lon is not None:
        query = query.where(Spot.longitude >= min_lon)
    if max_lon is not None:
        query = query.where(Spot.longitude <= max_lon)

    result = await db.execute(query)
    return list(result.scalars().all())


async def create_spot(db: AsyncSession, spot_in: SpotCreate, created_by: int) -> Spot:
    spot = Spot(**spot_in.model_dump(), created_by=created_by)
    db.add(spot)
    await db.commit()
    await db.refresh(spot)
    return spot


async def update_spot(db: AsyncSession, spot: Spot, spot_in: SpotUpdate) -> Spot:
    for field, value in spot_in.model_dump(exclude_unset=True).items():
        setattr(spot, field, value)
    await db.commit()
    await db.refresh(spot)
    return spot


async def delete_spot(db: AsyncSession, spot: Spot) -> None:
    await db.delete(spot)
    await db.commit()
