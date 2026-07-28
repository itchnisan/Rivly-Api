from datetime import date

from pydantic import BaseModel, ConfigDict


class SpeciesBase(BaseModel):
    name: str
    common_name: str
    legal_size_cm: float | None = None
    open_season_start: date | None = None
    open_season_end: date | None = None


class SpeciesCreate(SpeciesBase):
    pass


class SpeciesRead(SpeciesBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
