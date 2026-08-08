"""Accès aux conditions météo utilisées par l'indice de pêchabilité.

La source est Open-Meteo (gratuite, sans clé d'API). Les prévisions ne changent
qu'une fois par heure : un cache mémoire évite de rappeler l'API à chaque
requête sur un même secteur.
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

settings = get_settings()

HOURLY_FIELDS = (
    "temperature_2m",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "precipitation",
)

# Écart utilisé pour mesurer la tendance barométrique.
PRESSURE_TREND_HOURS = 3

# Fenêtre demandée à Open-Meteo : la veille (pour la tendance en début de
# fenêtre et les requêtes sur le passé proche) et la semaine à venir.
PAST_DAYS = 1
FORECAST_DAYS = 7

# Précision de la clé de cache, en degrés (~1 km).
CACHE_COORD_PRECISION = 2


class WeatherUnavailable(Exception):
    """La source météo n'a pas pu être jointe ou a renvoyé une réponse inexploitable."""


class ForecastOutOfRange(Exception):
    """La date demandée sort de la fenêtre de prévision disponible."""


@dataclass(frozen=True)
class WeatherSnapshot:
    """Conditions à un instant donné, sur un point donné."""

    at: datetime
    temperature_c: float
    pressure_hpa: float
    pressure_trend_hpa: float
    cloud_cover_pct: float
    wind_speed_kmh: float
    precipitation_mm: float
    sunrise: datetime
    sunset: datetime


class WeatherProvider(Protocol):
    async def get_snapshot(
        self, latitude: float, longitude: float, at: datetime
    ) -> WeatherSnapshot: ...


def _parse_api_datetime(raw: str) -> datetime:
    """Open-Meteo renvoie des horodatages ISO sans fuseau, en UTC (`timezone=UTC`)."""
    return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)


class OpenMeteoProvider:
    """Client Open-Meteo avec cache mémoire à durée de vie limitée.

    Le cache est propre au processus : plusieurs workers gardent chacun le leur,
    et deux requêtes simultanées sur un secteur froid déclenchent deux appels.
    C'est sans conséquence (l'appel est idempotent) et suffisant à cette échelle.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._cache: dict[tuple[float, float], tuple[float, dict[str, Any]]] = {}

    async def _fetch(self, latitude: float, longitude: float) -> dict[str, Any]:
        key = (round(latitude, CACHE_COORD_PRECISION), round(longitude, CACHE_COORD_PRECISION))
        cached = self._cache.get(key)
        if cached is not None:
            fetched_at, payload = cached
            if time.monotonic() - fetched_at < settings.weather_cache_ttl_seconds:
                return payload

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": ",".join(HOURLY_FIELDS),
            "daily": "sunrise,sunset",
            "timezone": "UTC",
            "past_days": PAST_DAYS,
            "forecast_days": FORECAST_DAYS,
        }

        try:
            if self._client is not None:
                response = await self._client.get(settings.weather_api_url, params=params)
            else:
                async with httpx.AsyncClient(timeout=settings.weather_timeout_seconds) as client:
                    response = await client.get(settings.weather_api_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise WeatherUnavailable(str(exc)) from exc

        self._cache[key] = (time.monotonic(), payload)
        return payload

    async def get_snapshot(
        self, latitude: float, longitude: float, at: datetime
    ) -> WeatherSnapshot:
        payload = await self._fetch(latitude, longitude)
        return build_snapshot(payload, at)


def build_snapshot(payload: dict[str, Any], at: datetime) -> WeatherSnapshot:
    """Extrait les conditions à `at` d'une réponse Open-Meteo.

    Séparé du client réseau pour rester testable sans appel HTTP.
    """
    at = at.astimezone(timezone.utc)

    try:
        hourly = payload["hourly"]
        times = [_parse_api_datetime(raw) for raw in hourly["time"]]
        daily = payload["daily"]
        sunrises = [_parse_api_datetime(raw) for raw in daily["sunrise"]]
        sunsets = [_parse_api_datetime(raw) for raw in daily["sunset"]]
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherUnavailable(f"Réponse météo inexploitable : {exc}") from exc

    if not times or not sunrises or not sunsets:
        raise WeatherUnavailable("Réponse météo vide")

    # Les séries sont horaires : on prend l'heure pleine la plus proche.
    index = min(range(len(times)), key=lambda i: abs(times[i] - at))
    if abs(times[index] - at) > timedelta(hours=1):
        raise ForecastOutOfRange(
            f"Aucune prévision disponible pour {at.isoformat()} "
            f"(fenêtre : {times[0].isoformat()} → {times[-1].isoformat()})"
        )

    def series(field: str) -> list[float | None]:
        values = hourly.get(field)
        if not isinstance(values, list) or len(values) != len(times):
            raise WeatherUnavailable(f"Série météo manquante ou incomplète : {field}")
        return values

    def value_at(field: str, i: int) -> float:
        raw = series(field)[i]
        if raw is None:
            raise WeatherUnavailable(f"Valeur météo manquante : {field}")
        return float(raw)

    pressure = value_at("surface_pressure", index)
    earlier = index - PRESSURE_TREND_HOURS
    # En tout début de série la tendance n'est pas mesurable : on la déclare nulle
    # plutôt que de l'inventer, le facteur retombe alors sur « pression stable ».
    pressure_trend = pressure - value_at("surface_pressure", earlier) if earlier >= 0 else 0.0

    day_index = min(range(len(sunrises)), key=lambda i: abs(sunrises[i].date() - at.date()))

    return WeatherSnapshot(
        at=times[index],
        temperature_c=value_at("temperature_2m", index),
        pressure_hpa=pressure,
        pressure_trend_hpa=pressure_trend,
        cloud_cover_pct=value_at("cloud_cover", index),
        wind_speed_kmh=value_at("wind_speed_10m", index),
        precipitation_mm=value_at("precipitation", index),
        sunrise=sunrises[day_index],
        sunset=sunsets[day_index],
    )
