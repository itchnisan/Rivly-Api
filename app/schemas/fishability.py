from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class FishabilityFactor(BaseModel):
    name: str
    label: str
    weight: int = Field(description="Poids du facteur dans le score, en points sur 100")
    score: float = Field(ge=0, le=1, description="Note du facteur, de 0 à 1")
    contribution: float = Field(description="Points effectivement apportés au score")
    detail: str


class FishabilityAdvisory(BaseModel):
    level: Literal["info", "warning", "blocking"]
    message: str


class FishabilityWeather(BaseModel):
    temperature_c: float
    pressure_hpa: float
    pressure_trend_hpa: float = Field(description="Variation de pression sur les 3 dernières heures")
    cloud_cover_pct: float
    wind_speed_kmh: float
    precipitation_mm: float
    sunrise: datetime
    sunset: datetime


class FishabilityRead(BaseModel):
    spot_id: int
    species_id: int | None = None
    at: datetime = Field(description="Heure pleine réellement évaluée, en UTC")
    score: float = Field(ge=0, le=10, description="Indice de pêchabilité sur 10, forcé à 0 hors saison")
    rating: Literal["poor", "fair", "good", "excellent"]
    factors: list[FishabilityFactor]
    advisories: list[FishabilityAdvisory]
    weather: FishabilityWeather


class FishabilityPoint(BaseModel):
    at: datetime
    score: float = Field(ge=0, le=10)
    rating: Literal["poor", "fair", "good", "excellent"]


class FishabilitySeriesRead(BaseModel):
    spot_id: int
    species_id: int | None = None
    points: list[FishabilityPoint]
