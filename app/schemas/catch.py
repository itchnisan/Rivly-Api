from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CatchBase(BaseModel):
    spot_id: int
    species_id: int
    weight_g: int | None = None
    length_cm: float | None = None
    caught_at: datetime
    conditions: dict | None = None
    photo_url: str | None = None
    notes: str | None = None


class CatchCreate(CatchBase):
    pass


class CatchUpdate(BaseModel):
    spot_id: int | None = None
    species_id: int | None = None
    weight_g: int | None = None
    length_cm: float | None = None
    caught_at: datetime | None = None
    conditions: dict | None = None
    photo_url: str | None = None
    notes: str | None = None


class CatchRead(CatchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
