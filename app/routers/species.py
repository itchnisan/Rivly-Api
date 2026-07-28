from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.species import SpeciesRead
from app.services import species_service

router = APIRouter(prefix="/species", tags=["species"])


@router.get("", response_model=list[SpeciesRead])
async def list_species(db: AsyncSession = Depends(get_db)) -> list[SpeciesRead]:
    species = await species_service.list_species(db)
    return [SpeciesRead.model_validate(s) for s in species]


@router.get("/{species_id}", response_model=SpeciesRead)
async def get_species(species_id: int, db: AsyncSession = Depends(get_db)) -> SpeciesRead:
    species = await species_service.get_species(db, species_id)
    if species is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Species not found")
    return SpeciesRead.model_validate(species)
