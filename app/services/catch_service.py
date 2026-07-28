from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catch import Catch
from app.schemas.catch import CatchCreate, CatchUpdate


async def get_catch(db: AsyncSession, catch_id: int) -> Catch | None:
    return await db.get(Catch, catch_id)


async def list_catches_for_user(db: AsyncSession, user_id: int) -> list[Catch]:
    result = await db.execute(select(Catch).where(Catch.user_id == user_id))
    return list(result.scalars().all())


async def create_catch(db: AsyncSession, catch_in: CatchCreate, user_id: int) -> Catch:
    catch = Catch(**catch_in.model_dump(), user_id=user_id)
    db.add(catch)
    await db.commit()
    await db.refresh(catch)
    return catch


async def update_catch(db: AsyncSession, catch: Catch, catch_in: CatchUpdate) -> Catch:
    for field, value in catch_in.model_dump(exclude_unset=True).items():
        setattr(catch, field, value)
    await db.commit()
    await db.refresh(catch)
    return catch


async def delete_catch(db: AsyncSession, catch: Catch) -> None:
    await db.delete(catch)
    await db.commit()
