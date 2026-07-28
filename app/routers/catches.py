from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.catch import CatchCreate, CatchRead, CatchUpdate
from app.services import catch_service

router = APIRouter(prefix="/catches", tags=["catches"])


@router.get("", response_model=list[CatchRead])
async def list_my_catches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CatchRead]:
    catches = await catch_service.list_catches_for_user(db, current_user.id)
    return [CatchRead.model_validate(catch) for catch in catches]


@router.post("", response_model=CatchRead, status_code=status.HTTP_201_CREATED)
async def create_catch(
    catch_in: CatchCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CatchRead:
    catch = await catch_service.create_catch(db, catch_in, user_id=current_user.id)
    return CatchRead.model_validate(catch)


@router.get("/{catch_id}", response_model=CatchRead)
async def get_catch(
    catch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CatchRead:
    catch = await catch_service.get_catch(db, catch_id)
    if catch is None or catch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catch not found")
    return CatchRead.model_validate(catch)


@router.patch("/{catch_id}", response_model=CatchRead)
async def update_catch(
    catch_id: int,
    catch_in: CatchUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CatchRead:
    catch = await catch_service.get_catch(db, catch_id)
    if catch is None or catch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catch not found")

    catch = await catch_service.update_catch(db, catch, catch_in)
    return CatchRead.model_validate(catch)


@router.delete("/{catch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_catch(
    catch_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    catch = await catch_service.get_catch(db, catch_id)
    if catch is None or catch.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catch not found")

    await catch_service.delete_catch(db, catch)
