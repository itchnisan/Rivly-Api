from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.species import Species


async def get_species(db: AsyncSession, species_id: int) -> Species | None:
    return await db.get(Species, species_id)


async def list_species(db: AsyncSession) -> list[Species]:
    result = await db.execute(select(Species))
    return list(result.scalars().all())
