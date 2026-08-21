"""Conversion d'une adresse ou d'un code postal en coordonnées géographiques.

La source est la Base Adresse Nationale (BAN, data.gouv.fr), gratuite et sans
clé. Une même recherche renvoie toujours le même résultat : un cache mémoire
évite de rappeler l'API pour une requête déjà vue.
"""

import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import get_settings

settings = get_settings()

# Durée de vie du cache : les adresses ne bougent pas, une valeur haute suffit.
CACHE_TTL_SECONDS_DEFAULT = 86400


class GeocodingUnavailable(Exception):
    """La BAN n'a pas pu être jointe ou a renvoyé une réponse inexploitable."""


class GeocodingNotFound(Exception):
    """Aucune adresse ne correspond à la recherche."""


@dataclass(frozen=True)
class GeocodingResult:
    """Point trouvé pour une recherche, avec le libellé retenu par la BAN."""

    latitude: float
    longitude: float
    label: str
    postcode: str | None
    city: str | None


class GeocodingProvider(Protocol):
    async def geocode(self, query: str) -> GeocodingResult: ...


class BanGeocodingProvider:
    """Client Base Adresse Nationale avec cache mémoire à durée de vie limitée.

    Le cache est propre au processus : plusieurs workers gardent chacun le
    leur, et deux requêtes simultanées sur une recherche froide déclenchent
    deux appels. C'est sans conséquence (l'appel est idempotent) et suffisant
    à cette échelle.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}

    async def _fetch(self, query: str) -> dict[str, Any]:
        key = query.strip().lower()
        cached = self._cache.get(key)
        if cached is not None:
            fetched_at, payload = cached
            if time.monotonic() - fetched_at < settings.geocoding_cache_ttl_seconds:
                return payload

        params = {"q": query, "limit": 1}

        try:
            if self._client is not None:
                response = await self._client.get(settings.geocoding_api_url, params=params)
            else:
                async with httpx.AsyncClient(timeout=settings.geocoding_timeout_seconds) as client:
                    response = await client.get(settings.geocoding_api_url, params=params)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise GeocodingUnavailable(str(exc)) from exc

        self._cache[key] = (time.monotonic(), payload)
        return payload

    async def geocode(self, query: str) -> GeocodingResult:
        payload = await self._fetch(query)
        return build_result(payload)


def build_result(payload: dict[str, Any]) -> GeocodingResult:
    """Extrait le meilleur résultat d'une réponse BAN (GeoJSON).

    Séparé du client réseau pour rester testable sans appel HTTP.
    """
    try:
        features = payload["features"]
    except (KeyError, TypeError) as exc:
        raise GeocodingUnavailable(f"Réponse BAN inexploitable : {exc}") from exc

    if not features:
        raise GeocodingNotFound("Aucune adresse ne correspond à cette recherche")

    best = features[0]
    try:
        longitude, latitude = best["geometry"]["coordinates"]
        properties = best["properties"]
        label = properties["label"]
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingUnavailable(f"Réponse BAN inexploitable : {exc}") from exc

    return GeocodingResult(
        latitude=latitude,
        longitude=longitude,
        label=label,
        postcode=properties.get("postcode"),
        city=properties.get("city"),
    )
