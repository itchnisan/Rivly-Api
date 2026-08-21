"""Détection des types de plans d'eau à proximité d'un point via OpenStreetMap.

La source est l'API Overpass (gratuite, sans clé). Le résultat pour un secteur
donné ne change quasiment jamais : un cache mémoire évite de rappeler l'API à
chaque requête sur le même point.
"""

import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

settings = get_settings()

# Rayon de recherche autour du point, en mètres.
DEFAULT_SEARCH_RADIUS_METERS = 5000

# Précision de la clé de cache, en degrés (~1 km).
CACHE_COORD_PRECISION = 2

_OVERPASS_QUERY_TEMPLATE = """
[out:json][timeout:{timeout}];
(
  way["waterway"~"^(river|canal|stream)$"](around:{radius},{latitude},{longitude});
  way["natural"="water"](around:{radius},{latitude},{longitude});
  relation["natural"="water"](around:{radius},{latitude},{longitude});
  way["natural"="coastline"](around:{radius},{latitude},{longitude});
);
out tags;
"""

# Tags OSM -> catégorie. Décorrélé du `WaterType` persisté sur `Spot` : cette
# détection sert à suggérer des types à l'utilisateur, pas à les imposer.
_WATERWAY_TAGS = {"river": "river", "stream": "river", "canal": "canal"}
_NATURAL_WATER_TAGS = {"lake": "lake", "pond": "pond"}


class WaterTypeDetectionUnavailable(Exception):
    """La source OSM n'a pas pu être jointe ou a renvoyé une réponse inexploitable."""


@dataclass(frozen=True)
class WaterTypeDetection:
    """Types de plans d'eau détectés autour d'un point."""

    water_types: frozenset[str]


class WaterTypeProvider(Protocol):
    async def get_water_types(
        self, latitude: float, longitude: float, radius_meters: float = DEFAULT_SEARCH_RADIUS_METERS
    ) -> WaterTypeDetection: ...


class OverpassProvider:
    """Client Overpass avec cache mémoire à durée de vie limitée.

    Le cache est propre au processus : plusieurs workers gardent chacun le
    leur, et deux requêtes simultanées sur un secteur froid déclenchent deux
    appels. C'est sans conséquence (l'appel est idempotent) et suffisant à
    cette échelle.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._cache: dict[tuple[float, float, float], tuple[float, dict[str, Any]]] = {}

    async def _fetch(self, latitude: float, longitude: float, radius_meters: float) -> dict[str, Any]:
        key = (
            round(latitude, CACHE_COORD_PRECISION),
            round(longitude, CACHE_COORD_PRECISION),
            radius_meters,
        )
        cached = self._cache.get(key)
        if cached is not None:
            fetched_at, payload = cached
            if time.monotonic() - fetched_at < settings.overpass_cache_ttl_seconds:
                return payload

        query = _OVERPASS_QUERY_TEMPLATE.format(
            timeout=int(settings.overpass_timeout_seconds),
            radius=radius_meters,
            latitude=latitude,
            longitude=longitude,
        )

        try:
            if self._client is not None:
                response = await self._client.post(settings.overpass_api_url, data={"data": query})
            else:
                async with httpx.AsyncClient(timeout=settings.overpass_timeout_seconds) as client:
                    response = await client.post(settings.overpass_api_url, data={"data": query})
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise WaterTypeDetectionUnavailable(str(exc)) from exc

        self._cache[key] = (time.monotonic(), payload)
        return payload

    async def get_water_types(
        self, latitude: float, longitude: float, radius_meters: float = DEFAULT_SEARCH_RADIUS_METERS
    ) -> WaterTypeDetection:
        payload = await self._fetch(latitude, longitude, radius_meters)
        return build_detection(payload)


def build_detection(payload: dict[str, Any]) -> WaterTypeDetection:
    """Extrait les types de plans d'eau d'une réponse Overpass.

    Séparé du client réseau pour rester testable sans appel HTTP.
    """
    try:
        elements = payload["elements"]
    except (KeyError, TypeError) as exc:
        raise WaterTypeDetectionUnavailable(f"Réponse Overpass inexploitable : {exc}") from exc

    water_types: set[str] = set()
    for element in elements:
        tags = element.get("tags", {})

        waterway = _WATERWAY_TAGS.get(tags.get("waterway"))
        if waterway is not None:
            water_types.add(waterway)

        if tags.get("natural") == "coastline":
            water_types.add("sea")
        elif tags.get("natural") == "water":
            water_types.add(_NATURAL_WATER_TAGS.get(tags.get("water"), "lake"))

    return WaterTypeDetection(water_types=frozenset(water_types))
