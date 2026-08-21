from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.spot import WaterType


class SpotBase(BaseModel):
    name: str
    description: str | None = None
    latitude: float
    longitude: float
    water_type: WaterType


class SpotCreate(SpotBase):
    pass


class SpotUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    water_type: WaterType | None = None


class SpotRead(SpotBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int
    created_at: datetime


class SpotLocationLookup(BaseModel):
    """Résultat d'une recherche de lieu, pour préparer la création d'un spot."""

    latitude: float
    longitude: float
    label: str | None = None
    available_water_types: list[WaterType]
