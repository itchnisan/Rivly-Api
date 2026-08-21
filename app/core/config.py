from functools import lru_cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    api_v1_prefix: str = "/api/v1"
    project_name: str = "Rivly API"
    cors_origins: list[str] = ["http://localhost:5173"]

    weather_api_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout_seconds: float = 8.0
    weather_cache_ttl_seconds: int = 3600

    overpass_api_url: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_seconds: float = 10.0
    overpass_cache_ttl_seconds: int = 86400

    geocoding_api_url: str = "https://api-adresse.data.gouv.fr/search/"
    geocoding_timeout_seconds: float = 8.0
    geocoding_cache_ttl_seconds: int = 86400


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
